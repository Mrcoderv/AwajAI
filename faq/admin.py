"""Admin registration for FAQ records."""

from django.contrib import admin

from .models import FAQ


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    """Provide a searchable FAQ index in Django admin."""

    list_display = ("question", "category", "is_published", "created_at")
    search_fields = ("question", "answer", "category")
    list_filter = ("is_published", "category", "created_at")
    ordering = ("question",)
