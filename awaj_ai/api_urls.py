from django.urls import path

from . import api_views
from .chat_views import chat

urlpatterns = [
    # ── Unified chat/intent endpoint (engine-powered) ──────────────────────
    path("chat", chat, name="chat"),

    # ── Existing tool endpoints ─────────────────────────────────────────────
    path("check_account", api_views.check_account, name="check_account"),
    path("telconnect-account", api_views.telconnect_account, name="telconnect_account"),
    path("package", api_views.package_details, name="package_details"),
    path("faq", api_views.faq_search, name="faq_search"),
    path("prompts", api_views.assist_prompts, name="assist_prompts"),
    path("session-phone", api_views.session_phone, name="session_phone"),
    path("quick-questions", api_views.quick_questions, name="quick_questions"),
    path("support-ticket", api_views.support_ticket, name="support_ticket"),
    path("demo-accounts", api_views.demo_accounts, name="demo_accounts"),
    path("create-test-account", api_views.create_test_account_view, name="create_test_account"),
    path("generate-sample-customer", api_views.generate_sample_customer, name="generate_sample_customer"),
    path("delete-code-map", api_views.delete_code_map, name="delete_code_map"),
    path("intent-log", api_views.intent_log, name="intent_log"),
]