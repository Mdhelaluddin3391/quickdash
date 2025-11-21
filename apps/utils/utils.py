import uuid
from django.utils import timezone


def now():
    return timezone.now()


def generate_code(prefix=""):
    return prefix + uuid.uuid4().hex[:8].upper()


def dict_clean(d: dict):
    """
    Remove keys where value is None or empty
    """
    return {k: v for k, v in d.items() if v not in [None, "", [], {}]}
