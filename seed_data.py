from app import db, Vendor, Part, app

with app.app_context():
    v1 = Vendor(name="AutoPro Supply", contact_email="orders@autopro.example")
    v2 = Vendor(name="GearWorks", contact_email="sales@gearworks.example")
    db.session.add_all([v1, v2])
    db.session.flush()

    parts = [
        Part(name="Brake Pad Set", sku="BP-1001", price=39.99, stock=8, reorder_threshold=10, shelf_location="A1", vendor=v1),
        Part(name="Oil Filter", sku="OF-220", price=8.49, stock=50, reorder_threshold=20, shelf_location="B3", vendor=v1),
        Part(name="Spark Plug", sku="SP-77", price=4.99, stock=12, reorder_threshold=15, shelf_location="C2", vendor=v2),
    ]
    db.session.add_all(parts)
    db.session.commit()
    print("Seed complete.")
