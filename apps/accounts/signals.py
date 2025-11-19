from django.dispatch import Signal

# Custom Signal: Jab user ka phone OTP verify ho jaye
user_verified = Signal()  # arguments: user, request

# Custom Signal: Jab user ka role change ho (e.g. Customer -> Rider)
role_changed = Signal() # arguments: user, old_role, new_role