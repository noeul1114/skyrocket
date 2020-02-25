from .base import *

DEBUG = False

ALLOWED_HOSTS = ['*']

secret_root = '/run/secret/'

secret_list = dict()
all_secret_file = os.listdir(secret_root)

for secret in all_secret_file:
    file = open(os.path.join(secret_root, secret))
    secret_list[secret] = file.read().lstrip().rstrip()
    file.close()

SECRET_KEY = secret_list['SECRET_KEY']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': secret_list['MYSQL_DATABASE'],
        'USER': secret_list['MYSQL_USER'],
        'PASSWORD': secret_list['MYSQL_PASSWORD'],
        'HOST': 'mariadb',
        'PORT': '3306',
    }
}