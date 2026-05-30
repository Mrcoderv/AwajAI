"""Frontend page views for the AwajAI template UI."""

from django.shortcuts import render

from accounts.services import get_dashboard_customer
from core.exceptions import AppError


def home(request):
	"""Render the project landing page."""
	return render(request, "core/home.html")


def call_page(request):
	"""Render the chat-first assistant page."""
	return render(request, "core/chat.html")


def chat_page(request):
	"""Render the chat-first assistant page."""
	return render(request, "core/chat.html")


def dashboard(request):
	"""Render the customer dashboard, optionally filtered by phone."""
	phone = (request.GET.get("phone") or "").strip()
	try:
		customer = get_dashboard_customer(phone)
	except AppError:
		customer = None

	return render(
		request,
		"core/dashboard.html",
		{
			"search_phone": phone,
			"customer": customer,
		},
	)


def code_map(request):
	return render(request, "core/code_map.html")
