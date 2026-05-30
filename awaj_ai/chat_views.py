import json
from django.http import JsonResponse
from .engine import process_message

def chat(request):
    """Unified endpoint for Awaj AI conversation.
    Accepts GET with `msg` and optional `phone`, or POST JSON {msg, phone}.
    Delegates all logic to `engine.process_message`.
    """
    return process_message(request)
