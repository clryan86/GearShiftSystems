import os
from flask import (
    Flask, render_template, request, redirect, url_for, flash, Response
)
from models import db, Part, Vendor


# -----------------------------
# App Factory
# -----------------------------
def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))

    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(basedir, "app.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="dev",  # replace in prod
    )
    db.init_app(app)

    # -----------------------------
    # Home / Dashboard
    # -----------------------------
    @app.route("/")
    def index():
        low_parts = Part.query.filter(Part.stock <= Part.reorder_threshold).all()
        return render_template("index.html", low_parts=low_parts)

    # -----------------------------
    # Parts – list / add / edit / delete / export
    # -----------------------------
    @app.route("/parts", methods=["GET"])
    def list_parts():
        """List parts, with optional low-stock filter via ?low=1."""
        low_only = request.args.get("low", type=int)
        q = Part.query
        if low_only == 1:
            q = q.filter(Part.stock <= Part.reorder_threshold)
        parts = q.order_by(Part.name.asc()).all()
        return render_template("parts_list.html", parts=parts)

    @app.route("/parts/add", methods=["GET", "POST"])
    def add_part():
        if request.method == "POST":
            try:
                price = float(request.form.get("price", "0") or 0)
                stock = int(request.form.get("stock", "0") or 0)
                threshold = int(request.form.get("reorder_threshold", "5") or 5)
            except ValueError:
                flash("Invalid number in Price/Stock/Threshold.", "warning")
                return redirect(url_for("add_part"))

            vendor_id = request.form.get("vendor_id")
            vendor_id = int(vendor_id) if vendor_id else None

            p = Part(
                name=request.form["name"].strip(),
                sku=request.form["sku"].strip(),
                price=price,
                stock=stock,
                shelf_location=(request.form.get("shelf_location") or "").strip(),
                reorder_threshold=threshold,
                vendor_id=vendor_id,
            )
            db.session.add(p)
            db.session.commit()
            flash("Part added!", "success")
            return redirect(url_for("list_parts"))

        vendors = Vendor.query.order_by(Vendor.name.asc()).all()
        return render_template("add_part.html", vendors=vendors)

    @app.route("/parts/<int:part_id>/edit", methods=["GET", "POST"])
    def edit_part(part_id):
        part = Part.query.get_or_404(part_id)

        if request.method == "POST":
            try:
                part.price = float(request.form.get("price", "0") or 0)
                part.stock = int(request.form.get("stock", "0") or 0)
                part.reorder_threshold = int(request.form.get("reorder_threshold", "5") or 5)
            except ValueError:
                flash("Invalid number in Price/Stock/Threshold.", "warning")
                return redirect(url_for("edit_part", part_id=part.id))

            part.name = request.form["name"].strip()
            part.sku = request.form["sku"].strip()
            part.shelf_location = (request.form.get("shelf_location") or "").strip()

            vendor_id = request.form.get("vendor_id")
            part.vendor_id = int(vendor_id) if vendor_id else None

            db.session.commit()
            flash("Part updated.", "success")
            return redirect(url_for("list_parts"))

        vendors = Vendor.query.order_by(Vendor.name.asc()).all()
        return render_template("edit_part.html", part=part, vendors=vendors)

    @app.route("/parts/<int:part_id>/delete", methods=["POST"])
    def delete_part(part_id):
        part = Part.query.get_or_404(part_id)
        db.session.delete(part)
        db.session.commit()
        flash("Part deleted.", "info")
        return redirect(url_for("list_parts"))

    @app.route("/parts/export", methods=["GET"])
    def export_parts():
        """Stream a CSV export of all parts."""
        parts = Part.query.order_by(Part.name.asc()).all()

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
        low = Part.query.filter(Part.stock <= Part.reorder_threshold).all()

        if request.method == "GET":
            return render_template("reorder_draft.html", items=low)

        # POST path
        if not low:
            flash("No low-stock items detected. Inventory looks healthy!", "success")
            return redirect(url_for("index"))

        suggestions = []
        for p in low:
            # naive target: 2x threshold, at least +1 beyond current
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
