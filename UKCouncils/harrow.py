import requests
import json
from config import url, headers, abbrev_mappings, HARROW_COUNCIL_WARDS
from mongo_utils import database


class HarrowCouncil:
	def __init__(self):
		self.url = url
		self.collectionName = "harrow_council"
		self.headers = headers
		self.abbrev_mappings = abbrev_mappings
		self.wards = HARROW_COUNCIL_WARDS
		self.database = database
		self.collection = self.database[self.collectionName]

	def sendWardRequest(self,ward_code,fromRow=1,toRow=11):
		# By default gets the first 10 rows
		payload = json.dumps({
			"NOTotalRows": True,
			"fromRow": fromRow,
			"refType": "GFPlanning",
			"searchFields": {
				"APicklist2": ward_code
			},
			"toRow": toRow
		})
		response = requests.request("POST", url, headers=headers, data=payload)
		response = response.json()
		return response

	def scrapeWards(self):
		for count,(ward,code) in enumerate(self.wards.items()):
			print(f"Scraping Ward [{count}/{len(self.wards)}]")
			response = self.sendWardRequest(code)
			totalRows = response["TotalRows"]
			keyObjects = response["KeyObjects"]

			if totalRows <= 10:
				self.parseKeyObjects(keyObjects)
			else:
				for i in range(21,totalRows,10):
					response = self.sendWardRequest(code,fromRow=i,toRow=i+10)
					keyObjects = response["KeyObjects"]
					self.parseKeyObjects(keyObjects)

	def parseKeyObjects(self,keyObjects):
		planning_applications = []
		for _, keyObject in enumerate(keyObjects):
			planning_application = {"council":"Harrow Council"}
			for item in keyObject["Items"]:
				abbrev_meaning = self.abbrev_mappings[item["FieldName"]]
				planning_application[abbrev_meaning] = item["Value"]
			planning_applications.append(planning_application)

		if len(planning_applications) > 0:
			self.collection.insert_many(planning_applications)

	# def saveResults(self,filename,data):
	# 	with open(filename, "w") as results_json:
	# 		json.dump(data, results_json, indent=4)
	#

harrowCouncil = HarrowCouncil()
harrowCouncil.scrapeWards()
