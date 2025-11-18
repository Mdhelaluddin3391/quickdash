# apps/utils/models.py
from django.db import models

class TimestampedModel(models.Model):
    """
    Ek abstract base class model jo har model mein 
    'created_at' aur 'updated_at' fields jodta hai.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Abstract = True se Django is model ke liye koi table nahi banayega.
        # Yeh sirf doosre models ko fields dene ke liye hai.
        abstract = True
        ordering = ['-created_at']