import os
import tempfile
import unittest

from app import create_app
from models import (
    Order,
    Part,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Vendor,
    db,
)


class GearShiftWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_dir.name, "workflow-test.db")
        os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
        os.environ["SECRET_KEY"] = "workflow-test-secret"

        self.app = create_app()
        self.app.config.update(TESTING=True)

        with self.app.app_context():
            db.create_all()

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("SECRET_KEY", None)
        self.temp_dir.cleanup()

    def test_cart_checkout_creates_order_and_decrements_stock(self):
        with self.app.app_context():
            part = Part(
                name="Performance Air Filter",
                sku="AIR-100",
                price=25.0,
                stock=5,
                reorder_threshold=1,
            )
            db.session.add(part)
            db.session.commit()
            part_id = part.id

        with self.client.session_transaction() as session:
            session["cart"] = {str(part_id): 2}

        response = self.client.post(
            "/cart/checkout",
            data={"buyer_name": "Test Buyer", "buyer_email": "buyer@example.com"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            saved_part = db.session.get(Part, part_id)
            order = Order.query.one()

            self.assertEqual(saved_part.stock, 3)
            self.assertEqual(order.status, "paid")
            self.assertEqual(order.item_count, 2)
            self.assertAlmostEqual(order.total_amount, 50.0)
            self.assertEqual(order.items[0].sku_snapshot, "AIR-100")

    def test_purchase_order_receipt_updates_inventory_and_audit_log(self):
        with self.app.app_context():
            vendor = Vendor(name="Acme Parts", contact_email="parts@example.com")
            part = Part(
                name="Brake Rotor",
                sku="ROTOR-200",
                price=80.0,
                stock=1,
                reorder_threshold=3,
                vendor=vendor,
            )
            po = PurchaseOrder(vendor=vendor, status="SENT")
            line = PurchaseOrderItem(
                po=po,
                product=part,
                qty_ordered=4,
                qty_received=0,
                unit_cost=80.0,
            )
            db.session.add_all([vendor, part, po, line])
            db.session.commit()

            po_id = po.id
            line_id = line.id
            part_id = part.id

        response = self.client.post(
            f"/pos/{po_id}/receive",
            data={f"receive_{line_id}": "4"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            saved_po = db.session.get(PurchaseOrder, po_id)
            saved_line = db.session.get(PurchaseOrderItem, line_id)
            saved_part = db.session.get(Part, part_id)
            movement = StockMovement.query.one()

            self.assertEqual(saved_line.qty_received, 4)
            self.assertEqual(saved_part.stock, 5)
            self.assertEqual(saved_po.status, "RECEIVED")
            self.assertEqual(movement.qty_delta, 4)
            self.assertEqual(movement.reason, "PO_RECEIVE")
            self.assertEqual(movement.ref_id, po_id)


if __name__ == "__main__":
    unittest.main()
