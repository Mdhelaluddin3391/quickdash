from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

class BurstRateThrottle(UserRateThrottle):
    """
    Strict throttling for OTP generation and login attempts.
    Scope: 'burst' (Configured in settings as 10/min)
    """
    scope = 'burst'

class SustainedRateThrottle(UserRateThrottle):
    """
    General API usage.
    """
    scope = 'user'