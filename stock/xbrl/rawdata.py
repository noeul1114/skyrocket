from django.shortcuts import render, HttpResponseRedirect, HttpResponse
from django.urls import reverse

from django.core.paginator import Paginator
from stock.models import CompanyBase, CompanyNameGlobal, CompanyData

from rest_framework.views import APIView
from rest_framework.response import Response

# Create your views here.

from rest_framework import serializers

import requests
from urllib import request as rq
import zipfile
from copy import copy
import os

from .xbrl_code_list import *

import math
import json
import urllib3
import requests
import time
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup as bs
from stock.models import CompanyData, CompanyBase, XBRL_CompanyData
from django.utils import timezone

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from collections import deque

from django.conf import settings

import csv
import pandas
from tqdm import tqdm

BASE_DIR = settings.BASE_DIR


class RawDataManager:

    def get_chromedriver(self, **path):

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        if path:
            driver_path = path
        else:
            driver_path = os.path.join(BASE_DIR, "chromedriver.exe")
        driver = webdriver.Chrome(driver_path, chrome_options=chrome_options)
        return driver

def index_view_page_xbrl(request):
    # 재무정보 일괄 다운로드 하는 과정

    ####################################
    rawDataManager = RawDataManager()
    driver = rawDataManager.get_chromedriver()

    base_url = "http://dart.fss.or.kr/dsext002/main.do"

    driver.get(base_url)

    print(driver.page_source)

    soup = bs(driver.page_source, 'html.parser')
    soup = soup.find('table', class_="list")

    print(soup)

    total_list = soup.find_all("tr")

    # 분기별 일괄정보 zip URL 파싱해내는 작업

    BS_list, PL_list, CF_list, CE_list = deque(), deque(), deque(), deque()

    for row in total_list[1:]:
        table_datas = row.find_all("td")
        # print(table_datas)
        BS = table_datas[3]     # 재무상태표 : BS  (Balance Sheet)
        PL = table_datas[4]     # 손익계산서 : PL  (Profit & Loss)
        CF = table_datas[5]     # 현금흐름표 : CF  (Cash Flow)
        CE = table_datas[6]     # 자본변동표 : CE  (Changes in Equity)

        print(BS.find("a")['onclick'].split('\'')[7])
        print(PL.find("a")['onclick'].split('\'')[7])
        print(CF.find("a")['onclick'].split('\'')[7])
        print(CE.find("a")['onclick'].split('\'')[7])

        BS_list.append(BS.find("a")['onclick'].split('\'')[7])
        PL_list.append(PL.find("a")['onclick'].split('\'')[7])
        CF_list.append(CF.find("a")['onclick'].split('\'')[7])
        CE_list.append(CE.find("a")['onclick'].split('\'')[7])

    print(BS_list, PL_list, CF_list, CE_list)

    # 일괄정보 URL 파싱한 것으로 for 돌리는 작업

    LIST = [BS_list, PL_list, CF_list, CE_list]
    length = len(BS_list)

    for x in range(4):
        t = 1
        for y in range(length):
            url = LIST[x].pop()

            # URL of the image to be downloaded is defined as image_url
            r = requests.get(url)  # create HTTP response object

            # send a HTTP request to the server and save
            # the HTTP response in a response object called r
            temp_path = os.path.join(BASE_DIR, 'Download', 'temp.zip')
            with open(temp_path, 'wb') as f:
                # Saving received content as a png file in
                # binary format

                # write the contents of the response (r.content)
                # to a new file in binary mode.
                f.write(r.content)

            with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                # Get a list of all archived file names from the zip
                listOfFileNames = zip_ref.namelist()
                # Iterate over the file names
                for fileName in listOfFileNames:
                    # Check filename endswith csv
                    if fileName.endswith('.txt'):

                        # Extract a single file from zip
                        zip_ref.extract(fileName, path="Download/")

                        # zipfile 라이브러리로 바로 풀경우에 한글 제목 깨짐 방지하기 위해
                        # cp437 - euc-kr 거쳐서 제목을 바꾸어주는 과정
                        os.rename('Download/'+fileName,
                                  'Download/'+fileName.encode('cp437').decode('euc-kr'))

            # for fileName in listOfFileNames:
            #     os.remove("Download/"+fileName.encode('cp437').decode('euc-kr'))

            os.remove("Download/temp.zip")

    ########################################

    # 일괄정보 zip 압축 풀어낸 이후 내부에서 원하는 정보 추출해내는 작업

    # 1. 연도/분기 나누어서 BS,PL,CF,CE 파일 결정
    # 2. CSV 타입의 TXT 파일 읽어들이기
    # 3. XBRL_CompanyData 필요한 정보들 파싱
    # 4. 연도/분기 모든 정보들 있으면 Verify 후 저장

    all_report_list = []

    current_location = os.path.join(BASE_DIR, "Download")

    # r=>root, d=>directories, f=>files
    # Download 내의 모든 txt 파일들 이름 추출해내는 작업
    for r, d, f in os.walk(current_location):
        for item in f:
            if '.txt' in item:
                all_report_list.append(os.path.join(r, item))

    for item in all_report_list:
        print("all_report_list: ", item)

    # txt 파일들 이름은 yyyy_X분기보고서_00_재무상태표_(연결)_최종수정날짜 순으로 되어있음
    # "_" 언더바를 기준으로 Split 하여 정보들을 나누고 그를 기반으로 연도/분기별 원하는 파일만 골라냄

    gaap = []
    ifrs = []

    for report_name in all_report_list:
        splitted = report_name.split("\\")[-1]
        splitted = splitted.split("_")
        if len(splitted) == 5:
            gaap.append(splitted)
        else:
            ifrs.append(splitted)

    for txt in tqdm(gaap[::-1]):
        # read CSV file & load into list
        file_path = os.path.join(current_location, "_".join(txt))
        with open(file_path, 'r') as my_file:
            reader = pandas.read_csv(my_file, delimiter='\t')
            # print(reader)
            # repr(reader)

            # 재무상태표
            if txt[2] == "01":
                # 보고서별로 뽑아낼 XBRL 라벨을 알아두어야함
                # print(reader[reader['항목코드']
                #       .isin(['ifrs_Assets', 'ifrs_Equity', 'ifrs_Liabilities'])])
                temp = reader[reader['항목코드'].isin
                (['ifrs_Assets', 'ifrs_Equity', 'ifrs_Liabilities','ifrs-full_Assets', 'ifrs-full_Equity', 'ifrs-full_Liabilities'])]

                if txt[1] == "사업보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기', '항목명']]
                    quarter = 12
                elif txt[1] == "1분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 1분기말', '항목명']]
                    quarter = 3
                elif txt[1] == "반기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 반기말', '항목명']]
                    quarter = 6
                elif txt[1] == "3분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 3분기말', '항목명']]
                    quarter = 9

                for index, row in temp.iterrows():
                    # print(row['종목코드'][1:-1])
                    company_code = row['종목코드'][1:-1]
                    if CompanyBase.objects.filter(code=company_code).exists():
                        company = CompanyBase.objects.get(code=company_code)
                    else:
                        company = CompanyBase.objects.create(code=company_code,
                                                             status=0)
                    XBRL, XO = XBRL_CompanyData.objects.get_or_create(company_name=company,
                                                                      year_model=txt[0],
                                                                      quarter_model=quarter,
                                                                      gaap=True)

                    row_index = row.index

                    if row['항목코드'] == "ifrs_Assets" or\
                            row['항목코드'] == "ifrs-full_Assets":
                        try:
                            XBRL.asset = int(row[row_index[5]].replace(',',''))
                        except:
                            XBRL.asset = 0
                    elif row['항목코드'] == "ifrs_Equity" or\
                            row['항목코드'] == "ifrs-full_Equity":
                        try:
                            XBRL.capital = int(row[row_index[5]].replace(',',''))
                        except:
                            XBRL.capital = 0
                    elif row['항목코드'] == "ifrs_Liabilities" or\
                            row['항목코드'] == 'ifrs-full_Liabilities':
                        try:
                            XBRL.liabilities = int(row[row_index[5]].replace(',',''))
                        except:
                            XBRL.liabilities = 0

                    XBRL.year_model = txt[0]

                    if txt[1] == '사업보고서':
                        XBRL.quarter_model = 12
                    elif txt[1] == '1분기보고서':
                        XBRL.quarter_model = 3
                    elif txt[1] == '반기보고서':
                        XBRL.quarter_model = 6
                    elif txt[1] == '3분기보고서':
                        XBRL.quarter_model = 9

                    XBRL.created_at = timezone.now()

                    XBRL.ratio = row['통화']

                    XBRL.gaap = True
                    XBRL.ifrs = False

                    XBRL.save()

            # 손익계산서
            elif txt[2] == "02":
                # 보고서별로 뽑아낼 XBRL 라벨을 알아두어야함
                # print(reader[reader['항목코드']
                #       .isin(['ifrs_Assets', 'ifrs_Equity', 'ifrs_Liabilities'])])
                temp = reader[reader['항목코드']
                    .isin(['ifrs_Revenue', 'dart_OperatingIncomeLoss', 'ifrs_ProfitLoss',
                           'ifrs-full_Revenue', 'ifrs-full_ProfitLoss'])]

                if txt[1] == "사업보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기', '항목명']]
                    quarter = 12
                elif txt[1] == "1분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 1분기 3개월', '항목명']]
                    quarter = 3
                elif txt[1] == "반기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 반기 3개월', '항목명']]
                    quarter = 6
                elif txt[1] == "3분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 3분기 3개월', '항목명']]
                    quarter = 9

                for index, row in temp.iterrows():
                    # print(row['종목코드'][1:-1])
                    company_code = row['종목코드'][1:-1]
                    if CompanyBase.objects.filter(code=company_code).exists():
                        company = CompanyBase.objects.get(code=company_code)
                    else:
                        company = CompanyBase.objects.create(code=company_code,
                                                             status=0)
                    XBRL, XO = XBRL_CompanyData.objects.get_or_create(company_name=company,
                                                                      year_model=txt[0],
                                                                      quarter_model=quarter,
                                                                      gaap=True)

                    row_index = row.index

                    if row['항목코드'] in ["ifrs_Revenue", "ifrs-full_Revenue"]:
                        try:
                            XBRL.sales = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.sales = 0
                    elif row['항목코드'] == "dart_OperatingIncomeLoss":
                        try:
                            XBRL.operating_revenue = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.operating_revenue = 0
                    elif row['항목코드'] == "ifrs_ProfitLoss" or\
                            row['항목코드'] == "ifrs-full_ProfitLoss":
                        try:
                            XBRL.net_income = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.net_income = 0

                    XBRL.year_model = txt[0]

                    if txt[1] == '사업보고서':
                        XBRL.quarter_model = 12
                    elif txt[1] == '1분기보고서':
                        XBRL.quarter_model = 3
                    elif txt[1] == '반기보고서':
                        XBRL.quarter_model = 6
                    elif txt[1] == '3분기보고서':
                        XBRL.quarter_model = 9

                    XBRL.created_at = timezone.now()

                    XBRL.ratio = row['통화']

                    XBRL.gaap = True
                    XBRL.ifrs = False

                    XBRL.save()

            # 포괄손익계산서
            elif txt[2] == "03":
                # 보고서별로 뽑아낼 XBRL 라벨을 알아두어야함
                # print(reader[reader['항목코드']
                #       .isin(['ifrs_Assets', 'ifrs_Equity', 'ifrs_Liabilities'])])
                temp = reader[reader['항목코드']
                    .isin(['ifrs_Revenue', 'dart_OperatingIncomeLoss',
                           'ifrs_ProfitLoss',
                           'ifrs-full_Revenue', 'ifrs-full_ProfitLoss'])]

                if txt[1] == "사업보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기', '항목명']]
                    quarter = 12
                elif txt[1] == "1분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 1분기 3개월', '항목명']]
                    quarter = 3
                elif txt[1] == "반기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 반기 3개월', '항목명']]
                    quarter = 6
                elif txt[1] == "3분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 3분기 3개월', '항목명']]
                    quarter = 9

                for index, row in temp.iterrows():
                    # print(row['종목코드'][1:-1])
                    company_code = row['종목코드'][1:-1]
                    if CompanyBase.objects.filter(code=company_code).exists():
                        company = CompanyBase.objects.get(code=company_code)
                    else:
                        company = CompanyBase.objects.create(code=company_code,
                                                             status=0)
                    XBRL, XO = XBRL_CompanyData.objects.get_or_create(company_name=company,
                                                                      year_model=txt[0],
                                                                      quarter_model=quarter,
                                                                      gaap=True)

                    row_index = row.index

                    if row['항목코드'] in ["ifrs_Revenue", "ifrs-full_Revenue"]:
                        try:
                            XBRL.sales = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.sales = 0
                    elif row['항목코드'] == "dart_OperatingIncomeLoss":
                        try:
                            XBRL.operating_revenue = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.operating_revenue = 0
                    elif row['항목코드'] == "ifrs_ProfitLoss" or\
                            row['항목코드'] == "ifrs-full_ProfitLoss":
                        try:
                            XBRL.net_income = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.net_income = 0

                    XBRL.year_model = txt[0]

                    if txt[1] == '사업보고서':
                        XBRL.quarter_model = 12
                    elif txt[1] == '1분기보고서':
                        XBRL.quarter_model = 3
                    elif txt[1] == '반기보고서':
                        XBRL.quarter_model = 6
                    elif txt[1] == '3분기보고서':
                        XBRL.quarter_model = 9

                    XBRL.created_at = timezone.now()

                    XBRL.ratio = row['통화']

                    XBRL.gaap = True
                    XBRL.ifrs = False

                    XBRL.save()

            # # 현금흐름표
            # elif txt[2] == "04":
            #     if txt[4] == "연결":
            #         pass
            #     else:
            #         pass
            #
            # # 자본변동표
            # elif txt[2] == "05":
            #     if txt[4] == "연결":
            #         pass
            #     else:
            #         pass

    for txt in tqdm(ifrs[::-1]):
        # read CSV file & load into list
        file_path = os.path.join(current_location, "_".join(txt))
        with open(file_path, 'r') as my_file:
            reader = pandas.read_csv(my_file, delimiter='\t')
            # print(reader)
            # repr(reader)

            # 재무상태표
            if txt[2] == "01":
                # 보고서별로 뽑아낼 XBRL 라벨을 알아두어야함
                temp = reader[reader['항목코드']
                    .isin(['ifrs_Assets', 'ifrs_Equity', 'ifrs_Liabilities',
                           'ifrs-full_Assets', 'ifrs-full_Equity', 'ifrs-full_Liabilities'])]

                if txt[1] == "사업보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기', '항목명']]
                    quarter = 12
                elif txt[1] == "1분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 1분기말', '항목명']]
                    quarter = 3
                elif txt[1] == "반기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 반기말', '항목명']]
                    quarter = 6
                elif txt[1] == "3분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 3분기말', '항목명']]
                    quarter = 9

                for index, row in temp.iterrows():
                    # print(row['종목코드'][1:-1])
                    company_code = row['종목코드'][1:-1]
                    if CompanyBase.objects.filter(code=company_code).exists():
                        company = CompanyBase.objects.get(code=company_code)
                    else:
                        company = CompanyBase.objects.create(code=company_code,
                                                             status=0)
                    XBRL, XO = XBRL_CompanyData.objects.get_or_create(company_name=company,
                                                                      year_model=txt[0],
                                                                      quarter_model=quarter,
                                                                      ifrs=True)

                    row_index = row.index

                    if row['항목코드'] == "ifrs_Assets" or \
                            row['항목코드'] == "ifrs-full_Assets":
                        try:
                            XBRL.asset = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.asset = 0
                    elif row['항목코드'] == "ifrs_Equity" or \
                            row['항목코드'] == "ifrs-full_Equity":
                        try:
                            XBRL.capital = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.capital = 0
                    elif row['항목코드'] == "ifrs_Liabilities" or \
                            row['항목코드'] == 'ifrs-full_Liabilities':
                        try:
                            XBRL.liabilities = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.liabilities = 0

                    XBRL.year_model = txt[0]

                    if txt[1] == '사업보고서':
                        XBRL.quarter_model = 12
                    elif txt[1] == '1분기보고서':
                        XBRL.quarter_model = 3
                    elif txt[1] == '반기보고서':
                        XBRL.quarter_model = 6
                    elif txt[1] == '3분기보고서':
                        XBRL.quarter_model = 9

                    XBRL.created_at = timezone.now()

                    XBRL.ratio = row['통화']

                    XBRL.gaap = False
                    XBRL.ifrs = True

                    XBRL.save()

            # 손익계산서
            elif txt[2] == "02":
                # 보고서별로 뽑아낼 XBRL 라벨을 알아두어야함
                # print(reader[reader['항목코드']
                #       .isin(['ifrs_Assets', 'ifrs_Equity', 'ifrs_Liabilities'])])
                temp = reader[reader['항목코드']
                    .isin(['ifrs_Revenue', 'dart_OperatingIncomeLoss',
                           'ifrs_ProfitLoss',
                           'ifrs-full_Revenue', 'ifrs-full_ProfitLoss'])]

                if txt[1] == "사업보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기', '항목명']]
                    quarter = 12
                elif txt[1] == "1분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 1분기 3개월', '항목명']]
                    quarter = 3
                elif txt[1] == "반기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 반기 3개월', '항목명']]
                    quarter = 6
                elif txt[1] == "3분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 3분기 3개월', '항목명']]
                    quarter = 9

                for index, row in temp.iterrows():
                    # print(row['종목코드'][1:-1])
                    company_code = row['종목코드'][1:-1]
                    if CompanyBase.objects.filter(code=company_code).exists():
                        company = CompanyBase.objects.get(code=company_code)
                    else:
                        company = CompanyBase.objects.create(code=company_code,
                                                             status=0)
                    XBRL, XO = XBRL_CompanyData.objects.get_or_create(company_name=company,
                                                                      year_model=txt[0],
                                                                      quarter_model=quarter,
                                                                      ifrs=True)

                    row_index = row.index

                    if row['항목코드'] in ["ifrs_Revenue", "ifrs-full_Revenue"]:
                        try:
                            XBRL.sales = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.sales = 0
                    elif row['항목코드'] == "dart_OperatingIncomeLoss":
                        try:
                            XBRL.operating_revenue = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.operating_revenue = 0
                    elif row['항목코드'] == "ifrs_ProfitLoss" or\
                            row['항목코드'] == "ifrs-full_ProfitLoss":
                        try:
                            XBRL.net_income = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.net_income = 0

                    XBRL.year_model = txt[0]

                    if txt[1] == '사업보고서':
                        XBRL.quarter_model = 12
                    elif txt[1] == '1분기보고서':
                        XBRL.quarter_model = 3
                    elif txt[1] == '반기보고서':
                        XBRL.quarter_model = 6
                    elif txt[1] == '3분기보고서':
                        XBRL.quarter_model = 9

                    XBRL.created_at = timezone.now()

                    XBRL.ratio = row['통화']

                    XBRL.gaap = False
                    XBRL.ifrs = True

                    XBRL.save()

            # 포괄손익계산서
            elif txt[2] == "03":
                # 보고서별로 뽑아낼 XBRL 라벨을 알아두어야함
                # print(reader[reader['항목코드']
                #       .isin(['ifrs_Assets', 'ifrs_Equity', 'ifrs_Liabilities'])])
                temp = reader[reader['항목코드']
                    .isin(['ifrs_Revenue', 'dart_OperatingIncomeLoss',
                           'ifrs_ProfitLoss',
                           'ifrs-full_Revenue', 'ifrs-full_ProfitLoss'])]

                if txt[1] == "사업보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기', '항목명']]
                    quarter = 12
                elif txt[1] == "1분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 1분기 3개월', '항목명']]
                    quarter = 3
                elif txt[1] == "반기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 반기 3개월', '항목명']]
                    quarter = 6
                elif txt[1] == "3분기보고서":
                    temp = temp[['회사명', '종목코드', '시장구분', '통화', '항목코드', '당기 3분기 3개월', '항목명']]
                    quarter = 9

                for index, row in temp.iterrows():
                    # print(row['종목코드'][1:-1])
                    company_code = row['종목코드'][1:-1]
                    if CompanyBase.objects.filter(code=company_code).exists():
                        company = CompanyBase.objects.get(code=company_code)
                    else:
                        company = CompanyBase.objects.create(code=company_code,
                                                             status=0)
                    XBRL, XO = XBRL_CompanyData.objects.get_or_create(company_name=company,
                                                                      year_model=txt[0],
                                                                      quarter_model=quarter,
                                                                      ifrs=True)

                    row_index = row.index

                    if row['항목코드'] in ["ifrs_Revenue", "ifrs-full_Revenue"]:
                        try:
                            XBRL.sales = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.sales = 0
                    elif row['항목코드'] == "dart_OperatingIncomeLoss":
                        try:
                            XBRL.operating_revenue = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.operating_revenue = 0
                    elif row['항목코드'] == "ifrs_ProfitLoss" or\
                            row['항목코드'] == "ifrs-full_ProfitLoss":
                        try:
                            XBRL.net_income = int(row[row_index[5]].replace(',', ''))
                        except:
                            XBRL.net_income = 0

                    XBRL.year_model = txt[0]

                    if txt[1] == '사업보고서':
                        XBRL.quarter_model = 12
                    elif txt[1] == '1분기보고서':
                        XBRL.quarter_model = 3
                    elif txt[1] == '반기보고서':
                        XBRL.quarter_model = 6
                    elif txt[1] == '3분기보고서':
                        XBRL.quarter_model = 9

                    XBRL.created_at = timezone.now()

                    XBRL.ratio = row['통화']

                    XBRL.gaap = False
                    XBRL.ifrs = True

                    XBRL.save()

            # # 현금흐름표
            # elif txt[2] == "04":
            #     if txt[4] == "연결":
            #         pass
            #     else:
            #         pass
            #
            # # 자본변동표
            # elif txt[2] == "05":
            #     if txt[4] == "연결":
            #         pass
            #     else:
            #         pass

    return HttpResponse("hello")


