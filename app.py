import os
import pathlib
from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, flash, Response, session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

# ⬇️ models now include the new PO/audit tables (safe to import even before they exist)
from models import (
    db,
    Part,
    Vendor,
    Order,
    OrderItem,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
)
from paypal_mini import paypal_bp            # existing PayPal mini blueprint
from cart import cart_bp                     # session cart blueprint you added
from datetime import datetime


# -----------------------------
# SQLite autopatch helper (non-destructive)
# -----------------------------
def _sqlite_autopatch(engine):
    """
    Non-destructive shim for SQLite: ensures newly-added columns exist on 'orders'
    (and optionally 'order_items'). Safe to run multiple times. Keeps your data.
    """
    with engine.connect() as conn:
        if conn.dialect.name != "sqlite":
            return

        # --- Patch 'orders' table ---
        res = conn.exec_driver_sql("PRAGMA table_info('orders');")
        order_cols = {row[1] for row in res.fetchall()}

        stmts = []
        if "buyer_name" not in order_cols:
            stmts.append("ALTER TABLE orders ADD COLUMN buyer_name VARCHAR(120)")
        if "buyer_email" not in order_cols:
            stmts.append("ALTER TABLE orders ADD COLUMN buyer_email VARCHAR(255)")
        if "status" not in order_cols:
            stmts.append("ALTER TABLE orders ADD COLUMN status VARCHAR(32) DEFAULT 'paid' NOT NULL")
        if "total_amount" not in order_cols:
            stmts.append("ALTER TABLE orders ADD COLUMN total_amount FLOAT DEFAULT 0.0 NOT NULL")

        for sql in stmts:
            conn.exec_driver_sql(sql)

        # --- (Optional) Patch 'order_items' table in case it pre-existed without snapshots ---
        res_items = conn.exec_driver_sql("PRAGMA table_info('order_items');")
        item_cols = {row[1] for row in res_items.fetchall()}

        item_stmts = []
        if item_cols:
            if "name_snapshot" not in item_cols:
                item_stmts.append("ALTER TABLE order_items ADD COLUMN name_snapshot VARCHAR(255)")
            if "sku_snapshot" not in item_cols:
                item_stmts.append("ALTER TABLE order_items ADD COLUMN sku_snapshot VARCHAR(120)")
            if "unit_price" not in item_cols:
                item_stmts.append("ALTER TABLE order_items ADD COLUMN unit_price FLOAT DEFAULT 0.0 NOT NULL")
            if "quantity" not in item_cols:
                item_stmts.append("ALTER TABLE order_items ADD COLUMN quantity INTEGER DEFAULT 0 NOT NULL")
            if "line_total" not in item_cols:
                item_stmts.append("ALTER TABLE order_items ADD COLUMN line_total FLOAT DEFAULT 0.0 NOT NULL")

            for sql in item_stmts:
                conn.exec_driver_sql(sql)


