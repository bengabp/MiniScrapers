import os
from dotenv import load_dotenv
import logging
import sys
from colorlog import ColoredFormatter

DIR_PATH = os.path.dirname(os.path.realpath(__file__))

# Define and initialize all directories
DIRECTORIES = {
	"LOG_FILES_DIR": os.path.join(DIR_PATH, "logs"),
	"SCREENSHOTS_DIR": os.path.join(DIR_PATH, "screenshots"),
	"TWITTER_SESSIONS_DIR": os.path.join(DIR_PATH, "twitter_sessions"),
	"CSV_DATA_DIR": os.path.join(DIR_PATH, "output")
}

for _name, _dir in DIRECTORIES.items():
	if not os.path.exists(_dir):
		os.mkdir(_dir)

# Create a logger object
logger = logging.getLogger('mylogger')
logger.setLevel(logging.DEBUG)

# Define a custom date format
date_format = '%b,%d - %H:%M'

# Create a formatter object with color formatting
formatter = ColoredFormatter(
	'%(log_color)s[%(asctime)s] %(levelname)s => %(message)s',
	datefmt = date_format,
	log_colors = {
		'INFO': 'cyan',
		'DEBUG': 'green',
		'WARNING': 'yellow',
		'ERROR': 'red',
		'CRITICAL': 'red,bg_white',
	},
)
formatter2 = logging.Formatter('[%(asctime)s] %(levelname)s => %(message)s', datefmt = '%b,%d - %H:%M:%S')

# Create a file handler and add it to the logger
file_handler = logging.FileHandler(os.path.join(DIR_PATH, "runtime.log"), mode = "a")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter2)
# file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Create a stream handler for console output with color formatting
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

load_dotenv(os.path.join(DIR_PATH, ".env"))

SCHEMA = {
	"username": "elonmusk",
	"keywords": [
		"chatgpt",
		"marketing"
	],
	"tweets_featured_in": [
		"898989833433434343",
		"343434354565565631"
	],
	"likes_featured_in": [
		"898989833433434343",
		"343434354565565631"
	],
	"retweets_featured_in": [
		"898989833433434343",
		"343434354565565631"
	],
}

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = os.environ["REDIS_PORT"]
REDIS_TASKS_DB = os.environ["REDIS_TASKS_DB"]
