import time
import functools
from django.core.cache import cache
from apps.utils.exceptions import BusinessLogicException

class CircuitBreaker:
    def __init__(self, service_name, failure_threshold=5, recovery_timeout=60):
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.cache_key_failures = f"cb_failures:{service_name}"
        self.cache_key_open = f"cb_open:{service_name}"

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Check if Circuit is OPEN
            if cache.get(self.cache_key_open):
                raise BusinessLogicException(
                    f"{self.service_name} is temporarily unavailable. Please try again later."
                )

            try:
                # 2. Attempt Call
                result = func(*args, **kwargs)
                
                # 3. Success? Reset failures (optional, or rely on TTL)
                # For strictness, we don't reset on every success to avoid flapping,
                # but clearing it here is common for "stable" state.
                # cache.delete(self.cache_key_failures)
                return result

            except Exception as e:
                # 4. Failure: Increment Counter
                failures = cache.incr(self.cache_key_failures)
                
                # First failure? Set expiry for the counter window (e.g. 5 errors in 2 mins)
                if failures == 1:
                    cache.expire(self.cache_key_failures, 120)

                # 5. Threshold Reached? OPEN Circuit
                if failures >= self.failure_threshold:
                    cache.set(self.cache_key_open, "OPEN", timeout=self.recovery_timeout)
                    cache.delete(self.cache_key_failures) # Reset counter for next cycle
                
                raise e

        return wrapper

# Usage Example in PaymentService:
# from apps.utils.resilience import CircuitBreaker
# 
# @staticmethod
# @CircuitBreaker(service_name="razorpay", failure_threshold=5, recovery_timeout=30)
# def _get_client():
#     ...