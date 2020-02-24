from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.initial_test_page, name='initial_test_page')
]

