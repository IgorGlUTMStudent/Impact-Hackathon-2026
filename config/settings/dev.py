import os

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "dev-only-insecure-key-never-use-in-prod"
WHITENOISE_AUTOREFRESH = True  # serve static/ directly; no collectstatic in dev
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
# Add the laptop's LAN IP here to test `runserver 0.0.0.0:8000` from a phone.
ALLOWED_HOSTS += env_list("DJANGO_ALLOWED_HOSTS")  # noqa: F405
