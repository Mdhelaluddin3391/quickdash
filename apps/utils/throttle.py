from rest_framework.throttling import UserRateThrottle


class BurstRateThrottle(UserRateThrottle):
    scope = "burst"
    rate = "20/min"


class SustainedRateThrottle(UserRateThrottle):
    scope = "sustained"
    rate = "300/hour"
