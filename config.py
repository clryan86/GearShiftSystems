import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# SQLite dev DB in project root
SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Dev settings
DEBUG = True
TEMPLATES_AUTO_RELOAD = True

# Demo/dev secret (fine for the course)
SECRET_KEY = "dev-secret-key-change-later"
