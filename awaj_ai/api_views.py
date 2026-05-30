"""JSON endpoints used by the voice assistant tool layer.

These views stay thin and delegate business logic to app services.
"""

from django.views.decorators.csrf import csrf_exempt

from django.http import JsonResponse

from accounts.services import get_telconnect_account
from core.exceptions import AppError, ValidationError, NotFoundError
from core.services import lookup_package
from faq.services import search_faqs
from core.json_data import load_json
import json
from accounts.services import create_test_account
from datetime import datetime


def _tool_response(tool, message, data=None, status=200, **extra):
    payload = {
        "ok": status < 400,
        "tool": tool,
    }
    if data is not None:
        payload["data"] = data
    if extra:
        payload.update(extra)
    return JsonResponse(payload, status=status)


def _tool_error(tool, message, status=400, **extra):
    payload = {
        "ok": False,
        "tool": tool,
        "message": message,
    }
    if extra:
        payload["data"] = extra
    return JsonResponse(payload, status=status)


def check_account(request):
    """Return a customer summary for a phone-number lookup."""
    if request.method != "GET":
        return _tool_error("check_account", "Method not allowed", status=405, allowed_methods=["GET"])
    try:
        account = get_telconnect_account(request.GET.get("phone"))
    except ValidationError as exc:
        return _tool_error("check_account", str(exc), status=400)
    except NotFoundError as exc:
        return _tool_error("check_account", str(exc), status=404, phone=request.GET.get("phone"))
    except AppError as exc:
        return _tool_error("check_account", str(exc), status=500)
    except Exception:
        return _tool_error("check_account", "Unexpected server error.", status=500)

    return _tool_response(
        "check_account",
        f"I found {account['customer_name']}",
        account,
    )


def telconnect_account(request):
    """Return verified mock plan, balance, and due-date data for a caller."""
    if request.method != "GET":
        return _tool_error("get_telconnect_account", "Method not allowed", status=405, allowed_methods=["GET"])

    try:
        account = get_telconnect_account(request.GET.get("phone"))
    except ValidationError as exc:
        return _tool_error("get_telconnect_account", str(exc), status=400)
    except NotFoundError as exc:
        return _tool_error("get_telconnect_account", str(exc), status=404, phone=request.GET.get("phone"))
    except AppError as exc:
        return _tool_error("get_telconnect_account", str(exc), status=500)
    except Exception:
        return _tool_error("get_telconnect_account", "Unexpected server error.", status=500)

    return _tool_response(
        "get_telconnect_account",
        f"I verified {account['customer_name']}.",
        account,
    )


def package_details(request):
    """Return package details by id or name."""
    if request.method != "GET":
        return _tool_error("package", "Method not allowed", status=405, allowed_methods=["GET"])

    try:
        package = lookup_package(request.GET.get("id"), request.GET.get("name"))
    except ValidationError as exc:
        return _tool_error("package", str(exc), status=400)
    except NotFoundError as exc:
        return _tool_error("package", str(exc), status=404, id=request.GET.get("id"), name=request.GET.get("name"))
    except AppError as exc:
        return _tool_error("package", str(exc), status=500)
    except Exception:
        return _tool_error("package", "Unexpected server error.", status=500)

    return _tool_response(
        "package",
        f"{package.get('name')} costs {package.get('price')}",
        {
            "package_name": package.get("name"),
            "price": str(package.get("price")),
            "data_gb": package.get("data_gb"),
            "voice_minutes": package.get("voice_minutes"),
            "sms_count": package.get("sms_count"),
            "status": "active" if package.get("is_active") else "inactive",
        },
    )


def faq_search(request):
    """Search FAQs and return up to three relevant matches."""
    if request.method != "GET":
        return _tool_error("faq", "Method not allowed", status=405, allowed_methods=["GET"])

    try:
        results = search_faqs(request.GET.get("q"))
    except ValidationError as exc:
        return _tool_error("faq", str(exc), status=400)
    except NotFoundError as exc:
        return _tool_error("faq", str(exc), status=404, query=request.GET.get("q"))
    except AppError as exc:
        return _tool_error("faq", str(exc), status=500)
    except Exception:
        return _tool_error("faq", "Unexpected server error.", status=500)

    return _tool_response(
        "faq",
        f"I found {len(results)} FAQ result{'s' if len(results) != 1 else ''}.",
        {
            "query": (request.GET.get("q") or "").strip(),
            "count": len(results),
            "results": results,
        },
    )


def assist_prompts(request):
    """Serve the assistant prompt templates from data/assistprompt.json.

    This provides a stable endpoint for the frontend to fetch localized
    assistant templates (tool-first system prompt + language templates).
    """
    if request.method != "GET":
        return _tool_error("assist_prompts", "Method not allowed", status=405, allowed_methods=["GET"])

    try:
        data = load_json("assistprompt.json")
    except Exception as exc:
        return _tool_error("assist_prompts", f"Unable to load prompts: {exc}", status=500)

    return _tool_response("assist_prompts", "", data)


