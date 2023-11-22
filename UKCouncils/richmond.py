import requests
import json
from config import abbrev_mappings, RICHMOND_COUNCIL_WARDS
from mongo_utils import database
from lxml import etree, html
from selectolax.parser import HTMLParser
from useragents import USER_AGENTS
import random
import os
import re
from pprint import pprint

headers = {
	"authority": "www2.richmond.gov.uk",
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
	"strWard": "WTK",
	"strAppTyp": "ALL",
	"strWardTxt": "WEST TWICKENHAM WARD",
	"strAppTypTxt": "ALL-all applications",
	"strAppStat": "DEC",
	"strAppStarTxt": "Only applications that are decided",
	"strLimit": 10000,
	"strOrder": "REC_DEC",
	"strOrderText": "Most recently received first"
}


class RichmondCouncil:
	def __init__(self):
		self.planning_applications_search_url = "https://www2.richmond.gov.uk/PlanData2/planning_summary.aspx"
		self.params = params
		self.headers = headers
		self.collectionName = "richmond_council"
		self.headers = headers
		# self.abbrev_mappings = abbrev_mappings
		self.wards = RICHMOND_COUNCIL_WARDS
		self.database = database
		self.failedPages = "DebugFailedPages"
		self.collection = self.database[self.collectionName]
		if not os.path.exists(self.failedPages):
			os.mkdir(self.failedPages)

	def sendWardRequest(self, ward_code, ward_name):
		self.params["strWard"] = ward_code
		self.params["strWardTxt"] = ward_name
		self.headers['user-agent'] = self.random_useragent()
		response = requests.get(self.planning_applications_search_url, params=self.params, headers=self.headers)
		htmlParser = HTMLParser(response.text)
		for application in htmlParser.css("ul.planning-apps > li"):
			address = application.css_first("h3").text().strip().replace("\n", " ")
			caseNo, description, _ = [ap.text().strip() for ap in application.css("p")]
			self.getApplicationDetails(ward_name, address, description, caseNo)

	# Make Request to get application details

	def scrapeWards(self):
		for count, (code, ward) in enumerate(self.wards.items()):
			print(f"Scraping Ward [{count}/{len(self.wards)}]")
			self.sendWardRequest(ward_code=code, ward_name=ward)

	def getApplicationDetails(self, ward, address, proposal, caseNo):
		proposal = proposal.replace("\n", " ").replace("\t", " ")
		planningApplicationDetailsLink = f"https://www2.richmond.gov.uk/PlanData2/Planning_CASENO_Noindex.aspx?strCASENO={caseNo}"
		self.headers['user-agent'] = self.random_useragent()

		try:
			response = requests.get(planningApplicationDetailsLink, headers=self.headers)
			parser = HTMLParser(response.text)
		except Exception as error:
			print(f"Exception Occurred: {error}")
			return
		permission_date = ""
		latest = ""
		level = ""
		_type = ""
		applicant_name = ""
		applicant_address = ""
		agent = ""
		officer = ""

		try:
			permission_date = parser.css_first("#ctl00_PageContent_lbl_Status").text().split(" ", 2)[2].replace(
				"the Applicant", "")
		except:
			pass
		try:
			latest = parser.css_first(
					"#aspnetForm > div:nth-of-type(4) > div > div:nth-of-type(2) > div > p:nth-of-type(2) > a").text()
		except:
			pass
		try:
			level = parser.css_first("#ctl00_PageContent_lbl_Dec_Level").text().strip()
		except:
			pass
		try:
			applicant_name = parser.css_first("#ctl00_PageContent_lbl_Applic_Name").text().strip()
		except:
			pass
		try:
			applicant_address = parser.css_first("#ctl00_PageContent_lbl_Applic_Address").text().strip().replace("\n",
			                                                                                                     " ")
		except:
			pass

		textLines = []
		try:
			textLines = parser.css_first(
					"#aspnetForm > div:nth-of-type(5) > div > div:nth-of-type(2) > div").text().splitlines()
		except:
			print("Falied here ... Saving html page..")
			with open(
					f'{self.failedPages}/FailedSavedPage_@Ward-{ward.replace("/", "-")}|@caseNo-{caseNo.replace("/", "--")}.html',
					"w") as failed_log:
				failed_log.write(response.text)
			print("Done!.Moving on!")

		for i, line in enumerate(textLines):
			lineText = line.strip().lower()
			if lineText == "type":
				_type = textLines[i + 1]
			elif lineText == 'officer':
				officer = textLines[i + 1].strip()
			elif lineText == "agent":
				cut = textLines[i + 1:]
				agent_str = []
				for item in cut:
					item = item.strip()
					if item == "Officer":
						break
					agent_str.append(item)
				agent = agent_str
				agent = " ".join([t.strip() for t in agent if t.strip()])
		application_received, validated, decision_issued = "", "", ""
		try:
			application_received, validated, decision_issued = [text.text().split(":")[1].strip() for text in
			                                                    parser.css(
					                                                    "#aspnetForm > div:nth-of-type(5) > div > div:nth-of-type(5) > div > ul > li")]
		except:
			pass
		application = {
			"ward": ward,
			"case_no": caseNo,
			"site_address": address,
			"status": {
				"granted_permission": permission_date,
				"latest": latest,
				"level": level
			},
			"proposal": proposal,
			"type": _type,
			"applicant_name": applicant_name,
			"applicant_address": applicant_address,
			"agent": agent,
			"officer": officer,
			"application_received": application_received,
			"validated": validated,
			"decision_issued": decision_issued
		}
		self.collection.insert_one(application)

	def update_broken_applications(self):
		# Load html files
		""" This method fixes all applications which were not scrapped correctly ."""
		caseNoWards = []

		files = os.listdir(self.failedPages)
		print("Fixing applications ..")

		for i,file in enumerate(files):
			full_path = f"{self.failedPages}/{file}"
			with open(full_path, "r") as fileHandler:
				pattern = re.compile(r"[0-9]{2}-[0-9]{2}-[0-9]{2}")
				parser = HTMLParser(fileHandler.read())
				_, wardDirty, caseNoDirty = file.split("@")
				caseNo = caseNoDirty.split("-", 1)[1].replace(".html", "").replace("--", "/")
				wardClean = wardDirty.split("-", 1)[1].strip("|")
				first_found = pattern.findall(wardClean)
				if first_found:
					first_found = first_found[0]
					ward = wardClean.replace(first_found,first_found.replace("-","/"))
				else:
					ward = wardClean
				print(f"Fixing application [{i+1}/{len(files)}] ward={ward} and caseNo={caseNo}")
				try:
					textLines = parser.css_first("#aspnetForm > .infocontent").text().splitlines()
					officer = ""
					agent = ""
					_type = ""

					for i, line in enumerate(textLines):
						lineText = line.strip().lower()
						if lineText == "type":
							_type = textLines[i + 1]
						elif lineText == 'officer':
							officer = textLines[i + 1].strip()
						elif lineText == "agent":
							cut = textLines[i + 1:]
							agent_str = []
							for item in cut:
								item = item.strip()
								if item == "Officer":
									break
								agent_str.append(item)
							agent = " ".join([t.strip() for t in agent_str if t.strip()])
				except Exception as error:
					caseNoWards.append({"caseNo":caseNo,"ward":ward})
					print("Could not find element !")

				application_received = ""
				decision_issued = ""
				validated = ""

				for result in parser.css(".row > .col-sm-6 > ul > li"):
					r = result.text().strip()
					if r.startswith("Application Received"):
						application_received = r.split(":")[1].strip()
					elif r.startswith("Decision Issued"):
						decision_issued = r.split(":")[1].strip()
					elif r.startswith("Validated"):
						validated = r.split(":")[1].strip()
				targetDocument = self.collection.find({"ward":ward,"case_no":caseNo})
				try:
					targetDocument = targetDocument[0]
				except Exception as err:
					# targetDocument = {}
					print(f"Failed:{err}")
				if targetDocument is not None:
					if not targetDocument.get("type"):
						self.collection.update_one({"ward":ward,"case_no":caseNo},{"$set":{"type":_type}})
					if not targetDocument["agent"]:
						self.collection.update_one({"ward": ward, "case_no": caseNo}, {"$set": {"agent": agent}})
					if not targetDocument["officer"]:
						self.collection.update_one({"ward": ward, "case_no": caseNo}, {"$set": {"officer": officer}})
					if not targetDocument["application_received"]:
						self.collection.update_one({"ward": ward, "case_no": caseNo},
						                           {"$set": {"application_received": application_received}})
					if not targetDocument["validated"]:
						self.collection.update_one({"ward": ward, "case_no": caseNo},
						                           {"$set": {"validated":validated}})
					if not targetDocument["decision_issued"]:
						self.collection.update_one({"ward": ward, "case_no": caseNo},
						                           {"$set": {"decision_issued": decision_issued}})
				os.remove(full_path)

	def random_useragent(self):
		return random.choice(USER_AGENTS)


richmondCouncil = RichmondCouncil()
richmondCouncil.update_broken_applications()
