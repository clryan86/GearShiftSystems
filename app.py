from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import config
from models import db, Part, Vendor, Order, OrderItem

def create_app():
    app = Flask(__name__)
    app.config.from_object("config")
    db.init_app(app)

    # ---------- ROUTES ----------

    @app.route("/")
    def index():
        low_parts = Part.query.filter(Part.stock <= Part.reorder_threshold).all()
        return render_template("index.html", low_parts=low_parts)

    # Parts: list (with optional low-stock filter)
    @app.route("/parts")
    def list_parts():
        show = request.args.get("show")
        if show == "low":
            parts = Part.query.filter(Part.stock <= Part.reorder_threshold).order_by(Part.name).all()
        else:
            parts = Part.query.order_by(Part.name).all()
        low_parts = [p for p in parts if p.is_low_stock]
        return render_template("parts_list.html", parts=parts, low_parts=low_parts)

    # Add a part
    @app.route("/parts/add", methods=["GET", "POST"])
    def add_part():
        if request.method == "POST":
            name = (request.form.get("name") or "").strip()
            sku = (request.form.get("sku") or "").strip()
            price = float(request.form.get("price") or 0)
            stock = int(request.form.get("stock") or 0)
            reorder_threshold = int(request.form.get("reorder_threshold") or 5)
            shelf_location = (request.form.get("shelf_location") or "").strip() or None
            vendor_name = (request.form.get("vendor_name") or "").strip() or None

            if not name or not sku:
                flash("Name and SKU are required.", "error")
                return redirect(url_for("add_part"))

            # find or create vendor by name (simple for Unit 2)
            vendor = None
            if vendor_name:
                vendor = Vendor.query.filter_by(name=vendor_name).first()
                if not vendor:
                    vendor = Vendor(name=vendor_name)
                    db.session.add(vendor)

            part = Part(
                name=name, sku=sku, price=price, stock=stock,
                reorder_threshold=reorder_threshold, shelf_location=shelf_location,
                vendor=vendor
            )
            db.session.add(part)
            db.session.commit()
            flash(f"Part '{name}' added.", "success")
            return redirect(url_for("list_parts"))

            # GET
        return render_template("add_part.html")

    # Edit a part
    @app.route("/parts/<int:part_id>/edit", methods=["GET", "POST"])
    def edit_part(part_id):
        part = Part.query.get_or_404(part_id)
        if request.method == "POST":
            part.name = (request.form.get("name") or "").strip()
            part.sku = (request.form.get("sku") or "").strip()
            part.price = float(request.form.get("price") or 0)
            part.stock = int(request.form.get("stock") or 0)
            part.reorder_threshold = int(request.form.get("reorder_threshold") or 5)
            part.shelf_location = (request.form.get("shelf_location") or "").strip() or None

            vendor_name = (request.form.get("vendor_name") or "").strip() or None
            if vendor_name:
                vendor = Vendor.query.filter_by(name=vendor_name).first()
                if not vendor:
                    vendor = Vendor(name=vendor_name)
                    db.session.add(vendor)
                part.vendor = vendor
            else:
                part.vendor = None

            if not part.name or not part.sku:
                flash("Name and SKU are required.", "error")
                return redirect(url_for("edit_part", part_id=part.id))

            db.session.commit()
            flash(f"Part '{part.name}' updated.", "success")
            return redirect(url_for("list_parts"))

        return render_template("edit_part.html", part=part)

    # Delete a part
    @app.route("/parts/<int:part_id>/delete", methods=["POST"])
    def delete_part(part_id):
        part = Part.query.get_or_404(part_id)
        db.session.delete(part)
        db.session.commit()
        flash("Part deleted.", "success")
        return redirect(url_for("list_parts"))

    # Quick vendor list (optional page later)
    @app.route("/api/vendors")
    def api_vendors():
        vendors = Vendor.query.order_by(Vendor.name).all()
        data = [{"id": v.id, "name": v.name, "email": v.contact_email, "phone": v.phone} for v in vendors]
        return jsonify(data)

    # JSON for parts (handy for screenshots/testing)
    @app.route("/api/parts")
    def api_parts():
        parts = Part.query.order_by(Part.name).all()
        data = []
        for p in parts:
            data.append({
                "id": p.id,
                "name": p.name,
                "sku": p.sku,
                "price": p.price,
                "stock": p.stock,
                "reorder_threshold": p.reorder_threshold,
                "shelf_location": p.shelf_location,
                "vendor": p.vendor.name if p.vendor else None,
                "is_low_stock": p.is_low_stock,
                "suggested_reorder_qty": p.suggested_reorder_qty(),
            })
        return jsonify(data)

    # One-click: draft a "reorder" in-memory (flash summary) for all low-stock items
    @app.route("/reorder/low", methods=["POST"])
    def reorder_low():
        low_parts = Part.query.filter(Part.stock <= Part.reorder_threshold).all()
        if not low_parts:
            flash("No parts are currently under their reorder threshold.", "info")
            return redirect(url_for("list_parts"))

        # Create an order record (no detail page yet)
        order = Order(status="draft")
        db.session.add(order)
        for p in low_parts:
            qty = p.suggested_reorder_qty() or 1
            item = OrderItem(order=order, part=p, qty=qty, unit_price=p.price)
            db.session.add(item)

        db.session.commit()
        flash(f"Draft reorder created for {len(low_parts)} low-stock items (Order #{order.id}).", "success")
        return redirect(url_for("list_parts"))

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    # Run dev server
    app.run(debug=config.DEBUG)
