import os

from django.core.wsgi import get_wsgi_application

# Fail closed: a WSGI server started without DJANGO_SETTINGS_MODULE gets prod settings, which refuse to start
# without DJANGO_SECRET_KEY. An explicitly set module is respected; manage.py keeps dev as the local default.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

application = get_wsgi_application()
