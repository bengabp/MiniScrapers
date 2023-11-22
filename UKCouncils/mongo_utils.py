import pymongo
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import pandas


load_dotenv(".env")

"""
------------------------------------------
Setting up Cosmos DB
-------------------------------------------

cosmos_db_client = pymongo.MongoClient(os.environ["COSMOS_DB_CONNECTION_STRING"])
cosmos_db_uk_property_database = cosmos_db_client["uk_property_data"]

property_data_collection = cosmos_db_uk_property_database["property_data"]
applications_collection = cosmos_db_uk_property_database["applications"]
listed_buildings_collection = cosmos_db_uk_property_database["listed_buildings"]
hmos_collection = cosmos_db_uk_property_database["hmos"]

"""

client = pymongo.MongoClient(os.environ["ATLAS_DB_CONNECTION_STRING"])
database = client["UkCouncils"]
statusDatabase = client["StatusDB"]

