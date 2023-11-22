import calendar
import sys
import os

from config import logger
from mongo_utils import person_entitled_db, charges_collection, lenders_collection, main_database
import threading
from pymongo.errors import DuplicateKeyError,AutoReconnect
import pymongo


print("Creating months..")

month_names = calendar.month_abbr[1:]

monthly_year_pipeline = [
	{
		'$unwind': {
			'path': '$borrowers'
		}
	}, {
		'$project': {
			'monthly_year': {
				'$dateToString': {
					'format': '%Y-%m',
					'date': {
						'$toDate': '$borrowers.delivered_on'
					}
				}
			}
		}
	}, {
		'$group': {
			'_id': '$monthly_year'
		}
	}, {
		'$sort': {
			'_id': 1
		}
	}
]

monthly_years = [
	                f"{month_names[int(monthly_year['_id'].split('-')[1]) - 1]}_{monthly_year['_id'].split('-')[0]}"
	                for monthly_year in lenders_collection.aggregate(monthly_year_pipeline)
                ]




def get_borrower_time_charges(borrower_company_name, monthly_year, lender_person_entitled_name):
	global charges_collection
	borrower_time_charges_pipeline = [
		{
			'$match': {
				'company_name': borrower_company_name
			}
		}, {
			'$unwind': {
				'path': '$charges'
			}
		}, {
			'$project': {
				'charge': '$charges'
			}
		}, {
			'$match': {
				'charge.persons_entitled': {
					'$elemMatch': {
						'name': {
							'$exists': True,
							'$eq': lender_person_entitled_name
						}
					}
				}
			}
		}, {
			'$match': {
				'charge.delivered_on': {
					'$regex': monthly_year
				}
			}
		}, {
			'$group': {
				'_id': 0,
				'charges': {
					'$push': '$charge'
				}
			}
		}
	]
	borrower_charges = None
	while True:
		try:
			borrower_charges = charges_collection.aggregate(borrower_time_charges_pipeline)
			for _ in borrower_charges:
				return _["charges"]
			break
		except AutoReconnect:
			logger.info("Connection lost, Reconnecting ..")
			# If the AutoReconnect exception happens , then establish a new connection
			try:
				client = pymongo.MongoClient(os.environ["MONGODB_CONNECTION_STRING"], serverSelectionTimeoutMS=3600000)
				charges_collection = client["person_entitled"]["charges_Master_dbs"]
			except:
				pass
		
	return []


def save_result(monthly_year, result, search_date):
	borrowers = result["borrowers"]
	person_entitled_name = result["person_entitled_name"]
	modified_borrowers = []
	
	for borrower in borrowers:
		borrower_company_name = borrower["company_name"]
		borrower_charges = get_borrower_time_charges(borrower_company_name, search_date, person_entitled_name)
		new_borrower = borrower.copy()
		new_borrower["charges"] = borrower_charges
		modified_borrowers.append(new_borrower)
	modified_result = result.copy()
	modified_result["borrowers"] = modified_borrowers
	try:
		main_database[monthly_year].insert_one(modified_result)
		logger.info(f"\t\t => Success !")
	except DuplicateKeyError:
		logger.info("\t\t => Ignoring inserting duplicates ..")


def format_monthly_year_collections():
	logger.info("formatting collection ..")
	for k in monthly_years:
		main_database[k].delete_many({})
	logger.info("formatting complete ..")


# format_monthly_year_collections()


def run(monthly_year):
	main_database[monthly_year].create_index("person_entitled_name", unique = True)
	logger.info(f"Sorting month => {monthly_year}")
	mth, year = monthly_year.split("_")
	month_index = f'{month_names.index(mth) + 1:02d}'
	search_date = f'{year}-{month_index}'
	monthly_lenders_pipeline = [
		{
			'$unwind': {
				'path': '$borrowers'
			}
		},
		{
			'$project': {
				'borrowers._id': 0
			}
		}, {
			'$match': {
				'borrowers.delivered_on': {
					'$regex': search_date
				}
			}
		}, {
			'$group': {
				'_id': '$person_entitled_name',
				'number_of_borrowers': {
					'$sum': 1
				},
				'borrowers': {
					'$push': '$borrowers'
				}
			}
		}, {
			'$project': {
				'_id': 0,
				'person_entitled_name': '$_id',
				'number_of_borrowers': '$number_of_borrowers',
				'borrowers': '$borrowers'
			}
		}
	]
	results = [r for r in lenders_collection.aggregate(monthly_lenders_pipeline)]
	logger.info("Gathering unprocessed documents ...")
	unprocessed_documents = [r for r in results if main_database[monthly_year].find_one(r["person_entitled_name"])]

	total_results = len(results)
	total_unprocessed_results = len(unprocessed_documents)
	logger.info(f"Gathered {total_unprocessed_results}/{total_results} unprocessed results..")
	for index_r, result in enumerate(unprocessed_documents):
		logger.info(f"\t => Extracting result => [{index_r + 1}/{total_unprocessed_results}]")
		save_result(monthly_year, result, search_date)

_target_month_index = sys.argv[1:][0]
_target_month_index = int(_target_month_index)
 
if __name__ == "__main__":
	run(monthly_years[_target_month_index])