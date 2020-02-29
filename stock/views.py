from django.shortcuts import render
from django.shortcuts import HttpResponse


# Create your views here.


def initial_test_page(request):
    return HttpResponse("Testing succeeded!")
