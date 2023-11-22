import calendar
import sys
import os
from config import logger
from mongo_utils import (
    main_database,
    all_companies_collection
)
import threading
from pymongo.errors import DuplicateKeyError,AutoReconnect
import pymongo


total_charges_pipeline = [
    {
        '$unwind': {
            'path': '$charges'
        }
    }, {
        '$replaceRoot': {
            'newRoot': '$charges'
        }
    },{
        '$sort':{
            'etag':1
        }
    },
    {
        '$group': {
            '_id': 0, 
            'total_charges': {
                '$sum': 1
            }
        }
    }
]

all_charges_pipeline = [
    {
        '$unwind': {
            'path': '$charges'
        }
    }, {
        '$replaceRoot': {
            'newRoot': '$charges'
        }
    }, {
        '$sort': {
            'etag': 1
        }
    }
]

monthly_collection_names = main_database.list_collection_names()
total_monthly_collection_names = len(monthly_collection_names)

def main(_start=0,_stop=100):
    # Get all charges:
    logger.info
    all_charges = []
    for _ in range(5):
        try:
            all_charges = [res for res in all_companies_collection.aggregate(all_charges_pipeline)]
            break
        except AutoReconnect:
            logger.info("Connection lost, reconnecting...")

    all_charges = all_charges[_start:_stop]
    total_charges = len(all_charges)

    for iprog,charge in enumerate(all_charges):
        etag = charge["etag"]
        logger.info(f"Updating Charge => {etag} => {iprog+1}/{total_charges}")

        for iprog2,collection_name in enumerate(monthly_collection_names):
            collection_object = main_database[collection_name]            
            """ This query scans the collection for a borrowers.charge 
            object having the specified etag value, and it replaces 
            the charge with the equivalent new charge 
            from all_companies database"""

            collection_object.update_one(
                { "borrowers.charges.etag":etag},
                { "$set": { "borrowers.$.charges.$[charge]": charge}},
                array_filters= [ { "charge.etag":etag} ]
            )

if __name__ == "__main__":
    _start,_stop = sys.argv[1:]
    _start = int(_start)
    _stop = int(_stop)
    main(_start,_stop)