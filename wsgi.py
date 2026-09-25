from app import _sqlite_autopatch, create_app
from models import db

app = create_app()

with app.app_context():
    db.create_all()
    _sqlite_autopatch(db.engine)
