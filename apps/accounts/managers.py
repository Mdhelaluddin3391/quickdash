from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def add_arguments(self, parser):
        """
        Allow `python manage.py createsuperuser --phone ...` even when USERNAME_FIELD='id'
        (Django's createsuperuser normally expects the USERNAME_FIELD arg; this adds a friendly --phone).
        """
        parser.add_argument('--phone', type=str, required=False)

    def _create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("The phone field must be set")

        user = self.model(phone=phone, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone, password, **extra_fields)

    def create_superuser(self, phone=None, password=None, **extra_fields):
        """
        create_superuser will be used by management commands and by our management helper.
        Because USERNAME_FIELD='id', Django may supply an 'id' argument; we accept `phone` here
        so you can run: python manage.py createsuperuser --phone <number>
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        if phone is None:
            # fallback: if phone not provided, allow creation with empty phone (admin will set later)
            phone = ""

        return self._create_user(phone, password, **extra_fields)
