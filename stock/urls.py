from django.urls import path
from . import views

urlpatterns = [
    path('', views.initial_test_page, name='initial_test_page'),
    path('xbrl', views.xbrl_parse_page, name='xbrl_parse_page')
]
