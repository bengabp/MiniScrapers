import os
from dotenv import load_dotenv
import logging
import sys
from colorlog import ColoredFormatter

DIR_PATH = os.path.dirname(os.path.realpath(__file__))

# Create a logger object
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)

# Define a custom date format
date_format = '%b,%d - %H:%M'

# Create a formatter object with color formatting
formatter = ColoredFormatter(
		'%(log_color)s[%(asctime)s] %(levelname)s => %(message)s',
		datefmt=date_format,
		log_colors={
			'INFO': 'cyan',
			'DEBUG': 'green',
			'WARNING': 'yellow',
			'ERROR': 'red',
			'CRITICAL': 'red,bg_white',
		},
)

formatter2 = logging.Formatter('[%(asctime)s] %(levelname)s => %(message)s', datefmt='%b,%d - %H:%M')

# Create a file handler and add it to the logger
file_handler = logging.FileHandler(os.path.join(DIR_PATH,'runtime.log'), mode="a")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter2)
# file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Create a stream handler for console output with color formatting
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

load_dotenv(os.path.join(DIR_PATH,".env"))

alt_apikeys = ['15829749-b13c-44d4-af5b-55a8f5e6da40', '5ce5fb9f-0cc7-4ecc-a288-f47c8ea614e0', 'ec9793fa-bef4-4644-ba43-5e37c08ac80c', 
               'ced52c2e-3d62-482b-992b-e7be681395b3',
	'913d3f84-492c-4c32-becb-a0a2431c2e4c', '0b6645d6-f26a-43ec-b612-813a72ed9e86', '2f6ef1b5-7f8f-438e-be41-3f71fcf468bc', '61095a5a-248d-4d2f-87df-3086032d2f78',
	'7d8c1b81-e86e-4e2f-8547-d07df7868fa6', 'a6a62c2a-13ce-4014-a666-0d4c23dce41c', 'e723b494-eb44-4298-80ed-99ec11fa39bf', 'e0eda172-631e-49fe-8827-2b274d67f689',
	'156f6039-ea86-4c0b-9cf2-95ebe4fdf695', 'a6295444-9a38-43f0-ab3c-a84bcad19062', '66996cd2-3285-4909-9649-3a9936a85b66', '48c580fc-fcee-4a6d-8564-5232ac441501',
	'b9d214a2-56c1-4bd2-a820-2e3518ea4ec7', '6dd23756-b312-4de9-b159-f819d6cc45a3', 'a2e958f3-32a2-4cd6-a5b0-24cc7558030f', 'e290c006-711f-4eca-bc9a-f642c079dfa3',
	'13f3cabf-a304-4232-803c-5ff5229995aa', 'b99f133c-90b0-4f28-976a-831f7a9f1a42', 'bc5ced91-be10-48f0-9bd1-4d82970a3c84'
]   

CONTAINER_WORKER_COUNT = 200
SEARCH_QUERY = {
        "charges":{"$exists":True,"$ne":[]},
        "charges.address":{"$exists":False},
    }