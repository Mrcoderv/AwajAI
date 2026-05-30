"""Shared core service helpers using JSON files for package data."""

import datetime
from functools import lru_cache
from core.json_data import load_json
from core.exceptions import NotFoundError, ServiceError, ValidationError


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())

# ─── Pre-loaded FAQ knowledge base ───────────────────────────────────────────
# Topic-keyed map built at module-load time for O(1) lookup in lookup_faq().
_FAQ_KB: dict = {
    "change_plan": (
        "To change your TelConnect plan:\n"
        "1. Dial *100# → Select 'Change Plan'\n"
        "2. Visit telconnect.com.np → My Account → Change Plan\n"
        "3. Use the ConnectPay app → Plans section\n"
        "4. Visit any TelConnect store with your ID"
    ),
    "activate_roaming": (
        "To activate international roaming:\n"
        "1. Dial *131# → Select 'Roaming Services' → Activate\n"
        "2. SMS 'ROAM ON' to 1415\n"
        "3. Visit telconnect.com.np/roaming\n"
        "⚠️ Activate BEFORE you travel. Charges vary by country."
    ),
    "recharge": (
        "Ways to recharge your TelConnect account:\n"
        "1. eSewa / Khalti / IME Pay (instant, 24/7)\n"
        "2. Scratch recharge cards (any retailer)\n"
        "3. Online banking / ConnectPay App\n"
        "4. Dial *100# → Recharge option\n"
        "5. Visit any TelConnect store"
    ),
    "data_rollover": (
        "Data rollover policy:\n"
        "✅ Smart, Pro, Elite plans → Data rolls over automatically\n"
        "❌ Starter plan → No rollover, unused data expires\n"
        "📌 Rolled-over data valid for 1 billing cycle only"
    ),
    "low_balance": (
        "When your balance is low:\n"
        "- Below Rs. 10 → Calls & SMS restricted\n"
        "- Below Rs. 5  → Mobile data paused\n"
        "- Rs. 0        → Only emergency calls (100, 101, 102)\n"
        "💡 Recharge instantly via eSewa, Khalti, or *100#"
    ),
    "check_data": (
        "To check your data & balance:\n"
        "- Dial *123# (free)\n"
        "- Ask me: 'Check my balance' with your number\n"
        "- ConnectPay App → Dashboard\n"
        "- SMS 'BAL' to 1415"
    ),
    "latest_packages": (
        "TelConnect Current Plans (2026):\n"
        "| Plan    | Data      | Minutes   | SMS       | Price      |\n"
        "| Starter | 5 GB      | 200 min   | 100 SMS   | Rs. 199    |\n"
        "| Smart   | 15 GB     | 500 min   | 300 SMS   | Rs. 499    |\n"
        "| Pro     | 40 GB     | Unlimited | Unlimited | Rs. 999    |\n"
        "| Elite   | Unlimited | Unlimited | Unlimited | Rs. 1,799  |"
    ),
    "new_sim": (
        "To activate a new SIM:\n"
        "1. Visit any TelConnect store\n"
        "2. Bring valid government ID (citizenship/passport)\n"
        "3. Complete KYC biometric verification\n"
        "4. Choose your plan\n"
        "✅ SIM activated within 2 hours"
    ),
    "payment_methods": (
        "TelConnect accepts:\n"
        "- eSewa, Khalti, IME Pay, ConnectPay\n"
        "- Debit/Credit cards (Visa, Mastercard)\n"
        "- Net banking\n"
        "- Cash at TelConnect stores & authorized retailers"
    ),
}

