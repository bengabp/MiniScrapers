import requests
import asyncio
from httpx import AsyncClient,ReadTimeout
from mongo_utils import all_directors_collection, charges_collection, all_companies_collection, scrape_later_collection
import time
import random
from config import logger,alt_apikeys
import sys
from pymongo.errors import DuplicateKeyError
from apikeys import API_KEYS

## Load companies from collection
# companies = charges_collection.find({})[:10]
companies = [k for k in scrape_later_collection.find()]



# TOTAL_REQUESTS_PER_KEY = 173331
TOTAL_REQUESTS_PER_KEY = 3472
# TOTAL_DOCUMENTS = 5200000
TOTAL_DOCUMENTS = len(companies)
TORAL_REQUESTS_PER_KEY = (TOTAL_DOCUMENTS//30)+1
MAX_RETRIES = 5
MAX_PAGE_RESULTS = 100

API_URL_FORMAT = "https://api.company-information.service.gov.uk/company/{}/officers"

"""
There are 30 api keys and approximately 52000000 documents
52000000/30 approximately is 17,334 requests per key

This script runs for a single api key,
commang line args : api_index - [0 - 29]

It Automatically calculates the companie id list ranges needed for the key
"""

def save_scrape_later(company_details):
	try:
		scrape_later_collection.insert_one(company_details)
	except DuplicateKeyError:
		pass

async def make_request(client,url,key,params) -> tuple:
	""" This function sends an async request to the api and parses the result """
	global MAX_PAGE_RESULTS,MAX_RETRIES
	directors = []
	total_results = 0
	is_limit = False
	start_index = 0
	
	for _ in range(MAX_RETRIES):
		try:
			response = await client.get(url, headers = {
				"Authorization": key
			},params=params)
			if response.status_code == 200:
				is_limit = False
				try:
					json_response = response.json()
					total_results = json_response.get("total_results",0)
					directors = json_response.get("items",[])
					start_index = json_response.get("start_index")
				except:
					pass
			elif response.status_code == 429:
				""" Requests limit reached !"""
				is_limit = True
		except Exception as error:
			pass
	return total_results,directors,is_limit,start_index


async def run_task(api_key, client, task_details):
	global MAX_PAGE_RESULTS
	""" Makes a single api call and saved the result in the collection """
	company_number = task_details["company_number"]

	params = {"items_per_page":MAX_PAGE_RESULTS}
	url = API_URL_FORMAT.format(company_number)
	
	active_directors = []
	directors = []
	modified_company_details = task_details.copy()

	total_results,res_directors,is_limit,_ =  await make_request(client,url,api_key,params)
	directors.extend(res_directors)
	
	if is_limit:
		save_scrape_later(task_details)

	if total_results > MAX_PAGE_RESULTS:
		task_details_copy = task_details.copy()
		save_scrape_later(task_details_copy)

		# Crawl page
		num_pages = total_results // MAX_PAGE_RESULTS
		remaining_results = total_results % MAX_PAGE_RESULTS
		if remaining_results > 0:
			num_pages += 1
		num_pages -= 1  # Remove first page which has been scraped to get to this point
		for _index in range(MAX_PAGE_RESULTS,total_results,MAX_PAGE_RESULTS):
			params_copy = params.copy()
			params_copy["start_index"] = _index
			while True:
				_tr,res_directors,is_limit,start_index = await make_request(client,url,api_key,params_copy)
				if is_limit:
					print("rotating api key .. before crawling")
					api_key = random.choice(alt_apikeys)
					time.sleep(6*60)
				else:
					print(f"Got results for start index => {start_index}")
					directors.extend(res_directors)
					break

	active_directors = [director for director in directors if not director.get("resigned_on")]
	logger.info(f"Extracted directors for company => {company_number}")
	modified_company_details["active_directors"] = active_directors

	""" Save the modified company details with the added active directors """
	task_details_copy = task_details.copy()

	modified_company_details.pop("_id",None)
	modified_company_details.pop("total_results",None)
	
	all_companies_collection.replace_one({"company_number":company_number},modified_company_details,upsert=True)
	scrape_later_collection.delete_one({"company_number":company_number})
	
	""" Save all directors and if they exists already then add the current company to their list of companies """

	for active_director in active_directors:
		new_company = {"company_number":company_number,"company_name":task_details["company_name"]}
		try:
			all_directors_collection.update_one(active_director,{"$addToSet":{"companies":new_company}},upsert=True)
		except DuplicateKeyError:
			pass

async def create_async_tasks(apikey, one_request_batch: list = []) -> None:
	""" Creates the coroutines and executes them """
	for _ in range(MAX_RETRIES):
		try:
			async with AsyncClient(timeout=300) as client: # Set timeout to 5 minutes
				tasks = [run_task(apikey, client, task_details) for task_details in one_request_batch]
				results = await asyncio.gather(*tasks)
				break
		except ReadTimeout:
			print("httpx Read timeout.. Retrying after 6minutes ..")
			time.sleep(6*60)


def run(apikey, company_sublist: list = []):
	"""
	Receives the company sublist - A list of company ids from the main list for this api key.
	Script iterates pauses for 5 minutes before sending next set of requests
	"""
	total_companies = len(company_sublist)
	requests_perkey = 600

	for iprogress, i in enumerate(range(0, total_companies, requests_perkey)):
		logger.info(f"Extracting directors => [{(iprogress + 1)*600}/{total_companies}]")
		one_request_batch = company_sublist[i:i + requests_perkey]
		print(len(one_request_batch))
		asyncio.run(create_async_tasks(apikey, one_request_batch))
		logger.info("waiting for 6 minutes ..")
		time.sleep(6 * 60)  # Wait for 6 minutes instead of 5 to avoid effects of possibilities of timeshift !

def get_director_charged_companies(directors_list):
	total_directors_list = len(directors_list)
	logger.info(f"Updating {total_directors_list} directors..")
	for ind,director in enumerate(directors_list):
		logger.info(f"Updating director => {ind}/{total_directors_list}")
		companies = director["companies"]
		companies_with_charges = [company for company in companies if all_companies_collection.find_one({"company_number":company["company_number"],"charges":{"$ne":[]}})]
		all_directors_collection.update_one({"_id":director["_id"]},{"$set":{"companies_with_charges":companies_with_charges,"total_companies_with_charges":len(companies_with_charges)}})


if __name__ == "__main__":
	keyn = sys.argv[1:][0]
	keyn = int(keyn)
	logger.info("Calculating parameters ...")
	# _START_INDEX = keyn * TOTAL_REQUESTS_PER_KEY
	# _STOP_INDEX = _START_INDEX + TOTAL_REQUESTS_PER_KEY

	# company_details_list = [company_detail for company_detail in companies[_START_INDEX:_STOP_INDEX]]

	# target_apikey = API_KEYS[keyn]
	# logger.info("Done calculating .. Starting ..")
	# print(_START_INDEX, _STOP_INDEX, target_apikey, len(company_details_list))

	# run(target_apikey, company_details_list)
	total_directors = 5026927
	worker_count = 10

	directors_per_worker = total_directors//worker_count

	_start_index = keyn * directors_per_worker
	_stop_index = _start_index + directors_per_worker
	print(_start_index,_stop_index)

	# All directors
	directors_details_list = [j for j in all_directors_collection.find({"companies":{"$ne":[]}})[_start_index:_stop_index]]
	get_director_charged_companies(directors_details_list)
