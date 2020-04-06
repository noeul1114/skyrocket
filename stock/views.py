from django.shortcuts import render
from django.shortcuts import HttpResponse

from .xbrl.rawdata import raw_data_parse

# Create your views here.


def initial_test_page(request):
    return HttpResponse("Testing succeeded!!!!")


def xbrl_parse_page(request):
    raw_data_parse()
    return HttpResponse("xbrl parse success")
