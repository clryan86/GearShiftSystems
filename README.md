# GearShift Systems

GearShift Systems is an **online ordering and inventory management system** for auto parts, built as part of **IT488 – Software Product Development Using Agile**.  
It follows agile methodologies with sprint planning, reviews, retrospectives, and team collaboration.

---

## 🚀 Tech Stack
- **Backend**: Python (Flask)  
- **Database**: SQLite with SQLAlchemy ORM  
- **Frontend**: HTML5, Jinja2 Templates, Bootstrap 5 (dark theme)  
- **Payment Integration**: PayPal Sandbox (checkout workflow)  
- **Version Control**: Git + GitHub (CI-friendly)  

---

## ✨ Features
- **Parts Inventory**
  - Add, edit, delete, and view parts.
  - Track SKU, stock, price, vendor, and reorder thresholds.
  - Export inventory list as CSV.
- **Vendors**
  - Add and manage vendors with contact details.
  - Associate parts with vendors.
- **Shopping Cart**
  - Session-based cart with add, remove, update, and checkout.
  - Stock validation to prevent overselling.
- **Checkout & Orders**
  - PayPal sandbox checkout integration.
  - Orders are persisted with buyer details, line items, and totals.
  - Automatic stock deduction on checkout.
  - Order history and detail view.
- **Reorder Management**
  - Draft purchase order generator for low-stock items.
  - Preview or export purchase orders as CSV.
- **Agile Artifacts**
  - Product backlog, sprint backlog, and burndown charts tracked during development.
  - Sprint planning, reviews, and retrospectives documented.

---

## 📂 Project Structure
