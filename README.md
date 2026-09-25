# GearShift Systems

[![CI](https://github.com/clryan86/GearShiftSystems/actions/workflows/ci.yml/badge.svg)](https://github.com/clryan86/GearShiftSystems/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-black)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-red)
![License](https://img.shields.io/badge/license-MIT-green)

A full-stack inventory, purchasing, and order-management application for an automotive parts business. GearShift Systems demonstrates practical Python web development: relational data modeling, transactional inventory workflows, server-rendered UI, purchase-order lifecycle management, CSV exports, session carts, and automated CI checks.

> **Portfolio note:** This project began as an academic software-engineering project and is maintained here as a production-minded portfolio application.

## Why this project matters

GearShift Systems models a real operational workflow rather than a collection of disconnected demos:

- Parts are tied to vendors and reorder thresholds.
- Low-stock items can be grouped into purchase orders.
- Purchase orders move through draft, approval, send, partial receipt, receipt, and cancellation states.
- Receiving inventory creates auditable stock-movement records.
- Customers can use a session-backed cart and checkout flow.
- Orders preserve SKU/name/price snapshots so historical records survive later catalog changes.
- Inventory and purchase-order data can be exported as CSV.

## Tech stack

| Layer | Technology |
| --- | --- |
| Backend | Python, Flask |
| Data | SQLite, SQLAlchemy, Flask-SQLAlchemy |
| Frontend | Jinja2, HTML5, Bootstrap 5 |
| Payments | PayPal sandbox-oriented checkout helper |
| Testing | Python `unittest` |
| CI | GitHub Actions |
| Deployment | Gunicorn, Docker |
| Architecture | Flask app factory + ORM models + blueprints |

## Core capabilities

### Inventory and vendor management
- Create, edit, search, filter, and delete inventory items.
- Track SKU, pricing, stock, shelf location, reorder threshold, and vendor.
- Manage vendor contact information.
- Export inventory to CSV.

### Reordering and purchasing
- Detect low-stock parts.
- Build vendor-grouped reorder previews.
- Persist purchase orders and line items.
- Track PO status through the purchasing lifecycle.
- Record partial and complete receipts.
- Increment stock automatically on receipt.
- Write stock-movement audit records.

### Cart and order workflow
- Session-backed shopping cart.
- Quantity updates and stock validation.
- Checkout/order persistence.
- Historical line-item snapshots.
- Order history and order-detail views.

## Architecture

```text
Browser
  |
  v
Flask routes / blueprints
  |--------------------|
  v                    v
Cart + Orders       Purchasing
  |                    |
  |--------------------|
           v
      SQLAlchemy ORM
           |
           v
         SQLite
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for design details.

## Run locally

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/clryan86/GearShiftSystems.git
cd GearShiftSystems
python -m venv .venv
```

Activate it:

**Windows PowerShell**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure the environment

Copy `.env.example` to `.env` and set a strong `SECRET_KEY` for anything beyond local development.

### 4. Start the app

```bash
python app.py
```

Then open `http://127.0.0.1:5000`.

## Run tests

```bash
python -m unittest discover -s tests -v
```

The repository also runs smoke tests automatically with GitHub Actions on pushes and pull requests.

## Docker

```bash
docker build -t gearshift-systems .
docker run --rm -p 8000:8000 -e SECRET_KEY=change-me gearshift-systems
```

Open `http://127.0.0.1:8000`.

## Environment variables

| Variable | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask session signing | development fallback |
| `DATABASE_URL` | SQLAlchemy database URL | local SQLite `app.db` |
| `PAYPAL_CLIENT_ID` | PayPal sandbox/client identifier | sandbox placeholder |
| `PAYPAL_ENV` | PayPal environment label | `sandbox` |

## Repository structure

```text
GearShiftSystems/
├── .github/workflows/ci.yml
├── docs/ARCHITECTURE.md
├── tests/test_app.py
├── Templates/
├── app.py
├── cart.py
├── models.py
├── paypal_mini.py
├── create_db.py
├── seed_data.py
├── wsgi.py
├── Dockerfile
└── requirements.txt
```

## Engineering highlights

- App-factory pattern keeps initialization centralized.
- ORM relationships model inventory, vendors, orders, purchase orders, and stock movements.
- Historical order snapshots reduce coupling between current catalog data and old orders.
- Explicit PO state transitions model a realistic purchasing workflow.
- A health endpoint supports deployment checks.
- Environment-driven secrets/database settings improve portability.
- GitHub Actions provides repeatable verification on Linux and multiple Python versions.
- Docker/Gunicorn provide a repeatable production-style runtime.

## Current scope and next improvements

The project intentionally stays small enough to understand end to end. Logical next steps include authentication/roles, CSRF protection, database migrations, PostgreSQL support, API endpoints, richer automated coverage, structured logging, and deployment telemetry.

## Author

**Christopher Ryan**  
Software Development / Python / Automation / Data & AI portfolio

I am building practical software projects that demonstrate the ability to turn business workflows into maintainable applications.

## License

MIT — see [LICENSE](LICENSE).
