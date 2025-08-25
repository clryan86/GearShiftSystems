from flask import Flask
import config
from models import db, Vendor, Part

def create_app():
    app = Flask(__name__)
    app.config.from_object("config")
    db.init_app(app)
    return app

def seed_sample_data():
    # Vendors
    acme = Vendor(name="ACME Auto Parts", contact_email="sales@acme.example", phone="555-1000")
    turbo = Vendor(name="Turbo Supply Co.", contact_email="orders@turbo.example", phone="555-2000")

    # Parts (some purposely low to trigger alerts)
    parts = [
        Part(name="Brake Pad Set", sku="BP-100", price=39.99, stock=3,  reorder_threshold=5, shelf_location="A1", vendor=acme),
        Part(name="Oil Filter",    sku="OF-200", price=9.49,  stock=12, reorder_threshold=10, shelf_location="A3", vendor=acme),
        Part(name="Air Filter",    sku="AF-300", price=14.99, stock=2,  reorder_threshold=6, shelf_location="B2", vendor=turbo),
        Part(name="Spark Plug",    sku="SP-400", price=6.50,  stock=20, reorder_threshold=8, shelf_location="C4", vendor=turbo),
    ]
    for p in parts:
        db.session.add(p)

def main():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        seed_sample_data()
        db.session.commit()
        print("✅ Database created and seeded with sample data.")

if __name__ == "__main__":
    main()
