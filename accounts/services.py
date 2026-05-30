"""Customer-related service helpers using JSON mock data (no DB)."""

from datetime import date, timedelta
import re
import logging

from core.json_data import load_json
from core.json_data import save_json
from core.exceptions import NotFoundError, ServiceError, ValidationError

logger = logging.getLogger(__name__)


def _normalize_phone(value):
    """Strip a phone number down to digits only."""
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _load_customers():
    try:
        customers = load_json("customers.json")
        # Log loaded count for debugging
        try:
            logger.debug("ACCOUNT LOOKUP: loaded customers count=%d", len(customers) if customers else 0)
        except Exception:
            pass
        return customers
    except ServiceError:
        raise


def lookup_customer_by_phone(phone):
    """Find a customer by phone number in the JSON data.

    Accepts formatted phone numbers and falls back to partial matching.
    """
    # Accept either a phone number or a numeric customer_id
    raw = (phone or "").strip()
    if not raw:
        raise ValidationError("Please provide a phone number or customer id.")

    # Normalize phone by removing non-digits
    normalized_phone = _normalize_phone(raw)

    # If the input looks like a short numeric id, allow customer_id lookup
    is_possible_cid = False
    try:
        if raw.isdigit() and 1 <= int(raw) <= 99999:
            is_possible_cid = True
    except Exception:
        is_possible_cid = False

    if not normalized_phone and not is_possible_cid:
        raise ValidationError("Please provide a valid phone number or customer id.")

    try:
        customers = _load_customers()
    except ServiceError as exc:
        raise ServiceError("Unable to access customer records.") from exc

    if not customers:
        raise NotFoundError("No customer records are available yet.")

    logger.debug("ACCOUNT LOOKUP: searching for phone=%s, normalized=%s, possible_cid=%s", raw, normalized_phone, is_possible_cid)

    # Search most-recent-first by created_at if present
    def sort_key(c):
        return c.get("created_at", "")

    for customer in sorted(customers, key=sort_key, reverse=True):
        # support customer_id lookup
        try:
            cid = customer.get("customer_id")
            if is_possible_cid and cid is not None and int(cid) == int(raw):
                logger.debug("ACCOUNT LOOKUP: matched by customer_id=%s -> %s", raw, customer.get("full_name"))
                return customer
        except Exception:
            pass

        customer_phone = _normalize_phone(customer.get("phone_number"))
        # exact match
        if customer_phone == normalized_phone and normalized_phone:
            logger.debug("ACCOUNT LOOKUP: matched by exact phone=%s -> %s", normalized_phone, customer.get("full_name"))
            return customer
        # partial match (contains)
        if normalized_phone and (normalized_phone in customer_phone or customer_phone in normalized_phone):
            logger.debug("ACCOUNT LOOKUP: matched by partial phone=%s -> %s", normalized_phone, customer.get("full_name"))
            return customer

    logger.debug("ACCOUNT LOOKUP: no match found for %s", raw)
    raise NotFoundError("I couldn't find an account for that phone number.")


def get_dashboard_customer(phone=None):
    """Return a customer dict for the dashboard view or None if not found."""
    if phone:
        fragment = _normalize_phone(phone)
        if not fragment:
            return None

        try:
            if len(fragment) < 7:
                customers = _load_customers()
                for c in customers:
                    if fragment in _normalize_phone(c.get("phone_number", "")):
                        return c
                return None
            return lookup_customer_by_phone(phone)
        except NotFoundError:
            return None

    customers = _load_customers()
    if not customers:
        return None
    return sorted(customers, key=lambda c: c.get("created_at", ""), reverse=True)[0]


