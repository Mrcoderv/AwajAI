"""Awaj AI — Central Intent Engine (v2.0)

Single entry-point for all conversational requests.
Handles: intent detection · phone validation · session cache · tool dispatch.
"""

import json
import logging
from functools import lru_cache
from typing import Any, Dict, Optional

from django.http import JsonResponse

from accounts.services import get_telconnect_account
from core.services import (
    lookup_balance,
    lookup_faq,
    lookup_package,
    troubleshoot_issue,
)
from core.exceptions import NotFoundError, ValidationError
from support.services import create_support_ticket, format_ticket_confirmation, get_ticket_details

logger = logging.getLogger(__name__)

# ─── In-memory result cache (phone:tool → result) ────────────────────────────
_SESSION_CACHE: Dict[str, Any] = {}


def _cache_key(phone: str, tool: str) -> str:
    return f"{phone}:{tool}"


def cache_result(phone: str, tool: str, result: Any) -> None:
    _SESSION_CACHE[_cache_key(phone, tool)] = result


def get_cached_result(phone: str, tool: str) -> Optional[Any]:
    return _SESSION_CACHE.get(_cache_key(phone, tool))


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def _normalize_message(message: str) -> str:
    return (message or "").strip()


def _extract_phone_candidate(message: str) -> str:
    candidate = _normalize_phone(message)
    if len(candidate) == 10 and candidate.startswith(("97", "98")):
        return candidate
    return ""


def _looks_like_greeting(message: str) -> bool:
    lowered = message.lower().strip()
    return lowered in {"hi", "hello", "hey", "namaste", "namaskar", "नमस्ते", "hello there"}


def _looks_like_thanks(message: str) -> bool:
    lowered = message.lower().strip()
    return lowered in {"thanks", "thank you", "thx", "dhanyabad", "धन्यवाद", "dhanayabad"}


def _looks_out_of_scope(message: str) -> bool:
    lowered = message.lower().strip()
    telecom_terms = (
        "balance",
        "package",
        "plan",
        "expiry",
        "data",
        "internet",
        "network",
        "signal",
        "faq",
        "support",
        "ticket",
        "roam",
        "recharge",
        "sim",
        "call",
        "sms",
        "billing",
        "phone",
    )
    if any(term in lowered for term in telecom_terms):
        return False
    return bool(lowered) and len(lowered.split()) <= 4


def _conversation_state(request) -> Dict[str, Any]:
    state = request.session.get("awaj_conversation_state") or {}
    if not isinstance(state, dict):
        state = {}
    state.setdefault("flow", None)
    state.setdefault("support_step", None)
    state.setdefault("last_support_issue", None)
    state.setdefault("last_ticket_id", None)
    state.setdefault("language", None)
    return state


def _save_conversation_state(request, state: Dict[str, Any]) -> None:
    request.session["awaj_conversation_state"] = state
    if hasattr(request.session, "modified"):
        request.session.modified = True


def _support_issue_from_message(message: str) -> str:
    lowered = message.lower()
    if any(term in lowered for term in ["network", "internet", "signal", "data", "slow"]):
        return "Network connectivity"
    if "call" in lowered:
        return "Call service issue"
    if "sms" in lowered or "message" in lowered:
        return "SMS delivery issue"
    return "Network connectivity"


def _greeting_response(message: str) -> JsonResponse:
    if any(ch in message for ch in "नमस्ते"):
        return _ok(
            "engine",
            "Greeting received.",
            {
                "prompt": "नमस्ते! म AwajAI हुँ। म account information, packages, internet issues, र telecom FAQs मा मद्दत गर्न सक्छु। म तपाईंलाई कसरी सहयोग गरूँ?",
            },
        )
    return _ok(
        "engine",
        "Greeting received.",
        {
            "prompt": "Hello! I'm AwajAI. I can help with account information, packages, internet issues, and telecom FAQs. How can I assist you today?",
        },
    )


def _out_of_scope_response(message: str) -> JsonResponse:
    if any(ch in message for ch in "ँंहैछ"):
        return _ok(
            "engine",
            "Out of scope request.",
            {"prompt": "म telecom support र account assistance मा मद्दत गर्छु। कृपया telecom सम्बन्धी प्रश्न सोध्नुहोस्।"},
        )
    return _ok(
        "engine",
        "Out of scope request.",
        {"prompt": "I specialize in telecom support and account assistance. Could you ask a telecom-related question?"},
    )


