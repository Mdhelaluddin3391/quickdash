# apps/utils/context_processors.py
from django.conf import settings

def google_maps_api_key(request):
    """
    Expose GOOGLE_MAPS_API_KEY to all templates.
    Used in base.html or frontend pages for map rendering.
    """
    return {
        "GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", "")
    }