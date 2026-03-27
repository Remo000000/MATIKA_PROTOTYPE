from __future__ import annotations


def get_default_department(organization=None):
    """Default faculty/department for self-registered teachers (no admin form)."""
    from university.models import Department, Faculty
    from university.scope import get_default_organization

    org = organization or get_default_organization()
    faculty, _ = Faculty.objects.get_or_create(organization=org, name="Default")
    dept, _ = Department.objects.get_or_create(faculty=faculty, name="General")
    return dept


def latinize_text(value: str) -> str:
    """
    Normalize spacing while preserving the original alphabet (including Cyrillic).
    """
    text = (value or "").strip()
    if not text:
        return text
    return " ".join(text.split())

