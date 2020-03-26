from django.db import models

# Create your models here.


# 기본 기업 정보 모델
class CompanyBase(models.Model):
    company_name = models.CharField(max_length=255, null=True, blank=True, name='company_name')
    code = models.CharField(max_length=255, null=True, blank=True, name='code', unique=True)
    country = models.CharField(max_length=255, null=True, blank=True, name='country')
    market = models.CharField(max_length=255, null=True, blank=True, name='market')
    status = models.IntegerField()

    base_currency = models.CharField(max_length=255, null=True, blank=True)


# 다국어 지원용 국가별 이름 모델
class CompanyNameGlobal(models.Model):
    kr = models.CharField(max_length=255, null=True, blank=True)
    en = models.CharField(max_length=255, null=True, blank=True)

    company_name = models.OneToOneField(CompanyBase,
                                        on_delete=models.CASCADE,
                                        null=True,
                                        name='company_name')


# 기업별 정보 모델
class CompanyData(models.Model):
    company_name = models.ForeignKey(CompanyBase,
                                     on_delete=models.CASCADE,
                                     null=True,
                                     name='company_name')
    year_model = models.IntegerField(null=True)
    quarter_model = models.IntegerField(null=True)

    asset = models.BigIntegerField(null=True)
    capital = models.BigIntegerField(null=True)
    liabilities = models.BigIntegerField(null=True)

    sales = models.BigIntegerField(null=True)
    operating_revenue = models.BigIntegerField(null=True)
    net_income = models.BigIntegerField(null=True)

    total_share = models.BigIntegerField(null=True)
    foreigner_share = models.BigIntegerField(null=True)

    quarter_check = models.BooleanField(default=False)

    # ratio = models.TextField(null=True, max_length=1500)
    ratio_count = models.IntegerField(null=True)
    ratio_found = models.BooleanField(null=True)
    ratio_unity = models.BooleanField(null=True)

    market_code = models.CharField(null=True, max_length=10)

    created_at = models.DateTimeField(null=True)

    ifrs = models.BooleanField(null=True)
    gaap = models.BooleanField(null=True)

    verified = models.BooleanField(default=False)


# 기업별 정보 모델
class XBRL_CompanyData(models.Model):
    company_name = models.ForeignKey(CompanyBase,
                                     on_delete=models.CASCADE,
                                     null=True,
                                     name='company_name')
    year_model = models.IntegerField(null=True)
    quarter_model = models.IntegerField(null=True)

    asset = models.BigIntegerField(null=True)
    capital = models.BigIntegerField(null=True)
    liabilities = models.BigIntegerField(null=True)

    sales = models.BigIntegerField(null=True)
    operating_revenue = models.BigIntegerField(null=True)
    net_income = models.BigIntegerField(null=True)

    total_share = models.BigIntegerField(null=True)
    foreigner_share = models.BigIntegerField(null=True)

    quarter_check = models.BooleanField(default=False)

    # ratio = models.TextField(null=True, max_length=1500)
    ratio_count = models.IntegerField(null=True)
    ratio_found = models.BooleanField(null=True)
    ratio_unity = models.BooleanField(null=True)

    market_code = models.CharField(null=True, max_length=10)

    created_at = models.DateTimeField(null=True)

    ifrs = models.BooleanField(null=True)
    gaap = models.BooleanField(null=True)

    verified = models.BooleanField(default=False)


class XBRLVerify(models.Model):
    quarter_model = models.IntegerField()
    year_model = models.IntegerField()

    error = models.BooleanField(null=True)
    error_code = models.IntegerField(null=True)
    created_at = models.DateTimeField()

    edited_at = models.DateTimeField(null=True)