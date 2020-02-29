from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

SECRET_KEY = open(os.path.join(BASE_DIR, "env")).read().rstrip().lstrip()

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, '../../db.sqlite3'),
    }
}