# ─── Intent detection ─────────────────────────────────────────────────────────
# Priority order: ACCOUNT > FAQ > TROUBLESHOOT > ESCALATION > UNKNOWN
@lru_cache(maxsize=256)
def detect_intent(message: str) -> str:
    """Keyword-based intent detection with lru_cache for zero-cost repeats."""
    t = message.lower()

    # ── FAQ intents checked BEFORE generic account keywords ──
    # (avoids "change plan" triggering CHECK_PACKAGE)
    if "change" in t and ("plan" in t or "package" in t):
        return "FAQ_CHANGE_PLAN"
    if "roam" in t:
        return "FAQ_ACTIVATE_ROAMING"
    if "recharge" in t or "top up" in t or "top-up" in t or "रिचार्ज" in t:
        return "FAQ_RECHARGE"
    if ("roll" in t and "data" in t) or "rollover" in t:
        return "FAQ_DATA_ROLLOVER"
    if "low" in t and "balance" in t:
        return "FAQ_LOW_BALANCE"
    if "latest" in t and ("plan" in t or "package" in t):
        return "FAQ_LATEST_PACKAGES"
    if "new sim" in t or "activate sim" in t or "new connection" in t:
        return "FAQ_NEW_SIM"
    if "payment" in t or "how to pay" in t or "pay bill" in t:
        return "FAQ_PAYMENT_METHODS"

    # ── Account intents ──
    if any(w in t for w in ["balance", "ब्यालेन्स", "बाँकी", "due date", "expire", "expiry"]):
        return "CHECK_BALANCE"
    if any(w in t for w in ["package", "plan", "प्याकेज", "प्लान", "my plan", "my package"]):
        return "CHECK_PACKAGE"
    if "check account" in t or ("account" in t and "phone" in t):
        return "VERIFY_ACCOUNT"
    if any(w in t for w in ["usage", "remaining", "how much left"]):
        return "CHECK_BALANCE"

    # ── Troubleshoot intents ──
    if "slow" in t and ("data" in t or "internet" in t):
        return "TRBL_SLOW"
    if any(w in t for w in ["internet not working", "no data", "data not working", "डाटा छैन"]):
        return "TRBL_DATA"
    if "internet" in t or ("data" in t and "not" in t):
        return "TRBL_DATA"
    if any(w in t for w in ["cannot call", "can't call", "call not working", "call isn't working",
                              "कल हुँदैन", "calls not", "can not call", "make a call"]):
        return "TRBL_CALL"
    if "no signal" in t or "no network" in t or "नेटवर्क छैन" in t:
        return "TRBL_SIGNAL"
    if "sms not" in t or "message failed" in t:
        return "TRBL_SMS"
    if "network" in t:
        return "TRBL_SIGNAL"

    # ── Escalation intents ──
    if any(w in t for w in ["talk to human", "human agent", "real person", "operator", "live agent"]):
        return "ESCALATE_HUMAN"
    if any(w in t for w in ["complaint", "file complaint", "unhappy"]):
        return "ESCALATE_COMPLAINT"
    if "refund" in t or "money back" in t or "wrong charge" in t:
        return "ESCALATE_REFUND"

    return "UNKNOWN"


# ─── FAQ intent → KB key mapping ─────────────────────────────────────────────
_FAQ_KEY_MAP: Dict[str, str] = {
    "faq_change_plan":        "change_plan",
    "faq_activate_roaming":   "activate_roaming",
    "faq_recharge":           "recharge",
    "faq_data_rollover":      "data_rollover",
    "faq_low_balance":        "low_balance",
    "faq_check_data":         "check_data",
    "faq_latest_packages":    "latest_packages",
    "faq_new_sim":            "new_sim",
    "faq_payment_methods":    "payment_methods",
}

# ─── Troubleshoot intent → KB key mapping ────────────────────────────────────
_TRBL_KEY_MAP: Dict[str, str] = {
    "trbl_data":      "data",
    "trbl_slow":      "slow",
    "trbl_slow_data": "slow",
    "trbl_call":      "call",
    "trbl_signal":    "signal",
    "trbl_sms":       "sms",
}


# ─── Response helpers ─────────────────────────────────────────────────────────
def _ok(tool: str, message: str, data: Any = None, **extra) -> JsonResponse:
    payload: Dict[str, Any] = {"ok": True, "tool": tool, "message": message}
    if data is not None:
        payload["data"] = data
    payload.update(extra)
    return JsonResponse(payload)


def _err(tool: str, message: str, status: int = 400, **extra) -> JsonResponse:
    payload: Dict[str, Any] = {"ok": False, "tool": tool, "message": message}
    payload.update(extra)
    return JsonResponse(payload, status=status)


