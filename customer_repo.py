"""
Customer + artwork + order repository.

Persists customer profiles, uploaded logo files, and historical orders as JSON
on local disk. In production this would be Postgres/SQLite + S3 for artwork,
linked to Antera Customer Master via Antera Customer ID.

DESIGN NOTE: This module does NOT replicate Antera customer data (billing,
contacts, payment terms). It indexes by Antera Customer ID and stores ONLY
the artwork + decoration history layer that Antera doesn't natively manage.
"""
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).parent / "customer_data"
REPO_ROOT.mkdir(exist_ok=True)
CUSTOMERS_FILE = REPO_ROOT / "customers.json"


def _now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _load_customers():
    if not CUSTOMERS_FILE.exists():
        return []
    return json.loads(CUSTOMERS_FILE.read_text())


def _save_customers(customers):
    CUSTOMERS_FILE.write_text(json.dumps(customers, indent=2))


def list_customers():
    """Return all customers, sorted by name."""
    return sorted(_load_customers(), key=lambda c: c.get("display_name", "").lower())


def get_customer(customer_id):
    for c in _load_customers():
        if c["customer_id"] == customer_id:
            return c
    return None


def create_customer(display_name, antera_customer_id=None, notes=""):
    """Create a new customer record. Returns the customer dict."""
    customers = _load_customers()
    new_customer = {
        "customer_id": uuid.uuid4().hex[:12],
        "display_name": display_name.strip(),
        "antera_customer_id": (antera_customer_id or "").strip() or None,
        "notes": notes.strip(),
        "created_at": _now_iso(),
    }
    customers.append(new_customer)
    _save_customers(customers)
    (REPO_ROOT / new_customer["customer_id"] / "logos").mkdir(parents=True, exist_ok=True)
    (REPO_ROOT / new_customer["customer_id"] / "orders").mkdir(parents=True, exist_ok=True)
    return new_customer


def _customer_dir(customer_id):
    return REPO_ROOT / customer_id


def save_logo(customer_id, file_bytes, original_filename):
    """Persist an uploaded logo under this customer. Returns the logo record."""
    logo_id = uuid.uuid4().hex[:12]
    ext = Path(original_filename).suffix.lower()
    logo_dir = _customer_dir(customer_id) / "logos" / logo_id
    logo_dir.mkdir(parents=True, exist_ok=True)
    file_path = logo_dir / f"original{ext}"
    file_path.write_bytes(file_bytes)
    record = {
        "logo_id": logo_id,
        "original_filename": original_filename,
        "file_path": str(file_path),
        "ext": ext,
        "uploaded_at": _now_iso(),
    }
    (logo_dir / "meta.json").write_text(json.dumps(record, indent=2))
    return record


def list_logos(customer_id):
    """All logos for a customer, newest first."""
    logos_dir = _customer_dir(customer_id) / "logos"
    if not logos_dir.exists():
        return []
    records = []
    for logo_dir in logos_dir.iterdir():
        meta_file = logo_dir / "meta.json"
        if meta_file.exists():
            try:
                records.append(json.loads(meta_file.read_text()))
            except json.JSONDecodeError:
                continue
    return sorted(records, key=lambda r: r.get("uploaded_at", ""), reverse=True)


def get_logo_path(customer_id, logo_id):
    """Reconstruct the actual logo file path from IDs (cross-platform safe).

    Ignores any stored file_path in meta.json (those may be Windows-style
    paths that don't resolve on Linux/Streamlit Cloud). Logo files are
    always saved as `original<ext>` inside the logo's directory.
    """
    logo_dir = _customer_dir(customer_id) / "logos" / logo_id
    if not logo_dir.exists():
        return None
    # Look for original.* file (any extension)
    for f in logo_dir.glob("original.*"):
        return f
    return None


def get_logo_bytes(customer_id, logo_id):
    """Return the original logo bytes + original filename for a stored logo."""
    logo_dir = _customer_dir(customer_id) / "logos" / logo_id
    meta_file = logo_dir / "meta.json"
    if not meta_file.exists():
        return None, None
    meta = json.loads(meta_file.read_text())
    # Reconstruct path from IDs (cross-platform), not from stored file_path
    file_path = get_logo_path(customer_id, logo_id)
    if file_path is None or not file_path.exists():
        return None, None
    return file_path.read_bytes(), meta["original_filename"]