def session_phone(request):
    """Get, set, or clear the verified session phone stored in Django session.

    GET: return current session phone (or null)
    POST: set session phone (expects 'phone' param or JSON body)
    DELETE: clear session phone
    """
    if request.method == "GET":
        phone = request.session.get("awaj_session_phone")
        return _tool_response("session_phone", "", {"phone": phone})

    if request.method == "POST":
        # accept form-encoded or JSON body
        phone = request.POST.get("phone")
        if not phone:
            try:
                body = json.loads(request.body.decode("utf-8") or "{}")
                phone = body.get("phone")
            except Exception:
                phone = None

        if not phone:
            return _tool_error("session_phone", "Missing phone parameter.", status=400)

        try:
            # validate and fetch account to ensure phone is valid
            account = get_telconnect_account(phone)
        except ValidationError as exc:
            return _tool_error("session_phone", str(exc), status=400)
        except NotFoundError as exc:
            return _tool_error("session_phone", str(exc), status=404, phone=phone)
        except AppError as exc:
            return _tool_error("session_phone", str(exc), status=500)
        except Exception:
            return _tool_error("session_phone", "Unexpected server error.", status=500)

        # store normalized phone from the verified account
        request.session["awaj_session_phone"] = account.get("phone_number")
        request.session.modified = True
        return _tool_response("session_phone", f"Session phone set to {account.get('customer_name')}", {"phone": request.session.get("awaj_session_phone"), "customer": account})

    if request.method == "DELETE":
        request.session.pop("awaj_session_phone", None)
        request.session.modified = True
        return _tool_response("session_phone", "Session phone cleared.", {"phone": None})

    return _tool_error("session_phone", "Method not allowed", status=405, allowed_methods=["GET", "POST", "DELETE"])


def quick_questions(request):
    """Serve quick_questions.json from data/ for UI chips.

    GET: returns the JSON content of quick_questions.json
    """
    if request.method != "GET":
        return _tool_error("quick_questions", "Method not allowed", status=405, allowed_methods=["GET"])

    try:
        data = load_json("quick_questions.json")
    except Exception as exc:
        return _tool_error("quick_questions", f"Unable to load quick questions: {exc}", status=500)

    return _tool_response("quick_questions", "", data)


def demo_accounts(request):
    """Return the list of demo/test customers for UI display."""
    if request.method != "GET":
        return _tool_error("demo_accounts", "Method not allowed", status=405, allowed_methods=["GET"])
    try:
        data = load_json("customers.json")
    except Exception as exc:
        return _tool_error("demo_accounts", f"Unable to load demo accounts: {exc}", status=500)

    # Return a lightweight list for the UI
    out = []
    for c in data:
        out.append({
            "customer_id": c.get("customer_id"),
            "full_name": c.get("full_name"),
            "phone_number": c.get("phone_number"),
        })

    return _tool_response("demo_accounts", "", {"count": len(out), "accounts": out})


def create_test_account_view(request):
    """API endpoint to create a new test customer (appends to data/customers.json)."""
    if request.method != "POST":
        return _tool_error("create_test_account", "Method not allowed", status=405, allowed_methods=["POST"])

    # accept JSON body or form data
    body = {}
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        body = request.POST.dict() if request.POST else {}

    try:
        created = create_test_account(body)
    except ValidationError as exc:
        return _tool_error("create_test_account", str(exc), status=400)
    except Exception:
        # create_test_account can raise ServiceError/ValidationError; keep response safe for reviewers
        return _tool_error("create_test_account", "Failed to create test account.", status=500)

    return _tool_response("create_test_account", "Test account created.", {"customer": created})


def generate_sample_customer(request):
    """Return a non-persistent sample customer payload for autofill.

    GET: returns a pre-filled sample customer (does not save).
    """
    if request.method != "GET":
        return _tool_error("generate_sample_customer", "Method not allowed", status=405, allowed_methods=["GET"])

    import random
    sample_phone = f"98{random.randint(10000000, 99999999)}"
    sample = {
        "full_name": "Demo User",
        "phone_number": sample_phone,
        "package_name": "TelConnect Starter",
        "data_balance_gb": 5,
        "voice_minutes": 100,
        "sms_count": 50,
        "account_balance": 100.0,
        "expiry_date": (datetime.today().date()).isoformat(),
        "language": "en",
    }
    return _tool_response("generate_sample_customer", "", {"sample": sample})


def delete_code_map(request):
    """Delete the generated code-map SVG from the static/docs folder.

    POST or DELETE allowed. Returns 200 on success or 4xx/5xx on error.
    """
    if request.method not in ("POST", "DELETE"):
        return _tool_error("delete_code_map", "Method not allowed", status=405, allowed_methods=["POST", "DELETE"])

    from pathlib import Path
    from django.conf import settings

    path = Path(settings.BASE_DIR) / "static" / "docs" / "code-map.svg"
    try:
        if not path.exists():
            return _tool_error("delete_code_map", "Code map file not found.", status=404)
        path.unlink()
    except PermissionError as exc:
        return _tool_error("delete_code_map", "Permission denied when deleting code map.", status=500)
    except Exception as exc:
        return _tool_error("delete_code_map", f"Unable to delete code map: {exc}", status=500)

    return _tool_response("delete_code_map", "Code map deleted.")


@csrf_exempt
def intent_log(request):
    """Receive intent logs from the client for debugging/analytics.

    Expects JSON POST with fields: message, intent, confidence, route, faq (optional), support_state (optional), account (optional)
    """
    if request.method != "POST":
        return _tool_error("intent_log", "Method not allowed", status=405, allowed_methods=["POST"])

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        payload = {}

    try:
        logger = logging.getLogger(__name__)
        logger.info("INTENT LOG: message=%s intent=%s confidence=%.3f route=%s faq=%s support_state=%s account=%s",
                    payload.get("message"), payload.get("intent"), float(payload.get("confidence") or 0.0),
                    payload.get("route"), payload.get("faq"), payload.get("support_state"), payload.get("account"))
    except Exception:
        pass

    return _tool_response("intent_log", "logged")