import pymongo
from pymongo.mongo_client import MongoClient
from dotenv import load_dotenv
import os

""" This line ensures that the config module
is executed first as it initializes some
variables used throughout the program """

from config import DIR_PATH

client = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"], serverSelectionTimeoutMS=3600000)
main_database = client["MonthlyLenders"]
company_house_db = client["CompanyHouse"]
person_entitled_db = client["person_entitled"]

lenders_collection = person_entitled_db["all_lenders"]
charges_collection = person_entitled_db["charges_Master_dbs"]

all_directors_collection = company_house_db["all_directors"]
# Use compound index because two directors ma have same name
all_directors_collection.create_index([
    ("name",pymongo.ASCENDING),
    ("date_of_birth.month",pymongo.ASCENDING),
    ("date_of_birth.year",pymongo.ASCENDING),
    ("appointed_on",pymongo.ASCENDING),
    ("links.self",pymongo.ASCENDING),
],unique=True,sparse=True)
all_directors_collection.create_index([
    ("companies.company_number",pymongo.ASCENDING)
],unique=True,sparse=True)

all_companies_collection = company_house_db["all_companies"]
all_companies_collection.create_index("company_number",unique=True)

scrape_later_collection = company_house_db["scrape_later"]
scrape_later_collection.create_index("company_name",unique=True)

test_collection = company_house_db["test_charges"]
test_collection.create_index("etag",unique=True)