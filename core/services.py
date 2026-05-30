"""Shared core service helpers using JSON files for package data."""

from core.json_data import load_json
from core.exceptions import NotFoundError, ServiceError, ValidationError


def lookup_package(package_id=None, name=None):
    """Look up a package by numeric id or case-insensitive name from JSON.

    Returns a package dict if found.
    """
    if not package_id and not name:
        raise ValidationError("Please provide a package id or name.")

    try:
        packages = load_json("packages.json")
    except ServiceError as exc:
        raise

    if package_id:
        if not str(package_id).strip().isdigit():
            raise ValidationError("Package id must be a valid number.")
        for pkg in packages:
            if int(pkg.get("id")) == int(package_id):
                return pkg

    if name:
        lookup = (name or "").strip().lower()
        for pkg in packages:
            if (pkg.get("name") or "").strip().lower() == lookup:
                return pkg

    raise NotFoundError("I couldn't find that package.")
