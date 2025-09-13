# paypal_mini.py
from flask import Blueprint, render_template, current_app, flash, redirect, url_for
from models import Part

paypal_bp = Blueprint("paypal", __name__)

@paypal_bp.route("/buy/<int:part_id>")
def buy(part_id: int):
    part = Part.query.get_or_404(part_id)
    if getattr(part, "stock", 0) <= 0:
        flash("Out of stock.", "warning")
        return redirect(url_for("list_parts"))

    # Use config value if present, otherwise sandbox demo Client ID ("sb")
    client_id = current_app.config.get("PAYPAL_CLIENT_ID") or "sb"
    return render_template("checkout.html", part=part, paypal_client_id=client_id)
