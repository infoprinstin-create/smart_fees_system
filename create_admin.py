import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "school_fees_system.settings")
django.setup()

from django.contrib.auth.models import User

username = os.environ.get("ADMIN_USERNAME")
password = os.environ.get("ADMIN_PASSWORD")

if username and password:
    user, created = User.objects.get_or_create(username=username)

    user.set_password(password)
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()

    if created:
        print(f"Created admin user: {username}")
    else:
        print(f"Admin user already exists: {username}")
else:
    print("ADMIN_USERNAME or ADMIN_PASSWORD not configured.")