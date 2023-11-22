from config import HOUNSLOW_COUNCIL_WARDS,SCRAPED_HOUNSLOW_COUNCIL_WARDS
from mongo_utils import database, statusDatabase
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
from urllib.parse import urlencode, urlparse

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


class HounslowCouncil:
	def __init__(self):
		self.planning_applications_search_url = "https://planning.hounslow.gov.uk/planning_summary.aspx"
		self.params = params
		self.headers = headers
		self.cookies = cookies
		self.collectionName = "hounslow_council"
		self.database = database
		self.failedPages = "hounslowDebugFailedPages"
		self.collection = self.database[self.collectionName]
		self.scrapingStatus = statusDatabase
		self.statusCollection = self.scrapingStatus[self.collectionName + "_status"]
		if not os.path.exists(self.failedPages):
			os.mkdir(self.failedPages)

	def sendWardRequest(self, driver, ward):
		# fullUrl = f"{self.planning_applications_search_url}{urlencode(self.params)}"
		driver.get("https://planning.hounslow.gov.uk/Planning_Search_Advanced.aspx")
		wardsDropDown = Select(driver.find_element(By.ID, "MainContent_ddWard"))
		wardsDropDown.select_by_visible_text(ward)
		searchButton = driver.find_element(By.ID, "MainContent_btn_Search")
		searchButton.click()
		htmlParser = HTMLParser(driver.page_source)
		planningApplicationsLinks = []
		planningApplicationsLinks.extend([f"https://planning.hounslow.gov.uk/{node.attributes.get('href')}" for node in
		                                  htmlParser.css("a[href^='Planning_CaseNo']")])

		try:
			totalApplications = htmlParser.css_first('#MainContent_RecordCountLabel').text()
		except seleniumExceptions.NoSuchElementException:
			pass
		if totalApplications.isdigit():
			totalApplications = int(totalApplications)
		else:
			totalApplications = 0

		scrape = True
		page = 1
		while scrape:
			# Get Link for next page

			try:
				nextPageButton = driver.find_element(By.ID, "MainContent_NextLink")
				nextPageButton.click()
				page += 1
				htmlParser = HTMLParser(driver.page_source)
				planningApplicationsLinks.extend(
						[f"https://planning.hounslow.gov.uk/{node.attributes.get('href')}" for node in
						 htmlParser.css("a[href^='Planning_CaseNo']")])

			except seleniumExceptions.NoSuchElementException:
				scrape = False
		print(
				f"Scraped {page} pages| Scraped {len(planningApplicationsLinks)} and found max results to be {totalApplications}",
				end="\n")

		for applicationLink in planningApplicationsLinks:
			self.scrapeApplicationDetails(driver, applicationLink)

		self.statusCollection.update_one({"ward":ward},{"$set":{"status":"scraped"}})

	def scrapeWards(self):
		options = Options()
		options.add_argument("--start-maximized")
		options.add_argument('--no-sandbox')
		options.add_argument('--headless')
		options.add_argument('--disable-gpu')
		options.add_argument('--window-size=1920x1080')
		driver = Chrome(options=options, version_main=109)
		driver.get(
			"https://planning.hounslow.gov.uk/planning_summary.aspx?strWeekListType=SRCH&strStreet=ALL&strStreetTxt=---&strWard=00AJ&strWardTxt=Ealing%20(adjacent%20Borough)&strArea=ALL&strAreaTxt=---&strAppTyp=ALL&strAppTypTxt=All%20Application%20Types")
		try:
			tncButton = driver.find_element(By.ID, "MainContent_btn_AcceptTnC")
			tncButton.click()
			time.sleep(10)
			while True:
				scraped_wards, unscraped_wards = self.load_wards()
				if not unscraped_wards:
					break
				random_unscraped_ward = random.choice(unscraped_wards)['ward']
				print(f"Scraping Ward [{len(scraped_wards)}/{len(scraped_wards)+len(unscraped_wards)}] => {random_unscraped_ward}")
				self.sendWardRequest(driver, random_unscraped_ward)

		except seleniumExceptions.NoSuchElementException:
			print("An error occurred ! Restarting...")
			self.scrapeWards()

	def scrapeApplicationDetails(self, driver, applicationLink):
		address = ""
		proposal = ""
		applicationType = ""
		typeCode = ""
		status = ""
		date = ""
		systemReference = ""
		planningReference = ""
		ward = ""
		planningOfficer = ""
		applicationReceived = ""
		applicationAccepted = ""
		decision = ""
		initialStatus = ""
		decisionIssued = ""
		expiryDate = ""

		driver.get(applicationLink)
		htmlParser = HTMLParser(driver.page_source)
		caseNoFormatted = urlparse(applicationLink).query.split("=")[1].replace("/", "-")

		try:
			address = htmlParser.css_first('#MainContent_lbl_site_description').text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			proposal = htmlParser.css_first('#MainContent_lbl_Proposal').text()

		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			applicationType = htmlParser.css_first("#MainContent_lbl_App_Type").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			typeCode = htmlParser.css_first("#MainContent_lbl_app_type_code").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			status = htmlParser.css_first("#MainContent_lbl_Status").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			date = htmlParser.css_first("#MainContent_lbl_Date_Valid").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			systemReference = htmlParser.css_first("#MainContent_lbl_system_reference").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			planningReference = htmlParser.css_first("#MainContent_lbl_planning_reference").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			ward = htmlParser.css_first("#MainContent_lbl_Ward").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			planningOfficer = htmlParser.css_first("#MainContent_lbl_Officer").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			applicationReceived = htmlParser.css_first("#MainContent_lbl_RECEIVEDDATE").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			applicationAccepted = htmlParser.css_first("#MainContent_lbl_VALIDDATE").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			initialStatus = htmlParser.css_first("#MainContent_lbl_COMMDATETYPE").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			decision = htmlParser.css_first("#MainContent_lbl_Decision").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			decisionIssued = htmlParser.css_first("#MainContent_lbl_DECISIONNOTICESENTDATE").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		try:
			expiryDate = htmlParser.css_first("#MainContent_lbl_Temp_Expiry_Date").text()
		except AttributeError:
			with open(f"{self.failedPages}/{caseNoFormatted}.html", "w") as failedP:
				failedP.write(driver.page_source)

		data = {
			"address": address,
			"proposal": proposal,
			"applicationType": applicationType,
			"typeCode": typeCode,
			"status": status,
			"date": date,
			"systemReference": systemReference,
			"planningReference": planningReference,
			"ward": ward,
			"planningOfficer": planningOfficer,
			"applicationReceived": applicationReceived,
			"applicationAccepted": applicationAccepted,
			"initialStatus": initialStatus,
			"decision": decision,
			"decisionIssued": decisionIssued,
			"expiryDate": expiryDate
		}

		self.collection.insert_one(data)

	def load_wards(self):
		scraped_wards = list(self.statusCollection.find({"status":"scraped"}))
		unscraped_wards = list(self.statusCollection.find({"status":"unscraped"}))
		return scraped_wards,unscraped_wards

	def save_wards_to_mongodb(self):
		for ward in SCRAPED_HOUNSLOW_COUNCIL_WARDS:
			self.statusCollection.insert_one({
				"ward": ward,
				"status": "scraped"
			})
		print("Done1")

		for ward in HOUNSLOW_COUNCIL_WARDS:
			self.statusCollection.insert_one({
				"ward": ward,
				"status": "unscraped"
			})
		print("Done2")

	def random_useragent(self):
		return random.choice(USER_AGENTS)


hounslowCouncil = HounslowCouncil()
hounslowCouncil.scrapeWards()