from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Part
import config  # loads SQLAlchemy settings

app = Flask(__name__)
app.config.from_object("config")      # uses SQLALCHEMY_DATABASE_URI, SECRET_KEY, etc.
db.init_app(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/parts")
def list_parts():
    parts = Part.query.order_by(Part.name).all()
    return render_template("parts_list.html", parts=parts)

@app.route("/parts/add", methods=["GET", "POST"])
def add_part():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        sku  = request.form.get("sku", "").strip()
        price = float(request.form.get("price") or 0)
        stock = int(request.form.get("stock") or 0)

        if not name or not sku:
            flash("Name and SKU are required.", "error")
            return redirect(url_for("add_part"))

        p = Part(name=name, sku=sku, price=price, stock=stock)
        db.session.add(p)
        db.session.commit()
        flash("Part added!", "success")
        return redirect(url_for("list_parts"))
    return render_template("add_part.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()   # ensure tables exist on first run
    app.run(debug=True)

