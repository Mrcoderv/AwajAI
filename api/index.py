"""Vercel entrypoint for the AwajAI Django project."""

import os


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "awaj_ai.settings")

from awaj_ai.wsgi import application as app