from config import HOUNSLOW_COUNCIL_WARDS
from mongo_utils import database
from selectolax.parser import HTMLParser
from useragents import USER_AGENTS
import random
import os
import re
import time
from pprint import pprint
from undetected_chromedriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common import exceptions as seleniumExceptions
from selenium.webdriver.support.ui import Select
from urllib.parse import urlencode,urlparse


headers = {
	"method": "GET",
	"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
	"accept-encoding": "gzip, deflate, br",
	"accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
	"cache-control": "no-cache",
	# "cookie": 'sessionidPreLive26=2v3wl41i24siorxgd2h2gegl; CookieControl={"necessaryCookies":["UMB*","OpenIdConnect*","ARRAffinity"],"optionalCookies":{"analytics":"accepted","Marketing":"accepted"},"statement":{},"consentDate":1676407618702,"consentExpiry":90,"interactedWith":true,"user":"711856A6-6CBD-42BF-B919-DDE749B2939D"}; nmstat=1d99739a-b8b2-a868-1f20-26f4d6218790; ASP.NET_SessionId=uutmt0c0bjosxl1t1ert4dpl',
	"upgrade-insecure-requests": "1",
	"user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
}

params = {
	"strWeekListType": "SRCH",
	"strStreet": "ALL",
	"strStreetTxt": "---",
	"strWard": "00ATGF",
	"strWardTxt": "Hanworth",
	"strArea": "ALL",
	"strAreaTxt": "---",
	"strAppTyp": "ALL",
	"strAppTypTxt": "All Applications Types",
}

cookies = {
    "LBHSupportCookies": "true",
    " _ga": "GA1.3.799084166.1676131194",
    " _ga_SN6XMPNNGG": "GS1.1.1676131193.1.1.1676131318.0.0.0",
    " LBHPlanningAccept": "[i|jmN;:Âilz}|i[Nmjz}izÂ"
}


class HaringeyCouncil:
	def __init__(self):
		self.planning_applications_search_url = "https://planning.hounslow.gov.uk/planning_summary.aspx"
		self.params = params
		self.headers = headers
		self.cookies = cookies
		self.collectionName = "haringey_council"
		# self.abbrev_mappings = abbrev_mappings
		self.wards = HOUNSLOW_COUNCIL_WARDS
		self.database = database
		self.failedPages = "haringeyDebugFailedPages"
		self.collection = self.database[self.collectionName]
		if not os.path.exists(self.failedPages):
			os.mkdir(self.failedPages)


	def random_useragent(self):
		return random.choice(USER_AGENTS)

haringeyCouncil = HaringeyCouncil()

