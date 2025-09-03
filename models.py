from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(50))

    parts = db.relationship("Part", backref="vendor", lazy=True)

    def __repr__(self):
        return f"<Vendor {self.name}>"

class Part(db.Model):
    __tablename__ = "parts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(80), nullable=False, unique=True)
    price = db.Column(db.Float, nullable=False)

    # use 'stock' to match your seed data & templates
    stock = db.Column(db.Integer, nullable=False, default=0)

    shelf_location = db.Column(db.String(50))
    reorder_threshold = db.Column(db.Integer, nullable=False, default=5)

    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)

    def __repr__(self):
        return f"<Part {self.name} - {self.sku}>"

    def is_low_stock(self) -> bool:
        return self.stock <= self.reorder_threshold

def get_low_stock_parts():
    return Part.query.filter(Part.stock <= Part.reorder_threshold).all()

def get_all_vendors():
    return Vendor.query.all()
