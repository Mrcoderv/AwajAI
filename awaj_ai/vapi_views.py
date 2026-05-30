"""Vapi integration entrypoints.

This repository already exposes tool-style JSON endpoints under `/api/`.
Vapi needs a server-side webhook (or similar request handler) to:
- receive conversation events/transcripts
- decide the assistant reply
- (optionally) call backend tools and return the result

Because Vapi event payloads can vary by configuration, this handler is
implemented defensively: it accepts JSON payloads with common fields and
falls back gracefully.

Expected minimal client payload fields (typical):
- transcript: the latest user speech/text
- callId or call_id: unique call/session id
- sessionId (optional)

The response is shaped for a typical webhook usage:
- reply: assistant text to speak back
- language: best-effort language ('en' or 'ne')
"""

import json
import re
from typing import Optional, Tuple

from django.http import HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from accounts.services import get_telconnect_account
from core.exceptions import AppError, NotFoundError, ValidationError
from core.services import lookup_package
from faq.services import search_faqs


def _json_body(request) -> dict:
    try:
        body = request.body.decode("utf-8")
        if not body:
            return {}
        return json.loads(body)
    except Exception:
        return {}


def _extract_transcript(payload: dict) -> Optional[str]:
    # Try common keys
    for key in ("transcript", "text", "utterance", "message", "user_speech"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    # Some clients nest the transcript
    for container_key in ("input", "data", "event"):
        container = payload.get(container_key)
        if isinstance(container, dict):
            for key in ("transcript", "text", "utterance", "message"):
                val = container.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

    return None


def _detect_lang(text: str) -> str:
    if not text:
        return "en"
    # Devanagari block detection
    if re.search(r"[\u0900-\u097F]", text):
        return "ne"
    nepali_markers = r"\b(मेरो|नमस्ते|धन्यवाद|कसरी|मलाई|तपाईं|के|किन|कति|प्याकेज|प्लान)\b"
    if re.search(nepali_markers, text, flags=re.IGNORECASE):
        return "ne"
    return "en"


def _normalize(text: str) -> str:
    return (text or "").strip()


def _parse_phone(text: str) -> Optional[str]:
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    # telecom demo phones vary; accept 7-15 digits
    if 7 <= len(digits) <= 15:
        return digits
    return None


def _is_faq_like(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if t.endswith("?"):
        return True
    triggers = ["faq", "help", "about", "how", "what", "why", "when", "where"]
    return any(tr in t for tr in triggers)


@csrf_exempt
def vapi_webhook(request):
    """Handle Vapi webhook calls.

    Returns JSON with `reply`.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    payload = _json_body(request)
    transcript = _extract_transcript(payload) or ""

    if not transcript.strip():
        return JsonResponse({"ok": False, "error": "Missing transcript"}, status=400)

    lang = _detect_lang(transcript)
    tnorm = transcript.strip()

    # Phone-first routing for account lookup
    phone = _parse_phone(tnorm)
    if phone:
        try:
            account = get_telconnect_account(phone)
            if lang == "ne":
                reply = (
                    f"धन्यवाद। मैले {account.get('customer_name')} को account फेला पारेँ। "
                    f"तपाईंलाई balance, due date, कि package details चाहिन्छ?"
                )
            else:
                reply = (
                    f"Thanks. I found the account for {account.get('customer_name')}. "
                    f"Would you like your balance, due date, or package details next?"
                )
            # Optional: return tool data for Vapi/clients that support it
            return JsonResponse({"ok": True, "reply": reply, "language": lang, "data": {"account": account}})
        except ValidationError as exc:
            msg = str(exc)
            return JsonResponse({"ok": False, "error": msg}, status=400)
        except NotFoundError:
            if lang == "ne":
                reply = "त्यो फोन नम्बरका लागि account भेटिएन। अर्को नम्बर दिनुहुन्छ?"
            else:
                reply = "I couldn’t find an account for that phone number. Would you like to try another number?"
            return JsonResponse({"ok": True, "reply": reply, "language": lang})
        except AppError:
            return JsonResponse({"ok": False, "error": "Server error"}, status=500)

    # Package lookup (by keyword/name or id)
    lower = tnorm.lower()
    if "package" in lower or "plan" in lower or re.search(r"\b(starter|smart|plus)\b", lower):
        pkg_id = None
        m = re.search(r"\b(\d{1,})\b", lower)
        if m:
            pkg_id = m.group(1)
        name = None
        if "starter" in lower:
            name = "TelConnect Starter"
        elif "smart" in lower:
            name = "TelConnect Smart"
        elif "plus" in lower:
            name = "TelConnect Plus"

        try:
            package = lookup_package(pkg_id, name)
            if lang == "ne":
                reply = (
                    f"{package.get('name')} package सक्रिय छ। "
                    f"Data: {package.get('data_gb')} GB, Voice: {package.get('voice_minutes')} मिनेट, SMS: {package.get('sms_count')}."
                )
            else:
                reply = (
                    f"{package.get('name')} is active. "
                    f"Data: {package.get('data_gb')} GB, Voice: {package.get('voice_minutes')} minutes, SMS: {package.get('sms_count')}."
                )
            return JsonResponse({"ok": True, "reply": reply, "language": lang, "data": {"package": package}})
        except Exception:
            reply = "म package details पुष्टि गर्न सकेन। तपाईंले package नाम वा id भन्नुहुन्छ?" if lang == "ne" else "I couldn’t find that package. What’s the package name or id?"
            return JsonResponse({"ok": True, "reply": reply, "language": lang})

    # FAQ lookup
    if _is_faq_like(tnorm):
        q = tnorm
        try:
            results = search_faqs(q)
            if not results:
                raise NotFoundError("No FAQ")
            faq = results[0]
            if lang == "ne":
                reply = f"छोटो उत्तर: {faq.get('answer')}"
            else:
                reply = f"Here’s the answer: {faq.get('answer')}"
            return JsonResponse({"ok": True, "reply": reply, "language": lang, "data": {"faq": faq}})
        except Exception:
            reply = "म त्यस विषयको FAQ फेला पार्न सकिनँ। अलि स्पष्ट रूपमा सोध्न सक्नुहुन्छ?" if lang == "ne" else "I couldn’t find a matching FAQ. Could you ask in a different way?"
            return JsonResponse({"ok": True, "reply": reply, "language": lang})

    # Fallback
    if lang == "ne":
        reply = "म balance, package, र FAQ सबैमा मद्दत गर्न सक्छु। पहिले तपाईंको फोन नम्बर दिनुहुन्छ?"
    else:
        reply = "I can help with balance, packages, and FAQs. What phone number should I use?"

    return JsonResponse({"ok": True, "reply": reply, "language": lang})