def common_word_inspect(request):
    all_report_list = []

    current_location = os.path.join(BASE_DIR, "Download")

    # r=>root, d=>directories, f=>files
    # Download 내의 모든 txt 파일들 이름 추출해내는 작업
    for r, d, f in os.walk(current_location):
        for item in f:
            if '.txt' in item:
                all_report_list.append(os.path.join(r, item))

    for item in all_report_list:
        print("all_report_list: ", item)

    # txt 파일들 이름은 yyyy_X분기보고서_00_재무상태표_(연결)_최종수정날짜 순으로 되어있음
    # "_" 언더바를 기준으로 Split 하여 정보들을 나누고 그를 기반으로 연도/분기별 원하는 파일만 골라냄

    gaap = []
    ifrs = []

    for report_name in all_report_list:
        splitted = report_name.split("\\")[-1]
        splitted = splitted.split("_")
        if len(splitted) == 5:
            gaap.append(splitted)
        else:
            ifrs.append(splitted)

    revenueList = []
    operatingIncomeList = []
    profitLossList = []

    assetList = []
    capitalList = []
    liabilitiesList = []

    for txt in tqdm(gaap[::-1]):
        # read CSV file & load into list
        file_path = os.path.join(current_location, "_".join(txt))
        with open(file_path, 'r') as my_file:
            reader = pandas.read_csv(my_file, delimiter='\t')
            # print(reader)
            # repr(reader)

            # 손익계산서
            if txt[2] == "02":
                temp = reader[reader['항목코드']
                    .isin(revenue_code_list + operating_income_code_list + profit_loss_code_list)]

                for index, row in temp.iterrows():

                    if row['항목코드'] in revenue_code_list:
                        if row['항목명'] not in revenueList:
                            revenueList.append(row['항목명'])
                    elif row['항목코드'] in operating_income_code_list:
                        if row['항목명'] not in operatingIncomeList:
                            operatingIncomeList.append(row['항목명'])
                    elif row['항목코드'] in profit_loss_code_list:
                        if row['항목명'] not in profitLossList:
                            profitLossList.append(row['항목명'])

            # 포괄손익계산서
            if txt[2] == "02":
                temp = reader[reader['항목코드']
                    .isin(revenue_code_list + operating_income_code_list + profit_loss_code_list)]

                for index, row in temp.iterrows():

                    if row['항목코드'] in revenue_code_list:
                        if row['항목명'] not in revenueList:
                            revenueList.append(row['항목명'])
                    elif row['항목코드'] in operating_income_code_list:
                        if row['항목명'] not in operatingIncomeList:
                            operatingIncomeList.append(row['항목명'])
                    elif row['항목코드'] in profit_loss_code_list:
                        if row['항목명'] not in profitLossList:
                            profitLossList.append(row['항목명'])

            # 대차대조표
            if txt[2] == "01":
                temp = reader[reader['항목코드']
                    .isin(asset_code_list + capital_code_list + liabilities_code_list)]

                for index, row in temp.iterrows():


                    if row['항목코드'] in asset_code_list:
                        if row['항목명'] not in assetList:
                            assetList.append(row['항목명'])

                    elif row['항목코드'] in capital_code_list:
                        if row['항목명'] not in capitalList:
                            capitalList.append(row['항목명'])

                    elif row['항목코드'] in liabilities_code_list:
                        if row['항목명'] not in liabilitiesList:
                            liabilitiesList.append(row['항목명'])

    print(revenueList)
    print(operatingIncomeList)
    print(profitLossList)
    print(assetList)
    print(capitalList)
    print(liabilitiesList)

    word_list_1 = [revenueList, operatingIncomeList, profitLossList]
    word_list_2 = [assetList, capitalList, liabilitiesList]

    revenueList_code = []
    operatingIncomeList_code = []
    profitLossList_code = []

    assetList_code = []
    capitalList_code = []
    liabilitiesList_code = []

    code_list_1 = [revenueList_code, operatingIncomeList_code, profitLossList_code]
    code_list_2 = [assetList_code, capitalList_code, liabilitiesList_code]

    for txt in tqdm(gaap[::-1]):
        # read CSV file & load into list
        file_path = os.path.join(current_location, "_".join(txt))
        with open(file_path, 'r') as my_file:
            reader = pandas.read_csv(my_file, delimiter='\t')
            # print(reader)
            # repr(reader)

            # 손익계산서
            if txt[2] == "02":
                for i in range(len(code_list_1)):
                    temp = reader[reader['항목명']
                        .isin(word_list_1[i])]
                    for index, row in temp.iterrows():
                        if row['항목코드'] not in code_list_1[i]:
                            code_list_1[i].append(row['항목코드'])

            # 손익계산서
            if txt[2] == "03":
                for i in range(len(code_list_1)):
                    temp = reader[reader['항목명']
                        .isin(word_list_1[i])]
                    for index, row in temp.iterrows():
                        if row['항목코드'] not in code_list_1[i]:
                            code_list_1[i].append(row['항목코드'])

            # 대차대조표
            if txt[2] == "01":
                for i in range(len(code_list_2)):
                    temp = reader[reader['항목명']
                        .isin(word_list_2[i])]
                    for index, row in temp.iterrows():
                        if row['항목코드'] not in code_list_2[i]:
                            code_list_2[i].append(row['항목코드'])

    for x in range(len(code_list_1)):
        print('\n=================================\n')
        for y in range(len(code_list_1[x])):
            print(code_list_1[x][y])

    print('\n=================================\n')

    for x in range(len(code_list_2)):
        print('\n=================================\n')
        for y in range(len(code_list_2[x])):
            print(code_list_2[x][y])


    for txt in tqdm(ifrs[::-1]):
        # read CSV file & load into list
        file_path = os.path.join(current_location, "_".join(txt))
        with open(file_path, 'r') as my_file:
            reader = pandas.read_csv(my_file, delimiter='\t')
            # print(reader)
            # repr(reader)

            # 손익계산서
            if txt[2] == "02":
                temp = reader[reader['항목코드']
                    .isin(['ifrs_Revenue', 'dart_OperatingIncomeLoss', 'ifrs_ProfitLoss',
                           'ifrs-full_Revenue', 'ifrs-full_ProfitLoss'])]

                for index, row in temp.iterrows():

                    if row['항목코드'] == "ifrs_Revenue" or \
                            row['항목코드'] == "ifrs-full_Revenue":
                        if row['항목명'] not in revenueList:
                            revenueList.append(row['항목명'])
                    elif row['항목코드'] == "dart_OperatingIncomeLoss":
                        if row['항목명'] not in operatingIncomeList:
                            operatingIncomeList.append(row['항목명'])
                    elif row['항목코드'] == "ifrs_ProfitLoss" or \
                            row['항목코드'] == "ifrs-full_ProfitLoss":
                        if row['항목명'] not in profitLossList:
                            profitLossList.append(row['항목명'])

            # 손익계산서
            if txt[2] == "03":
                temp = reader[reader['항목코드']
                    .isin(['ifrs_Revenue', 'dart_OperatingIncomeLoss', 'ifrs_ProfitLoss',
                           'ifrs-full_Revenue', 'ifrs-full_ProfitLoss'])]

                for index, row in temp.iterrows():

                    if row['항목코드'] == "ifrs_Revenue" or \
                            row['항목코드'] == "ifrs-full_Revenue":
                        if row['항목명'] not in revenueList:
                            revenueList.append(row['항목명'])
                    elif row['항목코드'] == "dart_OperatingIncomeLoss":
                        if row['항목명'] not in operatingIncomeList:
                            operatingIncomeList.append(row['항목명'])
                    elif row['항목코드'] == "ifrs_ProfitLoss" or \
                            row['항목코드'] == "ifrs-full_ProfitLoss":
                        if row['항목명'] not in profitLossList:
                            profitLossList.append(row['항목명'])

            # 대차대조표
            if txt[2] == "01":
                temp = reader[reader['항목코드']
                    .isin(['ifrs_Assets', 'ifrs_Equity', 'ifrs_Liabilities',
                           'ifrs-full_Assets', 'ifrs-full_Equity', 'ifrs-full_Liabilities'])]

                for index, row in temp.iterrows():

                    row_index = row.index

                    if row['항목코드'] == "ifrs_Assets" or row['항목코드'] == "ifrs-full_Assets":
                        if row['항목명'] not in assetList:
                            assetList.append(row['항목명'])

                    elif row['항목코드'] == "ifrs_Equity" or row['항목코드'] == "ifrs-full_Equity":
                        if row['항목명'] not in capitalList:
                            capitalList.append(row['항목명'])

                    elif row['항목코드'] == "ifrs_Liabilities" or row['항목코드'] == "ifrs-full_Liabilities":
                        if row['항목명'] not in liabilitiesList:
                            liabilitiesList.append(row['항목명'])

    print("\n\n")
    print(revenueList)
    print(operatingIncomeList)
    print(profitLossList)
    print(assetList)
    print(capitalList)
    print(liabilitiesList)

    word_list_1 = [revenueList, operatingIncomeList, profitLossList]
    word_list_2 = [assetList, capitalList, liabilitiesList]

    revenueList_code = []
    operatingIncomeList_code = []
    profitLossList_code = []

    assetList_code = []
    capitalList_code = []
    liabilitiesList_code = []

    code_list_1 = [revenueList_code, operatingIncomeList_code, profitLossList_code]
    code_list_2 = [assetList_code, capitalList_code, liabilitiesList_code]

    for txt in tqdm(ifrs[::-1]):
        # read CSV file & load into list
        file_path = os.path.join(current_location, "_".join(txt))
        with open(file_path, 'r') as my_file:
            reader = pandas.read_csv(my_file, delimiter='\t')
            # print(reader)
            # repr(reader)

            # 손익계산서
            if txt[2] == "02":
                for i in range(len(code_list_1)):
                    temp = reader[reader['항목명']
                        .isin(word_list_1[i])]
                    for index, row in temp.iterrows():
                        if row['항목코드'] not in code_list_1[i]:
                            code_list_1[i].append(row['항목코드'])

            # 포괄손익계산서
            if txt[2] == "03":
                for i in range(len(code_list_1)):
                    temp = reader[reader['항목명']
                        .isin(word_list_1[i])]
                    for index, row in temp.iterrows():
                        if row['항목코드'] not in code_list_1[i]:
                            code_list_1[i].append(row['항목코드'])

            # 대차대조표
            if txt[2] == "01":
                for i in range(len(code_list_2)):
                    temp = reader[reader['항목명']
                        .isin(word_list_2[i])]
                    for index, row in temp.iterrows():
                        if row['항목코드'] not in code_list_2[i]:
                            code_list_2[i].append(row['항목코드'])

    for x in range(len(code_list_1)):
        print('\n=================================\n')
        for y in range(len(code_list_1[x])):
            print(code_list_1[x][y])

    print('\n=================================\n')

    for x in range(len(code_list_2)):
        print('\n=================================\n')
        for y in range(len(code_list_2[x])):
            print(code_list_2[x][y])

    return HttpResponse("hello")


