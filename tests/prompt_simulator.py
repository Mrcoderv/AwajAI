#!/usr/bin/env python3
"""Final conversational QA harness for AwajAI.

Runs a small end-to-end smoke suite against the chat engine and prints a
simple PASS / FAIL / WARNINGS report.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "awaj_ai.settings")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import django

django.setup()

from awaj_ai.engine import process_message  # noqa: E402


class DummyRequest:
    def __init__(self, message: str, phone: str = "", method: str = "GET", session=None):
        self.method = method
        self.session = session if session is not None else {}
        self.GET = {"msg": message, "phone": phone} if method == "GET" else {}
        self.POST = {}
        body = {"msg": message, "phone": phone}
        self.body = json.dumps(body).encode("utf-8") if method != "GET" else b""


def call_engine(message: str, phone: str = "", method: str = "GET", session=None):
    request = DummyRequest(message=message, phone=phone, method=method, session=session)
    response = process_message(request)
    payload = json.loads(response.content.decode("utf-8"))
    return payload, request.session


def assert_contains(text: str, fragments):
    lowered = (text or "").lower()
    return all(fragment.lower() in lowered for fragment in fragments)


def main() -> int:
    results = []
    warnings = []

    tests = [
        ("greetings", lambda: call_engine("hello", session={}), lambda payload: assert_contains(payload.get("data", {}).get("prompt", ""), ["hello", "awajai", "help"])),
        ("unknown_questions", lambda: call_engine("nitric acid", session={}), lambda payload: assert_contains(payload.get("data", {}).get("prompt", ""), ["telecom", "question"])),
        ("balance_only", lambda: call_engine("check my balance", phone="9866412176", session={}), lambda payload: assert_contains(payload.get("data", {}).get("prompt", ""), ["current balance"]) and "package" not in payload.get("data", {}).get("prompt", "").lower()),
        ("package_only", lambda: call_engine("package", phone="9866412176", session={}), lambda payload: assert_contains(payload.get("data", {}).get("prompt", ""), ["current package"]) and "balance" not in payload.get("data", {}).get("prompt", "").lower()),
        ("expiry_only", lambda: call_engine("expiry", phone="9866412176", session={}), lambda payload: assert_contains(payload.get("data", {}).get("prompt", ""), ["expiry date"])),
        ("faq_latest_packages", lambda: call_engine("latest packages", session={}), lambda payload: payload.get("tool") == "faq"),
        ("nepali_support", lambda: call_engine("नमस्ते", session={}), lambda payload: "नमस्ते" in payload.get("data", {}).get("prompt", "") or "AwajAI" in payload.get("data", {}).get("prompt", "")),

        ("voice_input", lambda: call_engine("9866 412 176", session={}), lambda payload: payload.get("tool") == "check_account"),
    ]

    support_session = {}
    support_steps = [
        ("support_troubleshooting", lambda: call_engine("network issue", session=support_session), lambda payload: payload.get("tool") == "troubleshoot" and "steps" in payload.get("data", {})),
        ("support_escalation", lambda: call_engine("still not working", session=support_session), lambda payload: payload.get("tool") == "escalate"),
        ("ticket_creation", lambda: call_engine("create support ticket", session=support_session), lambda payload: payload.get("tool") == "support_ticket" and str(payload.get("data", {}).get("ticket_id", "")).startswith("TKT-")),
        ("ticket_followup", lambda: call_engine("check ticket", session=support_session), lambda payload: payload.get("tool") == "support_ticket" and str(payload.get("data", {}).get("ticket_id", "")).startswith("TKT-")),
        ("thank_you_followup", lambda: call_engine("thank you", session=support_session), lambda payload: payload.get("tool") == "support_ticket" and payload.get("data", {}).get("status") == "Open"),
    ]

    tests.extend(support_steps)

    for name, runner, predicate in tests:
        try:
            payload, _ = runner()
            ok = bool(predicate(payload))
            status = "PASS" if ok else "FAIL"
            prompt = payload.get("data", {}).get("prompt") if isinstance(payload.get("data"), dict) else None
            if not prompt and payload.get("message"):
                prompt = payload.get("message")
            print(f"{status}: {name} -> tool={payload.get('tool')} prompt={prompt!r}")
            results.append(ok)
        except Exception as exc:
            print(f"FAIL: {name} -> {exc}")
            results.append(False)

    if not support_session.get("awaj_conversation_state"):
        warnings.append("Conversation state was not persisted in the support session during QA.")

    passed = sum(1 for item in results if item)
    total = len(results)
    failed = total - passed

    print("\nPASS")
    print(f"{passed}/{total}")
    print("FAIL")
    print(f"{failed}/{total}")
    print("WARNINGS")
    if warnings:
        for warning in warnings:
            print(f"- {warning}")
    else:
        print("- None")

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
