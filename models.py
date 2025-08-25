from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Vendor(db.Model):
    __tablename__ = "vendors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    notes = db.Column(db.Text)

    parts = db.relationship("Part", back_populates="vendor", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Vendor {self.name}>"


class Part(db.Model):
    __tablename__ = "parts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), nullable=False, unique=True, index=True)
    price = db.Column(db.Float, nullable=False, default=0.0)
    stock = db.Column(db.Integer, nullable=False, default=0)

    # New fields for Unit 2
    reorder_threshold = db.Column(db.Integer, nullable=False, default=5)
    shelf_location = db.Column(db.String(50))

    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"))
    vendor = db.relationship("Vendor", back_populates="parts")

    order_items = db.relationship("OrderItem", back_populates="part")

    @property
    def is_low_stock(self) -> bool:
        try:
            return int(self.stock) <= int(self.reorder_threshold)
        except Exception:
            return False

    def suggested_reorder_qty(self) -> int:
        """
        Simple heuristic: bring stock up to 2x threshold.
        e.g., threshold 10, stock 4 -> suggest 16-4 = 12.
        """
        target = max(0, (self.reorder_threshold * 2) - self.stock)
        return target if self.is_low_stock else 0

    def __repr__(self) -> str:
        return f"<Part {self.name} ({self.sku})>"


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default="draft")  # draft/submitted/received

    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Order #{self.id} {self.status}>"


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False, default=0.0)

    order = db.relationship("Order", back_populates="items")
    part = db.relationship("Part", back_populates="order_items")

    def __repr__(self) -> str:
        return f"<OrderItem part={self.part_id} qty={self.qty}>"