def save_order(customer_id, logo_id, order_data):
    """Persist a finalized quote/order under this customer."""
    order_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    order_record = {
        "order_id": order_id,
        "customer_id": customer_id,
        "logo_id": logo_id,
        "created_at": _now_iso(),
        **order_data,
    }
    order_path = _customer_dir(customer_id) / "orders" / f"{order_id}.json"
    order_path.parent.mkdir(parents=True, exist_ok=True)
    order_path.write_text(json.dumps(order_record, indent=2, default=str))
    return order_record


def save_expense(customer_id, expense_data):
    """Persist a receipt/expense under this customer, optionally tagged to a job number.

    In production this would also push to Antera's job costing module via API,
    crediting the expense against the specified Antera Job ID.
    """
    expense_id = datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    record = {
        "expense_id": expense_id,
        "customer_id": customer_id,
        "created_at": _now_iso(),
        **expense_data,
    }
    expenses_dir = _customer_dir(customer_id) / "expenses"
    expenses_dir.mkdir(parents=True, exist_ok=True)
    (expenses_dir / f"{expense_id}.json").write_text(json.dumps(record, indent=2, default=str))
    return record


def list_expenses(customer_id, job_number=None):
    """All expenses for a customer (optionally filtered by job number), newest first."""
    expenses_dir = _customer_dir(customer_id) / "expenses"
    if not expenses_dir.exists():
        return []
    records = []
    for f in expenses_dir.glob("*.json"):
        try:
            rec = json.loads(f.read_text())
            if job_number is None or rec.get("job_number") == job_number:
                records.append(rec)
        except json.JSONDecodeError:
            continue
    return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)


# ============================================================
# ANTERA JOBS (mocked per customer for the demo)
# In production, list_antera_jobs() would call the Antera API for the
# customer's active jobs. For the demo we maintain a local JSON per customer.
# ============================================================

def list_antera_jobs(customer_id):
    """Return mocked active Antera jobs for a customer (newest first)."""
    jobs_file = _customer_dir(customer_id) / "antera_jobs.json"
    if not jobs_file.exists():
        return []
    try:
        return sorted(json.loads(jobs_file.read_text()), key=lambda j: j.get("opened_at", ""), reverse=True)
    except json.JSONDecodeError:
        return []


def add_antera_job(customer_id, job_id, description, status="active"):
    """Add a job to the mocked Antera jobs list for this customer."""
    jobs_file = _customer_dir(customer_id) / "antera_jobs.json"
    jobs = list_antera_jobs(customer_id)
    if any(j["job_id"] == job_id for j in jobs):
        return None  # already exists
    jobs_file.parent.mkdir(parents=True, exist_ok=True)
    new_job = {
        "job_id": job_id,
        "description": description,
        "status": status,
        "opened_at": _now_iso(),
    }
    jobs.append(new_job)
    jobs_file.write_text(json.dumps(jobs, indent=2))
    return new_job


# ============================================================
# GLOBAL QUEUES (cross-customer accept buffers)
# Receipts, invoices, spec sheets, etc. land here when accepted by a user.
# In production these would push to Google Sheets / Antera. For the demo
# they live as JSON files and the Reporting module drills into them.
# ============================================================

QUEUES_ROOT = REPO_ROOT / "_queues"
QUEUES_ROOT.mkdir(exist_ok=True)

VALID_QUEUES = ("receipts", "invoices", "spec_sheets", "orders", "notes")


def append_to_queue(queue_name, record):
    """Append a record to a named queue. Returns the saved entry with an ID."""
    if queue_name not in VALID_QUEUES:
        raise ValueError(f"Unknown queue: {queue_name}")
    queue_file = QUEUES_ROOT / f"{queue_name}.json"
    entries = []
    if queue_file.exists():
        try:
            entries = json.loads(queue_file.read_text())
        except json.JSONDecodeError:
            entries = []
    entry = {
        "entry_id": uuid.uuid4().hex[:12],
        "accepted_at": _now_iso(),
        **record,
    }
    entries.append(entry)
    queue_file.write_text(json.dumps(entries, indent=2, default=str))
    return entry


def list_queue(queue_name):
    """Return all entries in a queue, newest first."""
    if queue_name not in VALID_QUEUES:
        return []
    queue_file = QUEUES_ROOT / f"{queue_name}.json"
    if not queue_file.exists():
        return []
    try:
        entries = json.loads(queue_file.read_text())
    except json.JSONDecodeError:
        return []
    return sorted(entries, key=lambda e: e.get("accepted_at", ""), reverse=True)


def queue_counts():
    """Return {queue_name: entry_count} for all known queues."""
    return {q: len(list_queue(q)) for q in VALID_QUEUES}

# ============================================================
# APPROVAL STAGE MANAGEMENT
# ============================================================

