from django.contrib import admin

from .models import Package


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
	list_display = ("name", "price", "data_gb", "voice_minutes", "sms_count", "is_active")
	search_fields = ("name", "description")
	list_filter = ("is_active",)
	ordering = ("name",)