# -----------------------------
# App Factory
# -----------------------------
def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))

    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(basedir, "app.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="dev",  # replace for production
    )
    db.init_app(app)

    # ---- PayPal (minimal) ----------------------------------------------
    app.config.setdefault("PAYPAL_ENV", "sandbox")
    app.config.setdefault("PAYPAL_CLIENT_ID", os.getenv("PAYPAL_CLIENT_ID", "sb"))
    if "paypal" not in app.blueprints:
        app.register_blueprint(paypal_bp)
    # --------------------------------------------------------------------

    # ---- Cart (session-based) ------------------------------------------
    if "cart" not in app.blueprints:
        app.register_blueprint(cart_bp)

    @app.context_processor
    def inject_cart_count_global():
        cart = session.get("cart") or {}
        total_qty = 0
        for q in cart.values():
            try:
                total_qty += int(q)
            except Exception:
                pass
        return {"cart_count": total_qty}
    # --------------------------------------------------------------------

    # -----------------------------
    # ADD: very simple "email" stub (writes vendor email to ./outbox and logs)
    # -----------------------------
    def _emit_vendor_email(po: "PurchaseOrder"):
        outdir = pathlib.Path("outbox")
        outdir.mkdir(exist_ok=True)
        html = render_template("po_email.html", po=po)
        fname = f"po_{po.id}_to_{(po.vendor.name if po.vendor else 'unassigned').replace(' ', '_')}.html"
        fpath = outdir / fname
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[EMAIL STUB] Vendor PO #{po.id} written to: {fpath.resolve()}")

    # Quick health endpoint
    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # -----------------------------
    # Home / Dashboard
    # -----------------------------
    @app.route("/")
    def index():
        low_parts = Part.query.filter(Part.stock <= Part.reorder_threshold).all()
        return render_template("index.html", low_parts=low_parts)

    # -----------------------------
    # Contact
    # -----------------------------
    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        if request.method == "POST":
            flash("Thanks! Your message was received.", "success")
            return redirect(url_for("contact"))
        return render_template("contact.html")

    # -----------------------------
    # Parts – list / add / edit / delete / export
    # -----------------------------
    @app.route("/parts", methods=["GET"])
    def list_parts():
        """
        Optional filters:
          - ?q=<text> matches name, SKU, or vendor name (case-insensitive)
          - ?low=1 shows only low-stock items
        """
        q_text = (request.args.get("q") or "").strip()
        low_only = request.args.get("low", type=int)

        q = Part.query.options(joinedload(Part.vendor))  # eager-load vendor

        if q_text:
            like = f"%{q_text}%"
            q = q.outerjoin(Vendor).filter(
                or_(Part.name.ilike(like), Part.sku.ilike(like), Vendor.name.ilike(like))
            )

        if low_only == 1:
            q = q.filter(Part.stock <= Part.reorder_threshold)

        parts = q.order_by(Part.name.asc()).all()
        return render_template("parts_list.html", parts=parts)

    @app.route("/parts/add", methods=["GET", "POST"])
    def add_part():
        if request.method == "POST":
            # safe parsers
            def _i(v, d=0):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return d

            def _f(v, d=0.0):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return d

            name = (request.form.get("name") or "").strip()
            sku = (request.form.get("sku") or "").strip()

            # avoid IntegrityError on duplicate SKUs
            if sku and Part.query.filter_by(sku=sku).first():
                flash(f"SKU '{sku}' already exists. Use Edit or choose another SKU.", "warning")
                vendors = Vendor.query.order_by(Vendor.name.asc()).all()
                return render_template("add_part.html", vendors=vendors, form=request.form)

            price = _f(request.form.get("price", "0"))
            stock = _i(request.form.get("stock", "0"))
            threshold = _i(request.form.get("reorder_threshold", "5"), 5)
            shelf = (request.form.get("shelf_location") or "").strip()

            vendor_id_raw = request.form.get("vendor_id")
            vendor_id = _i(vendor_id_raw, d=None) if vendor_id_raw else None

            p = Part(
                name=name,
                sku=sku,
                price=price,
                stock=stock,
                shelf_location=shelf,
                reorder_threshold=threshold,
                vendor_id=vendor_id,
            )
            db.session.add(p)
            try:
                db.session.commit()
                flash("Part added!", "success")
                return redirect(url_for("list_parts"))
            except IntegrityError:
                db.session.rollback()
                flash("Database error while adding part.", "danger")
                vendors = Vendor.query.order_by(Vendor.name.asc()).all()
                return render_template("add_part.html", vendors=vendors, form=request.form)

        vendors = Vendor.query.order_by(Vendor.name.asc()).all()
        return render_template("add_part.html", vendors=vendors, form={})

    @app.route("/parts/<int:part_id>/edit", methods=["GET", "POST"])
    def edit_part(part_id):
        part = Part.query.get_or_404(part_id)

        if request.method == "POST":
            def _i(v, d=0):
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return d

            def _f(v, d=0.0):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return d

            name = (request.form.get("name") or "").strip()
            new_sku = (request.form.get("sku") or "").strip()

            # block SKU collision with OTHER parts
            if new_sku and Part.query.filter(Part.id != part.id, Part.sku == new_sku).first():
                flash(f"SKU '{new_sku}' is already used by another part.", "warning")
                vendors = Vendor.query.order_by(Vendor.name.asc()).all()
                return render_template("edit_part.html", part=part, vendors=vendors, form=request.form)

            part.name = name
            part.sku = new_sku
            part.price = _f(request.form.get("price", "0"))
            part.stock = _i(request.form.get("stock", "0"))
            part.reorder_threshold = _i(request.form.get("reorder_threshold", "5"), 5)
            part.shelf_location = (request.form.get("shelf_location") or "").strip()

            vendor_id_raw = request.form.get("vendor_id")
            part.vendor_id = _i(vendor_id_raw, d=None) if vendor_id_raw else None

            db.session.commit()
            flash("Part updated.", "success")
            return redirect(url_for("list_parts"))

        vendors = Vendor.query.order_by(Vendor.name.asc()).all()
        return render_template("edit_part.html", part=part, vendors=vendors, form=None)

    @app.route("/parts/<int:part_id>/delete", methods=["POST"])
    def delete_part(part_id):
        part = Part.query.get_or_404(part_id)
        db.session.delete(part)
        db.session.commit()
        flash("Part deleted.", "info")
        return redirect(url_for("list_parts"))

    @app.route("/parts/export", methods=["GET"])
    def export_parts():
        """Stream a CSV export of all parts (with vendor names)."""
        parts = Part.query.options(joinedload(Part.vendor)).order_by(Part.name.asc()).all()

        def generate():
            yield "name,sku,price,stock,reorder_threshold,shelf_location,vendor\n"
            for p in parts:
                vendor_name = p.vendor.name if p.vendor else ""
                row = [
                    (p.name or "").replace(",", " "),
                    (p.sku or "").replace(",", " "),
                    f"{float(p.price or 0):.2f}",
                    str(int(p.stock or 0)),
                    str(int(p.reorder_threshold or 0)),
                    (p.shelf_location or "").replace(",", " "),
                    vendor_name.replace(",", " "),
                ]
                yield ",".join(row) + "\n"

        return Response(
            generate(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=parts.csv"},
        )

    # -----------------------------
    # Vendors – list / add / delete
    # -----------------------------
    @app.route("/vendors", methods=["GET"])
    def list_vendors():
        vendors = Vendor.query.order_by(Vendor.name.asc()).all()
        return render_template("vendors.html", vendors=vendors)

    @app.route("/vendors/add", methods=["POST"])
    def add_vendor():
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("contact_email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        if not name:
            flash("Vendor name is required.", "warning")
            return redirect(url_for("list_vendors"))

        db.session.add(Vendor(name=name, contact_email=email, phone=phone))
        db.session.commit()
        flash("Vendor added.", "success")
        return redirect(url_for("list_vendors"))

    @app.route("/vendors/<int:vendor_id>/delete", methods=["POST"])
    def delete_vendor(vendor_id):
        vendor = Vendor.query.get_or_404(vendor_id)
        db.session.delete(vendor)
        db.session.commit()
        flash("Vendor deleted.", "info")
        return redirect(url_for("list_vendors"))

    # -----------------------------
    # Draft Reorder (low-stock) + PO preview/CSV (existing behavior)
    # -----------------------------
    @app.route("/reorder/draft", methods=["GET", "POST"], endpoint="reorder_draft")
    def reorder_draft():
        """
        GET: show draft page listing low-stock items with suggested quantities.
        POST: same view (for compatibility); most submit actions go to /reorder/po.
        """
        items = (
            Part.query.options(joinedload(Part.vendor))
            .filter(Part.stock <= Part.reorder_threshold)
            .order_by(Part.name.asc())
            .all()
        )
        return render_template("reorder_draft.html", items=items)

    app.add_url_rule(
        "/reorder/draft",
        endpoint="draft_reorder",
        view_func=reorder_draft,
        methods=["POST"],
    )

    @app.route("/reorder/po", methods=["POST"])
    def generate_po():
        """
        Build a grouped Purchase Order PREVIEW from selected items posted by reorder_draft.html.
        If 'download' is present in the form, return CSV; otherwise show a preview page.
        """
        selected_ids = request.form.getlist("part_id")
        if not selected_ids:
            flash("No items selected for PO.", "warning")
            return redirect(url_for("reorder_draft"))

        # map id->qty from posted fields like qty_<id>
        qty_map = {}
        for pid in selected_ids:
            q = request.form.get(f"qty_{pid}", "").strip()
            try:
                qty_map[int(pid)] = max(int(q), 0)
            except (TypeError, ValueError):
                qty_map[int(pid)] = 0

        parts = (
            Part.query.options(joinedload(Part.vendor))
            .filter(Part.id.in_(qty_map.keys()))
            .order_by(Part.name.asc())
            .all()
        )

        grouped = defaultdict(list)
        vendor_totals = defaultdict(float)
        grand_total = 0.0

        for p in parts:
            qty = qty_map.get(p.id, 0)
            if qty <= 0:
                continue
            vendor_name = p.vendor.name if p.vendor else "Unassigned vendor"
            unit_price = float(p.price or 0)
            line_total = unit_price * qty
            grouped[vendor_name].append(
                {
                    "id": p.id,
                    "name": p.name,
                    "sku": p.sku,
                    "shelf_location": p.shelf_location,
                    "qty": qty,
                    "unit_price": unit_price,
                    "line_total": line_total,
                }
            )
            vendor_totals[vendor_name] += line_total
            grand_total += line_total

        if not grouped:
            flash("All selected items had zero quantity. Please adjust and try again.", "warning")
            return redirect(url_for("reorder_draft"))

        # CSV download?
        if request.form.get("download"):
            def gen_csv():
                yield "vendor,part,sku,qty,unit_price,line_total,shelf\n"
                for vendor_name in sorted(grouped.keys()):
                    for row in grouped[vendor_name]:
                        yield ",".join(
                            [
                                vendor_name.replace(",", " "),
                                (row["name"] or "").replace(",", " "),
                                (row["sku"] or "").replace(",", " "),
                                str(row["qty"]),
                                f"{row['unit_price']:.2f}",
                                f"{row['line_total']:.2f}",
                                (row["shelf_location"] or "").replace(",", " "),
                            ]
                        ) + "\n"
                    yield f"{vendor_name},SUBTOTAL,,,,{vendor_totals[vendor_name]:.2f},\n"
                yield f"ALL,GRAND TOTAL,,,,{grand_total:.2f},\n"

            return Response(
                gen_csv(),
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=purchase_order.csv"},
            )

        # Otherwise show a preview page
        return render_template(
            "po_preview.html",
            grouped=grouped,
            vendor_totals=vendor_totals,
            grand_total=grand_total,
        )

    # -----------------------------
    # Orders – list + detail (existing)
    # -----------------------------
    @app.route("/orders")
    def orders_list():
        orders = Order.query.order_by(Order.created_at.desc()).all()
        return render_template("orders_list.html", orders=orders)

    @app.route("/orders/<int:order_id>")
    def order_detail(order_id):
        order = Order.query.get_or_404(order_id)
        computed_total = sum((it.line_total or 0.0) for it in order.items)
        return render_template("order_detail.html", order=order, computed_total=computed_total)

    # -----------------------------
    # NEW: Persisted Purchase Orders lifecycle
    # -----------------------------
    @app.post("/pos/create")
    def create_pos():
        """
        Creates persisted Purchase Orders from the same form payload used by /reorder/po.
        Groups lines by vendor. Unassigned vendor is allowed.
        """
        selected_ids = request.form.getlist("part_id")
        if not selected_ids:
            flash("No items selected for PO.", "warning")
            return redirect(url_for("reorder_draft"))

        # Map part_id -> qty using qty_<id> fields
        qty_map = {}
        for pid in selected_ids:
            try:
                qty_map[int(pid)] = max(int(request.form.get(f"qty_{pid}", "0")), 0)
            except Exception:
                qty_map[int(pid)] = 0

        parts = (
            Part.query.options(joinedload(Part.vendor))
            .filter(Part.id.in_(qty_map.keys()))
            .order_by(Part.name.asc())
            .all()
        )

        # Group by vendor_id (None allowed)
        by_vendor = defaultdict(list)
        for p in parts:
            qty = qty_map.get(p.id, 0)
            if qty > 0:
                by_vendor[p.vendor_id].append((p, qty))

        if not by_vendor:
            flash("All selected items had zero quantity.", "warning")
            return redirect(url_for("reorder_draft"))

        created = []
        for vendor_id, rows in by_vendor.items():
            po = PurchaseOrder(vendor_id=vendor_id, status="DRAFT")
            db.session.add(po)
            for part, qty in rows:
                db.session.add(
                    PurchaseOrderItem(
                        po=po,
                        product_id=part.id,
                        qty_ordered=qty,
                        unit_cost=float(part.price or 0.0),
                    )
                )
            created.append(po)

        db.session.commit()
        if len(created) == 1:
            flash(f"Purchase Order #{created[0].id} created in DRAFT.", "success")
            return redirect(url_for("po_detail", po_id=created[0].id))
        else:
            flash(f"{len(created)} Purchase Orders created in DRAFT.", "success")
            return redirect(url_for("po_list"))

    @app.get("/pos")
    def po_list():
        pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
        return render_template("purchase_orders.html", pos=pos)

    @app.get("/pos/<int:po_id>")
    def po_detail(po_id):
        po = PurchaseOrder.query.get_or_404(po_id)
        return render_template("purchase_order_detail.html", po=po)

    @app.post("/pos/<int:po_id>/approve")
    def po_approve(po_id):
        po = PurchaseOrder.query.get_or_404(po_id)
        if po.status != "DRAFT":
            flash("Only DRAFT POs can be approved.", "warning")
            return redirect(url_for("po_detail", po_id=po.id))
        po.status = "APPROVED"
        po.approved_at = datetime.utcnow()
        db.session.commit()
        flash("PO approved.", "success")
        return redirect(url_for("po_detail", po_id=po.id))

    @app.post("/pos/<int:po_id>/send")
    def po_send(po_id):
        po = PurchaseOrder.query.get_or_404(po_id)
        if po.status not in {"APPROVED", "DRAFT"}:
            flash("Only DRAFT or APPROVED POs can be sent.", "warning")
            return redirect(url_for("po_detail", po_id=po.id))
        po.status = "SENT"
        po.sent_at = datetime.utcnow()
        db.session.commit()
        _emit_vendor_email(po)  # email stub: writes HTML to ./outbox
        flash("PO sent to vendor (see ./outbox).", "success")
        return redirect(url_for("po_detail", po_id=po.id))

    @app.post("/pos/<int:po_id>/receive")
    def po_receive(po_id):
        """
        Receives line items. Form fields: receive_<item.id>=<int>
        Increments Part.stock and writes StockMovement(+).
        """
        po = PurchaseOrder.query.get_or_404(po_id)
        if po.status not in {"SENT", "APPROVED", "PARTIALLY_RECEIVED"}:
            flash("PO must be SENT or APPROVED to receive.", "warning")
            return redirect(url_for("po_detail", po_id=po.id))

        any_received = False
        for it in po.items:
            fval = request.form.get(f"receive_{it.id}", "").strip()
            if not fval:
                continue
            try:
                delta = max(int(fval), 0)
            except Exception:
                delta = 0
            if delta <= 0:
                continue
            # Cap at remaining
            remaining = max((it.qty_ordered or 0) - (it.qty_received or 0), 0)
            to_apply = min(delta, remaining)
            if to_apply <= 0:
                continue
            # Apply to item
            it.qty_received = (it.qty_received or 0) + to_apply
            # Increment stock
            part = Part.query.get(it.product_id)
            part.stock = int(part.stock or 0) + to_apply
            # Stock movement audit
            db.session.add(
                StockMovement(
                    product_id=part.id,
                    qty_delta=to_apply,
                    reason="PO_RECEIVE",
                    ref_type="PO",
                    ref_id=po.id,
                )
            )
            any_received = True

        if not any_received:
            flash("No quantities to receive.", "info")
            return redirect(url_for("po_detail", po_id=po.id))

        # Update PO status
        all_full = all((li.qty_received or 0) >= (li.qty_ordered or 0) for li in po.items)
        po.status = "RECEIVED" if all_full else "PARTIALLY_RECEIVED"
        if po.status == "RECEIVED":
            po.received_at = datetime.utcnow()

        db.session.commit()
        flash("Receipt recorded.", "success")
        return redirect(url_for("po_detail", po_id=po.id))

    @app.post("/pos/<int:po_id>/cancel")
    def po_cancel(po_id):
        po = PurchaseOrder.query.get_or_404(po_id)
        if po.status in {"RECEIVED"}:
            flash("Received POs cannot be canceled.", "warning")
        else:
            po.status = "CANCELED"
            db.session.commit()
            flash("PO canceled.", "info")
        return redirect(url_for("po_detail", po_id=po.id))

    return app


# -----------------------------
# Dev Entrypoint
# -----------------------------
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
        _sqlite_autopatch(db.engine)
    app.run(debug=True)
