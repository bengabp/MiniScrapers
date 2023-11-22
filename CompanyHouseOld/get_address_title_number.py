from postal.parser import parse_address
from string import ascii_lowercase
import random
import threading
import asyncio
from mongo_utils import all_companies_collection,test_collection
from config import logger,CONTAINER_WORKER_COUNT,SEARCH_QUERY
import sys
from pymongo.errors import DuplicateKeyError
import re
from pprint import pprint




def extract_title_numbers(des_string:str) -> list:
    """ This function extract the title numbers using regex """
    pattern = re.compile(r"\b([0-9A-Z]{6,14}|\w+[0-9]{6,14})\b(?<!\d\d[A-Z]{2})")
    matches = pattern.findall(des_string)
    return matches

def process_description(str_address):
    address_list = parse_address(str_address)
    clean_address = {line[1]:line[0] for line in address_list}
    return clean_address


async def process_single_company(company_details):
    charges = company_details["charges"]
    modified_charges = []

    for charge in charges:
        modified_charge = {}
        title_numbers = []
        address = {}
        try:
            address = process_description(charge["particulars"]["description"])
        except KeyError:
            pass
        try:
            title_numbers = extract_title_numbers(charge["particulars"]["description"])
        except KeyError:
            pass

        modified_charge.update(charge)
        modified_charge["address"] = address
        modified_charge["title_numbers"] = title_numbers
        modified_charges.append(modified_charge)
    
    if modified_charges:
        company_details["charges"] = modified_charges
    else:
        company_details["charges"] = charges
    
    # Update company with new details
    company_number = company_details["company_number"]
    company_details.pop("_id",None) # Delete _id property to avoid write errors.

    all_companies_collection.update_one({"company_number":company_number},{"$set":company_details})


async def update_new_companies(companies):
    """ This function fetches all the new companies , 
    then adds the address and title number properties to them """

    CHUNK_SIZE = 200
    total_new_companies = len(companies)

    for i in range(0,total_new_companies,CHUNK_SIZE):
        chunk = companies[i:i+CHUNK_SIZE]
        logger.info(f"Updating companies => {i+1}/{total_new_companies}\n")
        # Process all companies using async functions
        tasks = [process_single_company(company) for company in chunk]
        results = await asyncio.gather(*tasks)


if __name__ == "__main__":
    start_index = int(sys.argv[1:][0])
    print("Getting all companies ...")
    
    # Get new documents from collection
    total_unprocessed_companies = all_companies_collection.count_documents(SEARCH_QUERY)

    companies = all_companies_collection.find(SEARCH_QUERY)
    stop_index = start_index+(total_unprocessed_companies//CONTAINER_WORKER_COUNT)+1
    region_of_interest_chunk = [g for g in companies[start_index:stop_index]]                                          
    logger.info(f"Updating companies from {start_index} to {stop_index} => {len(region_of_interest_chunk)} companies ...")
    print("Done.. Updating chunk by chunk ..")
    asyncio.run(update_new_companies(region_of_interest_chunk))

    