# ─── Phone validation ─────────────────────────────────────────────────────────
def _valid_phone(phone: str) -> bool:
    normalized = _normalize_phone(phone)
    return bool(normalized) and len(normalized) == 10 and normalized.startswith(("97", "98"))


# ─── Main entry point ─────────────────────────────────────────────────────────
def process_message(request) -> JsonResponse:
    """Unified handler for all chat/intent requests.

    GET  /api/chat?msg=...&phone=...
    POST /api/chat  {"msg": "...", "phone": "..."}
    """
    if request.method == "GET":
        msg = (request.GET.get("msg") or "").strip()
        phone = (request.GET.get("phone") or "").strip()
    else:
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = {}
        msg = (body.get("msg") or "").strip()
        phone = (body.get("phone") or "").strip()

    if not msg:
        return _err("engine", "Message parameter 'msg' is required.", status=400)

    state = _conversation_state(request)
    normalized_msg = _normalize_message(msg)
    lowered = normalized_msg.lower()
    normalized_phone = _normalize_phone(phone) or _extract_phone_candidate(normalized_msg)

    if any(term in lowered for term in ["expiry", "expire", "due date", "when does my plan expire", "myaad", "म्याद"]):
        intent = "CHECK_EXPIRY"
    elif normalized_phone and len(normalized_phone) == 10 and normalized_phone.startswith(("97", "98")) and not any(term in lowered for term in ["balance", "package", "plan", "expiry", "expire"]):
        intent = "VERIFY_ACCOUNT"
    else:
        intent = detect_intent(msg)

    if _looks_like_greeting(normalized_msg) and not any([state.get("last_ticket_id"), state.get("support_step"), normalized_phone]):
        logger.info("intent=greeting phone=%s msg=%r", phone or "none", msg[:80])
        return _greeting_response(normalized_msg)

    if _looks_like_thanks(normalized_msg) and state.get("last_ticket_id"):
        try:
            ticket = get_ticket_details(ticket_id=state.get("last_ticket_id"))
            return _ok(
                "support_ticket",
                "Ticket status retrieved.",
                {
                    "ticket_id": ticket.get("ticket_id"),
                    "issue": ticket.get("issue"),
                    "status": ticket.get("status"),
                    "prompt": f"You're welcome. Your ticket {ticket.get('ticket_id')} is currently {ticket.get('status', 'Open').lower()}.",
                },
            )
        except NotFoundError:
            pass

    if any(term in lowered for term in ["check ticket", "ticket details", "my ticket", "support ticket status"]):
        try:
            ticket = get_ticket_details(ticket_id=state.get("last_ticket_id"), phone=normalized_phone or phone)
            state["flow"] = "support"
            state["support_step"] = "ticket_created"
            state["last_ticket_id"] = ticket.get("ticket_id")
            _save_conversation_state(request, state)
            return _ok(
                "support_ticket",
                "Ticket details retrieved.",
                {
                    "ticket_id": ticket.get("ticket_id"),
                    "issue": ticket.get("issue"),
                    "status": ticket.get("status"),
                    "created_at": ticket.get("created_at"),
                    "phone_number": ticket.get("phone_number"),
                    "prompt": format_ticket_confirmation(ticket),
                },
            )
        except NotFoundError:
            return _ok(
                "support_ticket",
                "No ticket found.",
                {"prompt": "I couldn’t find an open ticket yet. Would you like me to create one?"},
            )

    if any(term in lowered for term in ["create support ticket", "open a ticket", "create ticket", "raise a ticket"]):
        issue = state.get("last_support_issue") or _support_issue_from_message(normalized_msg)
        try:
            ticket = create_support_ticket(
                issue=issue,
                phone=normalized_phone or phone,
                customer_name=(state.get("customer_name") or ""),
                conversation_state=state,
            )
            state["flow"] = "support"
            state["support_step"] = "ticket_created"
            state["last_ticket_id"] = ticket.get("ticket_id")
            state["last_support_issue"] = ticket.get("issue")
            _save_conversation_state(request, state)
            return _ok(
                "support_ticket",
                "Support ticket created successfully.",
                {
                    "ticket_id": ticket.get("ticket_id"),
                    "issue": ticket.get("issue"),
                    "status": ticket.get("status"),
                    "phone_number": ticket.get("phone_number"),
                    "prompt": format_ticket_confirmation(ticket),
                },
            )
        except ValidationError as exc:
            return _ok("support_ticket", str(exc), {"prompt": str(exc)})
        except Exception as exc:
            logger.exception("support ticket creation failed: %s", exc)
            return _ok(
                "support_ticket",
                "Could not create ticket right now.",
                {"prompt": "I’m having trouble creating the ticket right now. Please try again in a moment."},
            )

    if any(term in lowered for term in ["network issue", "network issues", "internet issue", "internet not working", "no network", "no signal", "signal weak", "data not working"]):
        issue = _support_issue_from_message(normalized_msg)
        state["flow"] = "support"
        state["support_step"] = "troubleshooting"
        state["last_support_issue"] = issue
        _save_conversation_state(request, state)
        try:
            steps = troubleshoot_issue("data" if "internet" in lowered or "data" in lowered else "signal")
            return _ok(
                "troubleshoot",
                "Troubleshooting steps provided.",
                {
                    "issue": issue,
                    "steps": steps,
                    "prompt": steps,
                },
            )
        except NotFoundError:
            return _ok(
                "troubleshoot",
                "Troubleshooting steps unavailable.",
                {"prompt": "I can still help. Please try restarting your phone and moving to an open area."},
            )

    if any(term in lowered for term in ["still not working", "not working", "no change", "same issue", "issue remains"]):
        state["flow"] = "support"
        state["support_step"] = "escalation_offer"
        _save_conversation_state(request, state)
        return _ok(
            "escalate",
            "Escalation offered.",
            {
                "prompt": "I can create a support ticket or connect you to a live agent. Which would you prefer?",
                "next_step": "create support ticket",
            },
        )

    if any(term in lowered for term in ["customer support", "contact support", "talk to someone", "live agent"]):
        state["flow"] = "support"
        state["support_step"] = state.get("support_step") or "escalation_offer"
        _save_conversation_state(request, state)
        return _ok(
            "escalate",
            "Support options provided.",
            {
                "prompt": "I can create a support ticket or connect you to customer support. If you'd like, say 'create support ticket'.",
                "hotline": "1600",
                "chat": "telconnect.com.np/support",
            },
        )

    logger.info("intent=%s phone=%s msg=%r", intent, phone or "none", msg[:80])

    # ── ACCOUNT intents ────────────────────────────────────────────────────────
    if intent in {"CHECK_BALANCE", "CHECK_PACKAGE", "CHECK_EXPIRY", "VERIFY_ACCOUNT"}:
        # Phone required — return friendly 200 message instead of hard 400
        phone_to_use = normalized_phone or phone
        if not phone_to_use:
            return _ok("engine", "Phone number required.",
                       {"prompt": "Could you please share your registered phone number?"})
        if not _valid_phone(phone_to_use):
            return _ok("engine", "Invalid phone number.",
                       {"prompt": "That doesn't look valid. Please enter a 10-digit Nepal number starting with 97 or 98."})

        # Cache hit
        cached = get_cached_result(phone_to_use, intent)
        if cached:
            return _ok(intent.lower(), "cached result", cached)

        if intent == "CHECK_BALANCE":
            try:
                data = lookup_balance(phone_to_use)
                cache_result(phone_to_use, intent, data)
                balance_message = f"Your current balance is Rs. {float(data.get('balance', 0)):.2f}."
                return _ok("check_balance", "Balance retrieved.", {"balance": data.get("balance"), "prompt": balance_message})
            except NotFoundError as exc:
                return _ok("check_balance", str(exc),
                           {"prompt": "No account found for that number. Please double-check or call 1600."})
            except Exception as exc:
                logger.exception("lookup_balance failed: %s", exc)
                return _ok("check_balance", "Could not fetch balance right now.",
                           {"prompt": "I'm having trouble fetching your balance. Please try again or call 1600."})

        if intent == "CHECK_PACKAGE":
            try:
                data = _lookup_package_for_phone(phone_to_use)
                cache_result(phone_to_use, intent, data)
                package = data.get("package") or {}
                return _ok(
                    "check_package",
                    "Package retrieved.",
                    {
                        "plan_name": data.get("plan_name"),
                        "package_name": package.get("name") or data.get("plan_name"),
                        "data_gb": package.get("data_gb"),
                        "voice_minutes": package.get("voice_minutes"),
                        "sms_count": package.get("sms_count"),
                        "prompt": f"Your current package is {data.get('plan_name') or package.get('name')}.",
                    },
                )
            except NotFoundError as exc:
                return _ok("check_package", str(exc),
                           {"prompt": "No account or package found. Please check your number."})
            except Exception as exc:
                logger.exception("check_package failed: %s", exc)
                return _ok("check_package", "Could not fetch package right now.",
                           {"prompt": "I'm having trouble fetching your package. Please try again or call 1600."})

        if intent == "CHECK_EXPIRY":
            try:
                data = get_telconnect_account(phone_to_use)
                cache_result(phone_to_use, intent, data)
                expiry_message = f"Your current expiry date is {data.get('due_date')}."
                return _ok("check_expiry", "Expiry retrieved.", {"due_date": data.get("due_date"), "prompt": expiry_message})
            except NotFoundError as exc:
                return _ok("check_expiry", str(exc), {"prompt": "No account found for that number. Please double-check or call 1600."})
            except Exception as exc:
                logger.exception("check_expiry failed: %s", exc)
                return _ok("check_expiry", "Could not fetch expiry right now.", {"prompt": "I'm having trouble fetching your expiry date. Please try again or call 1600."})

        if intent == "VERIFY_ACCOUNT":
            try:
                data = get_telconnect_account(phone_to_use)
                cache_result(phone_to_use, intent, data)
                state["customer_name"] = data.get("customer_name")
                _save_conversation_state(request, state)
                return _ok("check_account", "Account verified.", data)
            except (NotFoundError, ValidationError) as exc:
                return _ok("check_account", str(exc),
                           {"prompt": "No account found. Please verify your number or call 1600."})
            except Exception as exc:
                logger.exception("check_account failed: %s", exc)
                return _ok("check_account", "Could not verify account.",
                           {"prompt": "I'm having trouble right now. Please call 1600."})

    # ── FAQ intents ────────────────────────────────────────────────────────────
    if intent.startswith("FAQ_"):
        kb_key = _FAQ_KEY_MAP.get(intent.lower())
        if kb_key:
            try:
                answer = lookup_faq(kb_key)
                return _ok("faq", f"Answer for {kb_key}", {"topic": kb_key, "answer": answer})
            except NotFoundError:
                pass
        return _ok("faq", "No specific FAQ found.",
                   {"prompt": "I didn't find an exact answer. Try rephrasing or call 1600."})

    # ── Troubleshoot intents ───────────────────────────────────────────────────
    if intent.startswith("TRBL_"):
        kb_key = _TRBL_KEY_MAP.get(intent.lower(), intent.replace("TRBL_", "").lower())
        try:
            steps = troubleshoot_issue(kb_key)
            return _ok("troubleshoot", f"Steps for {kb_key}", {"issue": kb_key, "steps": steps})
        except NotFoundError:
            return _ok("troubleshoot", "No guide found.",
                       {"prompt": "I don't have a guide for that yet. Please call 1600 (free, 24/7)."})

    # ── Escalation intents ─────────────────────────────────────────────────────
    if intent == "ESCALATE_HUMAN":
        return _ok("escalate", "Connecting to human support.", {
            "hotline": "1600",
            "chat": "telconnect.com.np/support",
            "email": "support@telconnect.com.np",
            "prompt": "I'll connect you to our support team.\n📞 Hotline: 1600 (free, 24/7)\n💬 telconnect.com.np/support",
        })

    if intent in {"ESCALATE_COMPLAINT", "ESCALATE_REFUND"}:
        return _ok("escalate", "Escalating to complaint/refund team.", {
            "url": "telconnect.com.np/complaint",
            "hotline": "1600",
            "email": "complaint@telconnect.com.np",
            "prompt": (
                "I'm sorry for the inconvenience. To file a complaint or request a refund:\n"
                "1. Visit: telconnect.com.np/complaint\n"
                "2. Call: 1600 (free, 24/7)\n"
                "3. Email: complaint@telconnect.com.np"
            ),
        })

    # ── Unknown ────────────────────────────────────────────────────────────────
    if _looks_out_of_scope(normalized_msg):
        return _out_of_scope_response(normalized_msg)

    return _ok("engine", "Intent not recognized.", {
        "prompt": (
            "I can help with balance, packages, expiry dates, FAQs, and network issues. "
            "Please ask a telecom-related question."
        )
    })


def _lookup_package_for_phone(phone: str) -> Dict[str, Any]:
    """Get account then look up the named package."""
    account = get_telconnect_account(phone)
    plan_name = account.get("plan_name") or account.get("plan") or ""
    pkg = lookup_package(name=plan_name)
    return {
        "customer_name": account.get("customer_name"),
        "plan_name": plan_name,
        "package": pkg,
    }
