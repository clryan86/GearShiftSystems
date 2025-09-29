# cart.py
from flask import Blueprint, session, redirect, url_for, flash, render_template, request
from werkzeug.exceptions import BadRequest
from models import db, Part

cart_bp = Blueprint("cart", __name__, url_prefix="/cart")

def _get_cart():
    cart = session.get("cart")
    if not isinstance(cart, dict):
        cart = {}
    return cart

def _save_cart(cart):
    session["cart"] = cart
    session.modified = True

def _cart_items(cart):
    """Yield (part, qty, line_total) for valid parts in cart."""
    part_ids = [int(k) for k in cart.keys() if str(k).isdigit()]
    parts = Part.query.filter(Part.id.in_(part_ids)).all() if part_ids else []
    parts_by_id = {p.id: p for p in parts}
    for sid, qty in cart.items():
        try:
            pid = int(sid)
        except Exception:
            continue
        part = parts_by_id.get(pid)
        if not part:
            continue
        q = max(0, int(qty or 0))
        line = float(part.price or 0.0) * q
        yield part, q, line

@cart_bp.app_context_processor
def inject_cart_count():
    cart = _get_cart()
    total_qty = sum(int(q or 0) for q in cart.values())
    return {"cart_count": total_qty}

@cart_bp.get("/")
def view_cart():
    cart = _get_cart()
    items = list(_cart_items(cart))
    subtotal = sum(line for _, __, line in items)
    return render_template("cart.html", items=items, subtotal=subtotal)

@cart_bp.post("/update")
def update_cart():
    cart = _get_cart()
    if "qty" not in request.form:
        raise BadRequest("Missing qty payload")
    for sid, qty in request.form.getlist("item_id"):
        pass  # (not used; kept for compatibility)
    # Simpler: parse items[] and qty[]
    ids = request.form.getlist("ids[]")
    qtys = request.form.getlist("qtys[]")
    for sid, sqty in zip(ids, qtys):
        try:
            q = max(0, int(sqty))
        except Exception:
            q = 0
        if q == 0:
            cart.pop(sid, None)
        else:
            cart[sid] = q
    _save_cart(cart)
    flash("Cart updated.", "success")
    return redirect(url_for("cart.view_cart"))

@cart_bp.get("/add/<int:part_id>")
def add(part_id: int):
    part = Part.query.get_or_404(part_id)
    if (part.stock or 0) <= 0:
        flash("That item is out of stock.", "danger")
        return redirect(url_for("list_parts"))
    cart = _get_cart()
    new_qty = int(cart.get(str(part_id), 0)) + 1
    # Cap by available stock so users can't over-add
    new_qty = min(new_qty, int(part.stock or 0))
    cart[str(part_id)] = new_qty
    _save_cart(cart)
    flash(f"Added '{part.name}' to cart.", "success")
    return redirect(url_for("list_parts"))

@cart_bp.post("/remove/<int:part_id>")
def remove(part_id: int):
    cart = _get_cart()
    cart.pop(str(part_id), None)
    _save_cart(cart)
    flash("Item removed.", "success")
    return redirect(url_for("cart.view_cart"))

@cart_bp.get("/checkout")
def checkout_view():
    cart = _get_cart()
    items = list(_cart_items(cart))
    if not items:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("list_parts"))
    subtotal = sum(line for _, __, line in items)
    return render_template("checkout.html", items=items, subtotal=subtotal)

@cart_bp.post("/checkout")
def checkout_submit():
    cart = _get_cart()
    items = list(_cart_items(cart))
    if not items:
        flash("Your cart is empty.", "danger")
        return redirect(url_for("list_parts"))

    # Validate stock one last time and decrement
    for part, qty, _ in items:
        if qty > (part.stock or 0):
            flash(f"Not enough stock for {part.name}.", "danger")
            return redirect(url_for("cart.view_cart"))

    for part, qty, _ in items:
        part.stock = int(part.stock or 0) - qty
    db.session.commit()

    # Clear cart
    session.pop("cart", None)
    session.modified = True

    flash("Order placed. Inventory updated.", "success")
    return redirect(url_for("list_parts"))
vvvv
