import os
from flask import Flask, render_template, request, redirect, url_for, flash, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from models import db, Part, Vendor
from paypal_mini import paypal_bp   # <-- [NEW] import the PayPal blueprint


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

    # -----------------------------
    # Home / Dashboard
    # -----------------------------
    @app.route("/")
    def index():
        low_parts = Part.query.filter(Part.stock <= Part.reorder_threshold).all()
        return render_template("index.html", low_parts=low_parts)

    # -----------------------------
    # Contact (Sabir’s page)
    # -----------------------------
    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        """
        Simple contact page. If you add a form later, you can handle POST here.
        Ensure templates/contact.html exists.
        """
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
        List parts, with optional low-stock filter via ?low=1.
        Eager-load vendor so the template can safely show vendor names.
        """
        low_only = request.args.get("low", type=int)
        q = Part.query.options(joinedload(Part.vendor))  # <-- eager-load
        if low_only == 1:
            q = q.filter(Part.stock <= Part.reorder_threshold)
        parts = q.order_by(Part.name.asc()).all()
        return render_template("parts_list.html", parts=parts)

    @app.route("/parts/add", methods=["GET", "POST"])
    def add_part():
        if request.method == "POST":
            # Parse numbers safely
            def _i(v, d=0):
                try: return int(v)
                except (TypeError, ValueError): return d
            def _f(v, d=0.0):
                try: return float(v)
                except (TypeError, ValueError): return d

            name = (request.form.get("name") or "").strip()
            sku = (request.form.get("sku") or "").strip()

            # PRE-CHECK: avoid IntegrityError on duplicate SKUs
            if Part.query.filter_by(sku=sku).first():
                flash(f"SKU '{sku}' already exists. Use Edit or choose another SKU.", "warning")
                vendors = Vendor.query.order_by(Vendor.name.asc()).all()
                # Re-render with the user’s input preserved
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
            # Parse numbers safely
            def _i(v, d=0):
                try: return int(v)
                except (TypeError, ValueError): return d
            def _f(v, d=0.0):
                try: return float(v)
                except (TypeError, ValueError): return d

            name = (request.form.get("name") or "").strip()
            new_sku = (request.form.get("sku") or "").strip()

            # Prevent changing to a SKU used by *another* part
            exists = Part.query.filter(Part.id != part.id, Part.sku == new_sku).first()
            if exists:
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
        parts = (
            Part.query.options(joinedload(Part.vendor))
            .order_by(Part.name.asc())
            .all()
        )

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
    # Draft Reorder (low-stock)
    # -----------------------------
    @app.route("/reorder/draft", methods=["GET", "POST"])
    def draft_reorder():
        """
        POST: compute draft reorder (flash summary), redirect to parts.
        GET: show a simple draft page listing low-stock items.
        """
        low = Part.query.options(joinedload(Part.vendor)).filter(
            Part.stock <= Part.reorder_threshold
        ).all()

        if request.method == "GET":
            return render_template("reorder_draft.html", items=low)

        if not low:
            flash("No low-stock items detected. Inventory looks healthy!", "success")
            return redirect(url_for("index"))

        suggestions = []
        for p in low:
            target = max((p.reorder_threshold or 0) * 2, (p.stock or 0) + 1)
            suggested = max(target - (p.stock or 0), 1)
            suggestions.append((p, suggested))

        flash("Draft reorder created (not placed yet):", "success")
        for p, qty in suggestions:
            vendor = p.vendor.name if p.vendor else "Unassigned vendor"
            flash(f"{p.name} (SKU {p.sku}) → qty {qty} · {vendor}", "muted")

        return redirect(url_for("list_parts"))

    return app


# -----------------------------
# Dev Entrypoint
# -----------------------------
if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)
