import pymongo
from pymongo.mongo_client import MongoClient
from dotenv import load_dotenv
import os
from pymongo.errors import BulkWriteError, DuplicateKeyError
from pymongo.collection import Collection
from pymongo.database import Database

import time
import uuid
from typing import Any, Optional

""" This line ensures that the config module
is executed first as it initializes some
variables used throughout the program """

from config import DIR_PATH, logger


class TwitterMongoClient:
	def __init__(self):
		""" Defines all attributes for a mongodb client connection """
		self.logger = logger
		self._db_name = "TwitterDataStore"
		self.MONGO_CONNECTION_STRING = os.environ["MONGODB_CONN_STRING"]
		self.SERVER_SELECTION_TIMEOUT = 3600000

		self.twitter_users: Optional[Collection] = None
		self.tweets: Optional[Collection] = None
		self.result_backend: Optional[Collection] = None
		self.credentials: Optional[Collection] = None

		self.db: Optional[Database] = None

	def connect(self):
		""" Connects to a mongodb instance """
		self.logger.info("Connecting to mongod instance ..")
		client = pymongo.MongoClient(self.MONGO_CONNECTION_STRING,
									 serverSelectionTimeoutMS=self.SERVER_SELECTION_TIMEOUT)
		self.logger.info("Connected !")
		self.db = client[self._db_name]

		# Define collections
		self.twitter_users: Collection = self.db["twitter_users"]
		self.twitter_users.create_index("username", unique=True)

		self.tweets: Collection = self.db["tweets"]
		self.tweets.create_index([
			("tweet_owner", 1),
			("tweet_owner_profile", 1),
		])
		self.tweets.create_index("tweet_id", unique=True)

		self.result_backend = self.db["tasks"]

		self.credentials = self.db["credentials"]
		self.credentials.create_index([
			("Email", 1),
			("ScreenName", 1)
		], unique=True)
		self.credentials.create_index("ScreenName")

	def create_or_update_user(self, username: str, keyword: str = None, tweet_id: str = None, like_id: str = None,
							  retweet_id: str = None, own_tweet_id: str = None):
		nullable_vars = {
			"keywords": keyword,
			"tweets_featured_in": tweet_id,
			"likes_featured_in": like_id,
			"retweets_featured_in": retweet_id,  # This is the link to the retweet
			"own_tweets": own_tweet_id
		}

		user_doc = {
			"username": username,
			"own_tweets": [],
			"tweets_featured_in": [],
			"retweets_featured_in": [],
			"likes_featured_in": [],
			"keywords": []
		}

		try:
			self.twitter_users.insert_one(user_doc)
		except DuplicateKeyError:
			pass

		# Update fields with non-null values
		for doc_array, value in nullable_vars.items():
			if value is not None:
				self.twitter_users.update_one(user_doc, {'$addToSet': {doc_array: value}})

	def new_task(self, task_details):
		self.result_backend.insert_one(task_details)

	def get_task_result(self, task_id):
		return self.result_backend.find({"_id": task_id})
