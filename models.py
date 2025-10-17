from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index
from datetime import datetime

db = SQLAlchemy()

# -----------------------------
# Vendor
# -----------------------------
class Vendor(db.Model):
    __tablename__ = "vendors"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    contact_email = db.Column(db.String(120))
    phone = db.Column(db.String(50))

    parts = db.relationship("Part", backref="vendor", lazy=True)

    def __repr__(self):
        return f"<Vendor {self.name}>"

    # convenience for display / JSON
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "contact_email": self.contact_email,
            "phone": self.phone,
            "parts_count": len(self.parts or []),
        }


# -----------------------------
# Part
# -----------------------------
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

    # Helpful index for name searches (non-unique)
    __table_args__ = (
        Index("ix_parts_name", "name"),
    )

    def __repr__(self):
        return f"<Part {self.name} - {self.sku}>"

    def is_low_stock(self) -> bool:
        try:
            return int(self.stock or 0) <= int(self.reorder_threshold or 0)
        except Exception:
            return False

    # convenience for display / JSON
    @property
    def in_stock(self) -> bool:
        return (self.stock or 0) > 0

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "sku": self.sku,
            "price": float(self.price or 0.0),
            "stock": int(self.stock or 0),
            "shelf_location": self.shelf_location,
            "reorder_threshold": int(self.reorder_threshold or 0),
            "vendor_id": self.vendor_id,
            "is_low_stock": self.is_low_stock(),
        }


def get_low_stock_parts():
    return Part.query.filter(Part.stock <= Part.reorder_threshold).all()


def get_all_vendors():
    return Vendor.query.all()


# -----------------------------
# Order tracking models
# -----------------------------
class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Optional buyer info (no auth required)
    buyer_name = db.Column(db.String(120))
    buyer_email = db.Column(db.String(255))

    # 'paid','pending','failed','refunded', etc.
    status = db.Column(db.String(32), default="paid", nullable=False)
    total_amount = db.Column(db.Float, default=0.0, nullable=False)

    items = db.relationship(
        "OrderItem",
        backref="order",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="OrderItem.id.asc()",
    )

    # Useful indexes
    __table_args__ = (
        Index("ix_orders_created_at", "created_at"),
        Index("ix_orders_status", "status"),
    )

    def compute_total(self):
        return sum((item.line_total or 0.0) for item in self.items or [])

    # convenience
    @property
    def item_count(self) -> int:
        return sum(int(i.quantity or 0) for i in (self.items or []))

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "buyer_name": self.buyer_name,
            "buyer_email": self.buyer_email,
            "status": self.status,
            "total_amount": float(self.total_amount or 0.0),
            "item_count": self.item_count,
            "items": [i.to_dict() for i in (self.items or [])],
        }


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)

    # Link to the part at the time of purchase (nullable in case part is later deleted)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id"), nullable=True)

    # Snapshots preserve history even if Part changes later
    name_snapshot = db.Column(db.String(255))
    sku_snapshot = db.Column(db.String(120))
    unit_price = db.Column(db.Float, default=0.0, nullable=False)

    # Map Python attr "quantity" to DB column "qty" to keep older DBs happy.
    quantity = db.Column("qty", db.Integer, default=0, nullable=False)
    line_total = db.Column(db.Float, default=0.0, nullable=False)

    # Small index for reporting
    __table_args__ = (
        Index("ix_order_items_order_id", "order_id"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "part_id": self.part_id,
            "name": self.name_snapshot,
            "sku": self.sku_snapshot,
            "unit_price": float(self.unit_price or 0.0),
            "quantity": int(self.quantity or 0),
            "line_total": float(self.line_total or 0.0),
        }


# -----------------------------
# Purchase Orders + Stock Movements
# -----------------------------
class PurchaseOrder(db.Model):
    __tablename__ = "purchase_orders"
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="DRAFT")  # DRAFT/APPROVED/SENT/PARTIALLY_RECEIVED/RECEIVED/CANCELED
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    approved_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    received_at = db.Column(db.DateTime)

    vendor = db.relationship("Vendor", lazy="joined")
    items = db.relationship("PurchaseOrderItem", backref="po", cascade="all, delete-orphan")

    @property
    def total(self) -> float:
        return sum((it.qty_ordered or 0) * (it.unit_cost or 0.0) for it in self.items)

    @property
    def received_total_qty(self) -> int:
        return sum(it.qty_received or 0 for it in self.items)


class PurchaseOrderItem(db.Model):
    __tablename__ = "purchase_order_items"
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("parts.id"), nullable=False)
    qty_ordered = db.Column(db.Integer, nullable=False, default=0)
    qty_received = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Float, nullable=False, default=0.0)

    product = db.relationship("Part", lazy="joined")


class StockMovement(db.Model):
    __tablename__ = "stock_movements"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("parts.id"), nullable=False)
    qty_delta = db.Column(db.Integer, nullable=False)  # +in / -out
    reason = db.Column(db.String(32), nullable=False)  # e.g., PO_RECEIVE / SALE / ADJUST
    ref_type = db.Column(db.String(32))
    ref_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    product = db.relationship("Part", lazy="joined")
