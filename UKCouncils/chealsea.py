import requests
import json
from config import abbrev_mappings, CHELSEA_COUNCIL_WARDS
from mongo_utils import database
from lxml import etree, html
from selectolax.parser import HTMLParser
from useragents import USER_AGENTS
import random
import os
import re
from pprint import pprint
from httpx import AsyncClient
import asyncio
import time


headers = {
	"authority": "www.rbkc.gov.uk",
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
	"adv":1,
	"ward":"Abingdon",
	"batch":9999,
	"pgapp":1
}


class KensingtonChelseaCouncil:
	def __init__(self):
		self.planning_applications_search_url = "https://www.rbkc.gov.uk/planning/searches/default.aspx"
		self.params = params
		self.headers = headers
		self.collectionName = "kensington_chelsea_council"
		self.headers = headers
		self.wards = CHELSEA_COUNCIL_WARDS
		self.database = database
		self.failedPages = "ChelseaDebugFailedPages"
		self.collection = self.database[self.collectionName]
		if not os.path.exists(self.failedPages):
			os.mkdir(self.failedPages)

	async def sendWardRequest(self, ward):
		self.params["ward"] = ward
		self.headers['user-agent'] = self.random_useragent()
		response = requests.get(self.planning_applications_search_url, params=self.params, headers=self.headers)
		htmlParser = HTMLParser(response.text)
		async with AsyncClient() as client:
			links = [self.getApplicationDetails(client,f"https://www.rbkc.gov.uk/planning/searches/{node.attributes.get('href')}") for node in htmlParser.css("div #tabs-planning-1 tbody tr > td >a[href^='details.aspx']")]
			chunk = 10
			for i in range(0,len(links),chunk):
				linkRange = links[i:i+chunk]
				await asyncio.gather(*linkRange)
				print("waiting before sending another batch ...")
				time.sleep(5)
				print("done waiting...")
	async def scrapeWards(self):
		for count,ward in enumerate(self.wards):
			print(f"Scraping Ward [{count}/{len(self.wards)}]")
			await self.sendWardRequest(ward)
	async def getApplicationDetails(self, client,link):
		headers = self.headers.copy()
		headers['user-agent'] = self.random_useragent()
		response = await client.get(link,headers = headers)
		result = response.read()
		htmlParser = HTMLParser(result)

		try:
			propertyDetails = htmlParser.css_first("#property-details > tbody")
			propertyDetailsRows = propertyDetails.css("tr")
		except:
			pass

		try:
			applicantDetails = htmlParser.css_first("#applicant-details > tbody")
		except:
			pass
		# applicantDetailsRows = applicantDetails.css("tr")

		try:
			proposalDetailsRows = htmlParser.css("#proposal-details > tbody tr")
		except:
			pass

		caseReference = ""
		address = ""
		ward = ""
		pollingDistrict = ""
		listedBuildingGrade = ""
		conservationArea = ""

		applicantName = ""
		applicantCompanyName = ""
		contactAddress = ""

		applicationType = ""
		proposedDevelopment = ""
		dateReceived = ""
		registrationDate = ""
		publicConsultationEnds = ""
		applicationStatus = ""
		targetDecisionDate = ""


		for row in propertyDetailsRows:
			try:
				key,value = row.text().replace("\n","").replace("\t","").strip().split(":",1)
				key = key.strip().lower()
				value = value.strip()
				if key == "case reference":
					caseReference = value
				elif key == "address":
					address = value
				elif key == "ward":
					ward = value
				elif key == "polling district":
					pollingDistrict = value
				elif key == "listed building grade":
					listedBuildingGrade = value
				elif key == "conservation area":
					conservationArea = value
			except Exception as error:
				print(f"Error handler 1:{error}")
				if response.status_code != 200:
					print("Bot Blocked ! Saving Page ..")
					self.save_to_html(response.read().decode('utf-8'))
					exit()

		try:
			applicantName,applicantCompanyName,contactAddress = [" ".join(data.text().strip().split()) for data in applicantDetails.css("td")]
		except Exception as error:
			print(f"Exception Handler 2:{error}")

		for row in proposalDetailsRows:
			try:
				key,value = row.text().replace("\n","").replace("\t","").strip().split(":",1)
				key:str = key.strip().lower()
				value = value.strip()
				if key == "application type":
					applicationType = value
				elif key == "proposed development":
					proposedDevelopment = value
				elif key == "date received":
					dateReceived = value
				elif key.startswith("registration date"):
					registrationDate = value
				elif key == "public consultation ends":
					publicConsultationEnds = value
				elif key == "application status":
					applicationStatus = value
				elif key == "target date for decision":
					targetDecisionDate = value
			except Exception as error:
				print(f"Error handler 3:{error}")

		decisionDetailsRows = htmlParser.css("#decision-details > tbody tr")
		decisionDetails = {}
		for row in decisionDetailsRows:
			try:
				decisionDetails[" ".join(row.css_first("th").text().strip().split())] = " ".join(row.css_first("td").text().strip().split())
			except Exception as error:
				print(f"Exception Handler 4: {error}")

		committeeDetailsRows = htmlParser.css("#committee-details > tbody tr")
		commiteeDetails = {}
		for row in committeeDetailsRows:
			try:
				commiteeDetails[" ".join(row.css_first("th").text().strip().split())] = " ".join(row.css_first("td").text().strip().split())
			except Exception as error:
				print(f"Exception Handler 5: {error}")

		appealDetailsRows = htmlParser.css("#appeal-details > tbody tr")
		appealDetails = {}
		for row in appealDetailsRows:
			try:
				appealDetails[" ".join(row.css_first("th").text().strip().split())] = " ".join(
					row.css_first("td").text().strip().split())
			except Exception as error:
				print(f"Exception Handler 6: {error}")

		contactDetailsRows = htmlParser.css("#planning-dept-contact > tbody tr")
		contactDetails = {}
		for row in contactDetailsRows:
			try:
				contactDetails[" ".join(row.css_first("th").text().strip().split())] = " ".join(row.css_first("td").text().strip().split())
			except Exception as error:
				print(f"Exception Handler 7:{error}")

		applicationDetails = {
			"caseReference":caseReference,
			"address":address,
			"ward":ward,
			"pollingDistrict":pollingDistrict,
			"listedBuildingGrade":listedBuildingGrade,
			"conservationArea":conservationArea,
			"applicantName":applicantName,
			"applicantCompanyName":applicantCompanyName,
			"contactAddress":contactAddress,
			"applicationType":applicationType,
			"proposedDevelopment":proposedDevelopment,
			"dateReceived":dateReceived,
			"registrationDate":registrationDate,
			"publicConsultationEnds":publicConsultationEnds,
			"applicationStatus":applicationStatus,
			"targetDecisionDate":targetDecisionDate,
			"decisionDetails":decisionDetails,
			"committeeDetails":commiteeDetails,
			"contactDetails":contactDetails,
			"appealDetails":appealDetails
		}
		pprint(applicationDetails)
		# TODO // Implement Storing data in mongodb collection

	def random_useragent(self):
		return random.choice(USER_AGENTS)

	def save_to_html(self,html_string,filename="responses/response.html"):
		with open(filename,"w") as save:
			save.write(html_string)

kensingtonChelseaCouncil = KensingtonChelseaCouncil()
asyncio.run(kensingtonChelseaCouncil.scrapeWards())