def get_telconnect_account(phone):
    """Return a verified mock telecom account summary for a customer.

    The response is deterministic and derived from the customer_id so demo
    sessions are stable without a database.
    """
    customer = lookup_customer_by_phone(phone)

    plan_cycle = [
        {
            "plan_name": "TelConnect Starter",
            "balance": 245.5,
            "plan_status": "Active",
            "data_left_gb": 4.8,
            "minutes_left": 180,
            "sms_left": 120,
        },
        {
            "plan_name": "TelConnect Smart",
            "balance": 512.0,
            "plan_status": "Active",
            "data_left_gb": 11.2,
            "minutes_left": 420,
            "sms_left": 240,
        },
        {
            "plan_name": "TelConnect Plus",
            "balance": 128.75,
            "plan_status": "Active",
            "data_left_gb": 22.5,
            "minutes_left": 760,
            "sms_left": 390,
        },
    ]

    # Use customer_id when present, otherwise a numeric fallback from phone
    cid = customer.get("customer_id")
    if not cid:
        digits = re.sub(r"\D", "", customer.get("phone_number", ""))
        cid = int(digits[-2:]) if digits else 1

    profile = plan_cycle[(int(cid) - 1) % len(plan_cycle)]
    due_date = date.today() + timedelta(days=12 + ((int(cid) - 1) % 10))

    return {
        "customer_name": customer.get("full_name"),
        "account_number": customer.get("account_number"),
        "phone_number": customer.get("phone_number"),
        "verified": True,
        "plan_name": profile["plan_name"],
        "balance": round(profile["balance"], 2),
        "due_date": due_date.isoformat(),
        "plan_status": profile["plan_status"],
        "data_left_gb": profile["data_left_gb"],
        "minutes_left": profile["minutes_left"],
        "sms_left": profile["sms_left"],
        "next_bill_amount": round(profile["balance"] * 1.1, 2),
    }


def create_test_account(payload: dict):
    """Create and persist a new test customer record into data/customers.json.

    Validates required fields, ensures phone uniqueness, and generates a
    customer_id/account_number when not provided.
    """
    if not isinstance(payload, dict):
        raise ValidationError("Invalid payload for creating a customer.")

    full_name = (payload.get("full_name") or payload.get("name") or "").strip()
    phone = (payload.get("phone_number") or payload.get("phone") or "").strip()
    package = (payload.get("package_name") or payload.get("plan_name") or "").strip()
    expiry = (payload.get("expiry_date") or payload.get("expiry") or "").strip()

    if not full_name:
        raise ValidationError("Full name is required.")
    if not phone:
        raise ValidationError("Phone number is required.")
    # normalize phone
    normalized = _normalize_phone(phone)
    if not normalized:
        raise ValidationError("Please provide a valid phone number.")

    # validate expiry date (accept ISO YYYY-MM-DD or common variants)
    from datetime import datetime
    parsed_expiry = None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            parsed_expiry = datetime.strptime(expiry, fmt).date()
            break
        except Exception:
            continue
    if expiry and not parsed_expiry:
        raise ValidationError("Expiry date is not valid. Use YYYY-MM-DD.")

    try:
        customers = _load_customers() or []
    except ServiceError as exc:
        # if file does not exist, start with empty list
        customers = []

    # ensure unique phone
    for c in customers:
        if _normalize_phone(c.get("phone_number")) == normalized:
            raise ValidationError("A customer with that phone number already exists.")

    # generate customer id as max existing + 1
    max_cid = 0
    for c in customers:
        try:
            cid = int(c.get("customer_id") or 0)
            if cid > max_cid:
                max_cid = cid
        except Exception:
            continue
    new_cid = max_cid + 1

    # build record
    import time
    account_number = payload.get("account_number") or f"ACCT{int(time.time()) % 1000000:06d}"
    new_rec = {
        "customer_id": new_cid,
        "full_name": full_name,
        "phone_number": phone,
        "account_number": account_number,
        "package_name": package or "TelConnect Starter",
        "data_balance_gb": float(payload.get("data_balance_gb") or payload.get("data_gb") or 0),
        "voice_minutes": int(payload.get("voice_minutes") or 0),
        "sms_count": int(payload.get("sms_count") or 0),
        "account_balance": float(payload.get("account_balance") or payload.get("balance") or 0.0),
        "expiry_date": parsed_expiry.isoformat() if parsed_expiry else "",
        "language": payload.get("language") or "en",
        "is_active": True,
        "created_at": datetime.utcnow().isoformat(),
    }

    customers.append(new_rec)

    # persist safely
    try:
        save_json("customers.json", customers)
        logger.info("Created test customer: %s %s", new_rec.get("full_name"), new_rec.get("phone_number"))
    except Exception as exc:
        logger.exception("Failed to save new customer: %s", exc)
        raise ServiceError("Unable to persist new customer record.") from exc

    return new_rec
