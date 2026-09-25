import os
import tempfile
import unittest

from app import create_app
from models import Part, db


class GearShiftSmokeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_dir.name, "test.db")
        os.environ["DATABASE_URL"] = f"sqlite:///{database_path}"
        os.environ["SECRET_KEY"] = "test-secret"

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

    def test_health_endpoint(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"ok": True})

    def test_home_page_renders_on_linux_case_sensitive_filesystem(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_inventory_model_round_trip(self):
        with self.app.app_context():
            part = Part(
                name="Test Brake Pad",
                sku="TEST-BRAKE-001",
                price=49.99,
                stock=2,
                reorder_threshold=5,
            )
            db.session.add(part)
            db.session.commit()

            saved = Part.query.filter_by(sku="TEST-BRAKE-001").one()
            self.assertTrue(saved.is_low_stock())
            self.assertEqual(saved.stock, 2)


if __name__ == "__main__":
    unittest.main()
