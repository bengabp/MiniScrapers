from config import logger
from mongo_utils import TwitterMongoClient
from pymongo.errors import DuplicateKeyError

import sys
import re

filename = sys.argv[1:][0]

twitter_client = TwitterMongoClient()
twitter_client.connect()


def process_line(line, count):
	# Define the regex pattern
	pattern = r'(\w+):\s(.+?)(?=\s-\s\w+|$)'
	# Find all matches using the regex pattern
	matches = re.findall(pattern, line)
	data = {match[0]: match[1] for match in re.findall(pattern, line)}
	print(f"Data => {count} => {data}")
	try:
		twitter_client.credentials.insert_one(data)
	except DuplicateKeyError:
		pass


def gen_process_file():
	# Process each line in the file in parallel using multithreading
	for line in open(f"data/subfiles/{filename}"):
		yield line.strip()


count = 0
for line in gen_process_file():
	count += 1
	process_line(line,count)