# ─── Pre-loaded Troubleshoot knowledge base ───────────────────────────────────
_TROUBLESHOOT_KB: dict = {
    "data": (
        "Internet not working? Try these steps:\n"
        "1. Toggle Airplane Mode ON → 10 sec → OFF\n"
        "2. Restart your device\n"
        "3. Check APN: Name: TelConnect | APN: telconnect.com.np\n"
        "4. Confirm active data balance: Dial *123#\n"
        "5. Still not working? Call 1600 (free)"
    ),
    "slow": (
        "Data slow? Try these steps:\n"
        "1. Move to an open area\n"
        "2. Toggle Airplane Mode ON/OFF\n"
        "3. Restart your device\n"
        "4. Check APN: telconnect.com.np\n"
        "5. Persistent? Call 1600"
    ),
    "call": (
        "Cannot make calls? Try:\n"
        "1. Check balance is above Rs. 10\n"
        "2. Restart device\n"
        "3. Try a different location\n"
        "4. Check ISD/STD calling is enabled (*100#)\n"
        "5. Call 1600 for network support"
    ),
    "signal": (
        "No signal? Try:\n"
        "1. Move to an open area\n"
        "2. Toggle Airplane Mode ON/OFF\n"
        "3. Restart device\n"
        "4. Check coverage: telconnect.com.np/coverage\n"
        "5. Persistent? Call 1600"
    ),
    "sms": (
        "SMS not sending? Try:\n"
        "1. Check SMS balance (*123#)\n"
        "2. Ensure correct number format (+977XXXXXXXXXX)\n"
        "3. Restart device\n"
        "4. Clear SMS app cache\n"
        "5. Contact: 1600"
    ),
}


def lookup_package(package_id=None, name=None):
    """Look up a package by numeric id or case-insensitive name from JSON.

    Returns a package dict if found.
    """
    if not package_id and not name:
        raise ValidationError("Please provide a package id or name.")

    try:
        packages = load_json("packages.json")
    except ServiceError as exc:
        raise

    if package_id:
        if not str(package_id).strip().isdigit():
            raise ValidationError("Package id must be a valid number.")
        for pkg in packages:
            if int(pkg.get("id")) == int(package_id):
                return pkg

    if name:
        lookup = (name or "").strip().lower()
        for pkg in packages:
            if (pkg.get("name") or "").strip().lower() == lookup:
                return pkg

    raise NotFoundError("I couldn't find that package.")


def lookup_balance(phone: str) -> dict:
    """Return balance and usage data for the given phone number.

    Reads from customers.json if available; falls back to safe defaults.
    In a real deployment this would query a live billing API.
    """
    normalized_phone = _normalize_phone(phone)
    if not (len(normalized_phone) == 10 and normalized_phone.startswith(("97", "98"))):
        raise ValidationError("Invalid Nepal phone number.")
    # Try to find the account in customers.json for realistic data
    try:
        customers = load_json("customers.json")
        for c in customers:
            if _normalize_phone(c.get("phone_number")) == normalized_phone:
                today = datetime.date.today()
                return {
                    "balance": c.get("account_balance", 100.0),
                    "due_date": c.get("expiry_date", (today + datetime.timedelta(days=7)).isoformat()),
                    "data_left": c.get("data_balance_gb", 5),
                    "minutes_left": c.get("voice_minutes", 200),
                    "sms_left": c.get("sms_count", 100),
                }
    except Exception:
        pass
    raise NotFoundError("No account found for that number.")


def lookup_faq(topic: str) -> str:
    """Return the exact FAQ answer for a topic key.

    Uses the pre-loaded _FAQ_KB dict for O(1) lookup (no file I/O).
    Falls back to a fuzzy search in faqs.json if topic is not in KB.
    """
    topic_key = topic.strip().lower()
    # Direct hit
    if topic_key in _FAQ_KB:
        return _FAQ_KB[topic_key]
    # Fuzzy fallback: search faqs.json by keyword match
    try:
        faqs = load_json("faqs.json")
        for faq in faqs:
            if faq.get("is_published") and topic_key in (faq.get("question") or "").lower():
                return faq["answer"]
    except Exception:
        pass
    raise NotFoundError(f"No FAQ found for topic: {topic}")


def troubleshoot_issue(issue_type: str) -> str:
    """Return troubleshooting steps for a known issue type.

    Uses the pre-loaded _TROUBLESHOOT_KB dict for O(1) lookup.
    """
    key = issue_type.strip().lower()
    if key in _TROUBLESHOOT_KB:
        return _TROUBLESHOOT_KB[key]
    raise NotFoundError(f"No troubleshooting guide found for: {issue_type}")
