"""
URL configuration for awaj_ai project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from .vapi_views import vapi_webhook

urlpatterns = [
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("support/", include("support.urls")),
    path("api/", include("awaj_ai.api_urls")),
    # Vapi webhook (voice agent entrypoint)
    path("api/vapi-webhook", vapi_webhook, name="vapi_webhook"),
    path("admin/", admin.site.urls),
]
