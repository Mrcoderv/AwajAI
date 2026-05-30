"""Support ticket helpers backed by JSON mock storage."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from core.exceptions import NotFoundError, ServiceError, ValidationError
from core.json_data import load_json, save_json

logger = logging.getLogger(__name__)

_DEFAULT_ISSUE = "Network connectivity"


def _normalize_phone(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _load_tickets() -> List[Dict[str, Any]]:
    try:
        tickets = load_json("support_tickets.json")
        return tickets if isinstance(tickets, list) else []
    except ServiceError as exc:
        if "Data file not found" in str(exc):
            return []
        raise


def _save_tickets(tickets: List[Dict[str, Any]]) -> None:
    save_json("support_tickets.json", tickets)


def _ticket_number(ticket_id: str) -> int:
    try:
        return int(str(ticket_id).replace("TKT-", ""))
    except Exception:
        return 0


def _issue_label(issue: str) -> str:
    cleaned = (issue or "").strip()
    return cleaned or _DEFAULT_ISSUE


def _ticket_summary(ticket: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ticket_id": ticket.get("ticket_id"),
        "issue": ticket.get("issue"),
        "status": ticket.get("status"),
        "phone_number": ticket.get("phone_number"),
        "customer_name": ticket.get("customer_name"),
        "created_at": ticket.get("created_at"),
        "updated_at": ticket.get("updated_at"),
    }


def find_ticket(ticket_id: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
    tickets = _load_tickets()
    normalized_phone = _normalize_phone(phone)

    if ticket_id:
        for ticket in tickets:
            if str(ticket.get("ticket_id")) == str(ticket_id):
                return ticket
        raise NotFoundError("No ticket found for that ticket id.")

    if normalized_phone:
        matching = [t for t in tickets if _normalize_phone(t.get("phone_number")) == normalized_phone]
        if matching:
            matching.sort(key=lambda item: item.get("created_at", ""), reverse=True)
            return matching[0]

    raise NotFoundError("No ticket found for that phone number.")


def create_support_ticket(
    issue: str,
    phone: Optional[str] = None,
    customer_name: Optional[str] = None,
    conversation_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_phone = _normalize_phone(phone)
    if phone and len(normalized_phone) not in {0, 10}:
        raise ValidationError("Please provide a valid Nepal phone number.")

    tickets = _load_tickets()
    normalized_issue = _issue_label(issue)
    if conversation_state and conversation_state.get("ticket_id"):
        existing_id = str(conversation_state.get("ticket_id"))
        for ticket in tickets:
            if str(ticket.get("ticket_id")) == existing_id:
                return ticket

    if normalized_phone:
        for ticket in tickets:
            if _normalize_phone(ticket.get("phone_number")) == normalized_phone and ticket.get("status") == "Open":
                if (ticket.get("issue") or "").strip().lower() == normalized_issue.lower():
                    return ticket

    next_number = 1024
    if tickets:
        next_number = max(_ticket_number(ticket.get("ticket_id")) for ticket in tickets) + 1

    now = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    ticket = {
        "ticket_id": f"TKT-{next_number}",
        "issue": normalized_issue,
        "status": "Open",
        "phone_number": normalized_phone,
        "customer_name": customer_name or "",
        "created_at": now,
        "updated_at": now,
        "source": "chat",
        "conversation_state": conversation_state or {},
    }
    tickets.append(ticket)

    try:
        _save_tickets(tickets)
        logger.info("Created support ticket %s for %s", ticket["ticket_id"], normalized_phone or "anonymous")
    except Exception as exc:
        raise ServiceError(f"Unable to save support ticket: {exc}") from exc

    return ticket


def get_ticket_details(ticket_id: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
    ticket = find_ticket(ticket_id=ticket_id, phone=phone)
    return _ticket_summary(ticket)


def format_ticket_confirmation(ticket: Dict[str, Any]) -> str:
    issue = ticket.get("issue") or _DEFAULT_ISSUE
    return (
        "Support ticket created successfully.\n\n"
        f"Ticket ID: {ticket.get('ticket_id')}\n"
        f"Issue: {issue}\n"
        f"Status: {ticket.get('status', 'Open')}\n\n"
        "Our support team will contact you shortly."
    )