import os
import sys
from mongo_utils import all_companies_collection
from config import CONTAINER_WORKER_COUNT,SEARCH_QUERY
import time

# Execute system commands using os.system to create and start docker containers

# This is a test if the file will save
# Checking if file will save
def start_monthly_sort_containers():
	print("Building monthly sort containers ..")
	for i in range(38):
		command = f"docker run --restart on-failure -d --name monthlysort_{i} monthlysort:v1 python3 /app/CompanyHouse/monthly_sort.py {i}"
		os.system(command)
	print("Completed !")

def start_directors_containers():
	print("Building directors containers ..")
	for i in range(0,11):
		command = f"docker run --restart on-failure -d --name directors_{i} companyhouse:v1 python3 /app/CompanyHouse/get_directors.py {i}"
		os.system(command)
	print("Completed  !")   

def destroy_directors_containers():
	print("Destroying directors containers ..")
	for i in range(0,30):
		command = f"docker container stop directors_{i}"
		os.system(command)
		command = command.replace("stop","rm")
		os.system(command)
		
	print("Completed !")


def destroy_monthly_sort_containers():
	print("Destroying monthly sort containers ..")
	command = 'docker container stop $(docker ps --filter "name=monthlysort" -aq)'
	command = command.replace("stop","rm")
	os.system(command)
	print("Completed !")


def start_address_containers():
	global CONTAINER_WORKER_COUNT
	
	print("Calculating ...")
    # Get new documents from collection
	total_unprocessed_companies = all_companies_collection.count_documents(SEARCH_QUERY)
	for i,start_index in enumerate(range(1,total_unprocessed_companies,CONTAINER_WORKER_COUNT)):
		command = f"docker run --restart on-failure -d --name address{i} companyhouse:v1 python3 /app/CompanyHouse/get_address_title_number.py {start_index}"
		os.system(command)
		print("Waiting for 15 seconds before creating next one")
		time.sleep(5)
	print("Done ..")

func = start_directors_containers()
# ans = input(f"Are you sure you want to run function => {func.__name__}() y/n ? ")
# if ans == "y":
# 	func()
# elif ans == "n":
# 	print("exiting.")
# 	sys.exit()
# else:
# 	print("invalid answer")