def common_word_inspect_reverse(request):
    all_report_list = []

    current_location = os.path.join(BASE_DIR, "Download")

    # r=>root, d=>directories, f=>files
    # Download 내의 모든 txt 파일들 이름 추출해내는 작업
    for r, d, f in os.walk(current_location):
        for item in f:
            if '.txt' in item:
                all_report_list.append(os.path.join(r, item))

    for item in all_report_list:
        print("all_report_list: ", item)

    # txt 파일들 이름은 yyyy_X분기보고서_00_재무상태표_(연결)_최종수정날짜 순으로 되어있음
    # "_" 언더바를 기준으로 Split 하여 정보들을 나누고 그를 기반으로 연도/분기별 원하는 파일만 골라냄

    gaap = []
    ifrs = []

    for report_name in all_report_list:
        splitted = report_name.split("\\")[-1]
        splitted = splitted.split("_")
        if len(splitted) == 5:
            gaap.append(splitted)
        else:
            ifrs.append(splitted)

    revenueList = []
    operatingIncomeList = []
    profitLossList = []

    assetList = []
    capitalList = []
    liabilitiesList = []

    for txt in tqdm(gaap[::-1]):
        # read CSV file & load into list
        file_path = os.path.join(current_location, "_".join(txt))
        with open(file_path, 'r') as my_file:
            reader = pandas.read_csv(my_file, delimiter='\t')
            # print(reader)
            # repr(reader)

            # 손익계산서
            if txt[2] == "02":
                temp = reader[reader['항목명']
                    .isin(revenue_word_list_gaap + operating_income_word_list_gaap + profit_loss_word_list_gaap)]

                for index, row in temp.iterrows():

                    if row['항목명'] in revenue_word_list_gaap:
                        if row['항목코드'] not in revenueList:
                            revenueList.append(row['항목코드'])
                    elif row['항목명'] in operating_income_word_list_gaap:
                        if row['항목코드'] not in operatingIncomeList:
                            operatingIncomeList.append(row['항목코드'])
                    elif row['항목명'] in profit_loss_word_list_gaap:
                        if row['항목코드'] not in profitLossList:
                            profitLossList.append(row['항목코드'])

            # 포괄손익계산서
            if txt[2] == "03":
                temp = reader[reader['항목명']
                    .isin(
                    revenue_word_list_gaap + operating_income_word_list_gaap + profit_loss_word_list_gaap)]

                for index, row in temp.iterrows():

                    if row['항목명'] in revenue_word_list_gaap:
                        if row['항목코드'] not in revenueList:
                            revenueList.append(row['항목코드'])
                    elif row['항목명'] in operating_income_word_list_gaap:
                        if row['항목코드'] not in operatingIncomeList:
                            operatingIncomeList.append(row['항목코드'])
                    elif row['항목명'] in profit_loss_word_list_gaap:
                        if row['항목코드'] not in profitLossList:
                            profitLossList.append(row['항목코드'])

            # 대차대조표
            if txt[2] == "01":
                temp = reader[reader['항목명']
                    .isin(asset_word_list_gaap + capital_word_list_gaap + liabilities_word_list_gaap)]

                for index, row in temp.iterrows():

                    if row['항목명'] in asset_word_list_gaap:
                        if row['항목코드'] not in assetList:
                            assetList.append(row['항목코드'])

                    elif row['항목명'] in capital_word_list_gaap:
                        if row['항목코드'] not in capitalList:
                            capitalList.append(row['항목코드'])

                    elif row['항목명'] in liabilities_word_list_gaap:
                        if row['항목코드'] not in liabilitiesList:
                            liabilitiesList.append(row['항목코드'])

    for x in range(len(revenueList)) : print(revenueList[x])
    print('\n\n=========================================\n\n')
    for x in range(len(operatingIncomeList)): print(operatingIncomeList[x])
    print('\n\n=========================================\n\n')
    for x in range(len(profitLossList)): print(profitLossList[x])
    print('\n\n=========================================\n\n')
    for x in range(len(assetList)): print(assetList[x])
    print('\n\n=========================================\n\n')
    for x in range(len(capitalList)): print(capitalList[x])
    print('\n\n=========================================\n\n')
    for x in range(len(liabilitiesList)): print(liabilitiesList[x])
    print('\n\n=========================================\n\n')


    return HttpResponse("hello")