# Sports/licensed customers go through 3-party approval (team/property +
# league + sponsor). Corporate customers go through internal review only.
SPORTS_STAGES = [
    "draft", "pending_customer", "pending_league", "pending_sponsor",
    "approved", "in_production", "completed",
]
CORPORATE_STAGES = [
    "draft", "pending_customer", "pending_production_mgr",
    "approved", "in_production", "completed",
]
STAGE_LABELS = {
    "draft": "Draft",
    "pending_customer": "Pending Customer Review",
    "pending_league": "Pending League / Properties",
    "pending_sponsor": "Pending Sponsor Sign-off",
    "pending_production_mgr": "Pending Production Mgr",
    "approved": "Approved — Ready for Production",
    "in_production": "In Production",
    "completed": "Completed",
    "rejected": "Rejected / Change Requested",
}
STAGE_ICONS = {
    "draft": "📝",
    "pending_customer": "👤",
    "pending_league": "🏛️",
    "pending_sponsor": "💰",
    "pending_production_mgr": "🏭",
    "approved": "✅",
    "in_production": "⚙️",
    "completed": "📦",
    "rejected": "⚠️",
}


def get_customer_category(customer):
    """Returns 'sports' or 'corporate'. Reads from customer record (default corporate)."""
    if not customer:
        return "corporate"
    return customer.get("category", "corporate")


def get_flow_for_customer(customer):
    """Return the approval-stage list for this customer's category."""
    cat = get_customer_category(customer)
    return SPORTS_STAGES if cat == "sports" else CORPORATE_STAGES


def set_customer_category(customer_id, category):
    """Update a customer's category (sports/corporate). Persists to customers.json."""
    customers = _load_customers()
    for c in customers:
        if c["customer_id"] == customer_id:
            c["category"] = category
            _save_customers(customers)
            return c
    return None


def advance_order_stage(customer_id, order_id, actor="system", notes="", to_stage=None):
    """Advance an order to the next stage (or specific to_stage). Appends to approval_log."""
    order_path = _customer_dir(customer_id) / "orders" / f"{order_id}.json"
    if not order_path.exists():
        return None
    rec = json.loads(order_path.read_text())
    cust = get_customer(customer_id)
    flow = get_flow_for_customer(cust)
    current = rec.get("approval_stage", "draft")
    if to_stage:
        new_stage = to_stage
    else:
        try:
            idx = flow.index(current)
            new_stage = flow[idx + 1] if idx + 1 < len(flow) else current
        except ValueError:
            new_stage = flow[0]
    rec["approval_stage"] = new_stage
    rec.setdefault("approval_log", []).append({
        "at": _now_iso(),
        "actor": actor,
        "action": "advanced",
        "to_stage": new_stage,
        "from_stage": current,
        "notes": notes,
    })
    rec["stage_changed_at"] = _now_iso()
    order_path.write_text(json.dumps(rec, indent=2, default=str))
    return rec


def reject_order(customer_id, order_id, actor="system", notes=""):
    """Mark order as rejected/change-requested. Sends back to draft."""
    order_path = _customer_dir(customer_id) / "orders" / f"{order_id}.json"
    if not order_path.exists():
        return None
    rec = json.loads(order_path.read_text())
    current = rec.get("approval_stage", "draft")
    rec["approval_stage"] = "rejected"
    rec.setdefault("approval_log", []).append({
        "at": _now_iso(),
        "actor": actor,
        "action": "rejected",
        "from_stage": current,
        "notes": notes,
    })
    rec["stage_changed_at"] = _now_iso()
    order_path.write_text(json.dumps(rec, indent=2, default=str))
    return rec


def list_all_orders_with_stage():
    """Return ALL orders across all customers, with approval stage info attached.
    Used by the Approvals & Changes kanban view."""
    out = []
    for c in list_customers():
        cid = c["customer_id"]
        orders_dir = _customer_dir(cid) / "orders"
        if not orders_dir.exists():
            continue
        for f in orders_dir.glob("*.json"):
            try:
                rec = json.loads(f.read_text())
                rec["_customer"] = c
                out.append(rec)
            except json.JSONDecodeError:
                continue
    return out


def list_orders(customer_id, logo_id=None):
    """All orders for a customer (optionally filtered by logo), newest first."""
    orders_dir = _customer_dir(customer_id) / "orders"
    if not orders_dir.exists():
        return []
    records = []
    for order_file in orders_dir.glob("*.json"):
        try:
            rec = json.loads(order_file.read_text())
            if logo_id is None or rec.get("logo_id") == logo_id:
                records.append(rec)
        except json.JSONDecodeError:
            continue
    return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)
