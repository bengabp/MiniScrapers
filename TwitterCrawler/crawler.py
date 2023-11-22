# Built-in modules
import os
import sys
import json
from pprint import pprint
import re
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Literal, Union
from urllib.parse import urlencode, quote
import asyncio
import uuid
from multiprocessing import Process
import traceback

# Site-packages modules
from playwright.sync_api import (sync_playwright,
								 Page,
								 Error,
								 TimeoutError,
								 BrowserContext,
								 Locator,
								 Browser,
								 ElementHandle)

from selectolax.parser import HTMLParser, Node
from pymongo.errors import DuplicateKeyError
import requests
from redis import Redis
import pandas

# Custom modules
from config import logger, DIR_PATH, DIRECTORIES, REDIS_HOST, REDIS_PORT, REDIS_TASKS_DB
from mongo_utils import TwitterMongoClient
from utils import parse_humanreadable_string


class ContainerizedCrawler:
	def __init__(self, _id, search_query):
		self.dowload_link = None
		self.on_response_callback = None
		self.crawler_id = _id
		self.logger = logger
		self.search_query = search_query

		# Initialize the mongodb connection
		self.twitter_client = TwitterMongoClient()
		self.twitter_client.connect()

		# Initialize redis connection
		# DB 2 is tasks db
		self.redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_TASKS_DB)

		self.comments_usernames_per_tweet = int(os.environ["COMMENTS_USERNAMES_PER_TWEET"])
		self.retweets_usernames_per_tweet = int(os.environ["RETWEETS_USERNAMES_PER_TWEET"])
		self.likes_usernames_per_tweet = int(os.environ["LIKES_USERNAMES_PER_TWEET"])
		self.session_filename = os.environ["SESSION_FILE"]
		self.headless = eval(os.environ["HEADLESS"])

		self.crawler_expire_time = int(os.environ["CRAWLER_EXPIRE_TIME"])

		self.total_usernames = sum([self.likes_usernames_per_tweet,
									self.comments_usernames_per_tweet,
									self.retweets_usernames_per_tweet])

		self.sessions_dir = DIRECTORIES["TWITTER_SESSIONS_DIR"]

		self.session_filepath = os.path.join(DIR_PATH, self.sessions_dir, self.session_filename)

		self.screenshots_dir = DIRECTORIES["SCREENSHOTS_DIR"]
		self.twitter_login_url = "https://twitter.com/i/flow/login"

		self.total_comments_usernames = 0
		self.total_likes_usernames = 0
		self.total_retweets_usernames = 0

		self.comments_usernames = []
		self.retweets_usernames = []
		self.likes_usernames = []

		""" This data holds all response from the unauthenticated account so as to get the cursor for making requests"""
		self.json_data = {}

		self.tweet_detail_url_pattern = re.compile(r"api/graphql/\S+/TweetDetail", re.IGNORECASE)

		self.comments_start_time = 0
		self.comments_scroll_idle = 0

		self.process_start_time = 0
		self.all_usernames = set()

		self.tweet_comment_usernames = []
		self.json_data = {}

		self.response_headers = {}
		self.request_headers = {}
		self.tweet_graphql_url = ""

		self.comments_count = 0  # Holds the count of the comments for the current tweet
		self.tweet_comment_usernames = []  # Holds all commented usernames for a tweet

		self.default_timeout = 10

		self.useremail_pipeline = [
			{
				'$match': {
					'ScreenName': {
						'$in': [
							'JoeOsullivan2', 'FemaleWitticism'
						]
					}
				}
			}, {
				'$project': {
					'_id': 0,
					'ScreenName': 1,
					'Email': 1
				}
			}
		]

	def screenshot(self, page: Page, filename="screenshot.png", full_page=False):
		filepath = os.path.join(self.screenshots_dir, filename)
		try:
			page.screenshot(path=filepath, full_page=full_page)
		except TimeoutError:
			self.logger.info("Failed taking screenshot ...")

	def update_user(self, username, _from: Literal["tweet", "retweet", "comment", "like"], **kwargs):
		""" This method calls the create_or_update_user method while collecting some data """
		if username not in self.all_usernames:
			self.all_usernames.add(username)
			self.logger.info(f"Total usernames => {len(self.all_usernames)}")

		self.twitter_client.create_or_update_user(username, **kwargs)

	def run(self):
		exception_details = None
		self.process_start_time = time.time()

		# Update process state
		current_state = "RUNNING"
		self.update_crawler(state=current_state, error=exception_details)
		try:
			with sync_playwright() as playwright_sync:
				browser = playwright_sync.chromium.launch(headless=self.headless, args=[
					"--disable-blink-features=AutomationControlled"
				])
				self.logger.info(f"Loading saved session from file => {self.session_filepath} ...")

				context = browser.new_context(storage_state=self.session_filepath)
				page = context.new_page()
				page.goto(f"https://twitter.com/search?q={quote(self.search_query)}&src=typed_query&f=top", timeout=0)

				tweet_links = []
				# total_tweets_obtained = 0

				idle_time = 0
				start_time = time.time()
				scroll_tweets = True

				comments_context = browser.new_context()

				# while len(self.all_usernames) <= self.total_usernames and scroll_tweets:
				while scroll_tweets:
					idle_time = abs(start_time - time.time())
					self.screenshot(page=page, filename="sweepytrink.png", full_page=False)
					tweets = page.query_selector_all("article[data-testid='tweet']")
					if not tweets:
						self.logger.info("No tweets found,looping ...")
						time.sleep(1)
						continue

					for tweet in tweets:
						try:
							tweet_owner_profile = tweet.query_selector("div > a[role='link']").get_property(
								"href").__str__()
							tweet_owner = tweet_owner_profile.split("/")[-1]  # Username
							tweet_url = tweet.query_selector("a[href][dir='ltr']").get_property("href").__str__()
							if not tweet_url.startswith("https://twitter.com") or "status" not in tweet_url:
								self.logger.info("Invalid tweet url ... skipping tweet..")
								continue

							scraped_at = datetime.now().timestamp()
							tweet_id = tweet_url.split("/")[-1]
							like_element = tweet.query_selector("div[data-testid='like']")
							retweet_element = tweet.query_selector("div[data-testid='retweet']")

							likes = 0
							retweets = 0

							if like_element:
								try:
									likes = parse_humanreadable_string(like_element.text_content())
								except IndexError:
									pass
							if retweet_element:
								try:
									retweets = parse_humanreadable_string(retweet_element.text_content())
								except IndexError:
									pass

							# total_tweets_obtained += 1
							self.update_user(tweet_owner, "tweet", keyword=self.search_query,
											 own_tweet_id=tweet_id)

							if tweet_url not in tweet_links:
								start_time = time.time()
								idle_time = 0
								tweet_details = {
									"tweet_id": tweet_id,
									"tweet_owner": tweet_owner,
									"tweet_owner_profile": tweet_owner_profile,
									"tweet_url": tweet_url,
									"scraped_ts": scraped_at,
									"search_keyword": self.search_query,
									"likes": likes,
									"retweets": retweets
								}

								tweet_links.append(tweet_url)
								for _type in ["retweet", "like"]:
									try:
										self.get_retweet_like_usernames(context, tweet_details,
																		_type=_type)
									except Error:
										continue

								self.get_comments_usernames(comments_context, tweet_details)

								if len(self.all_usernames) > self.total_usernames:
									scroll_tweets = False
									break
						except AttributeError:
							continue
						except Error:
							continue

					last_tweet = tweets[-1]
					try:
						# Stop scrolling if the idle time is above the set threshold
						if idle_time >= self.default_timeout:
							scroll_tweets = False
							break
						# self.logger.info(f"No more new tweets has been recorded for the past => {idle_time}
						# seconds. " f"Exiting scroll loop with {len(required_tweets)} tweets...")
						last_tweet.scroll_into_view_if_needed()
					except:
						pass

				# Close page, context and browser
				for instance in [page, context, browser, comments_context]:
					try:
						instance.close()
					except Error:
						pass
			current_state = "COMPLETED"

		except:
			current_state = "FAILED"
			exception_details = traceback.format_exc()
			self.logger.info(exception_details)
		finally:
			self.update_crawler(state=current_state, error=exception_details, build_csv = True)

		self.logger.info(f"Task completed => {self.crawler_id}")

	def get_user_email(self, username):
		email = None
		res = self.twitter_client.credentials.find_one({"ScreenName": username})
		if res:
			email = res["Email"]
		return email

	# Literal["FAILED", "COMPLETED", "RUNNING", "STARTING"]
	def update_crawler(self, state: str, error: Optional[str] = None, build_csv=False):
		usernames_with_emails = []
		if build_csv:
			self.logger.info("Building csv data")
			username_list = list(self.all_usernames)
			pipeline = [
				{
					'$match': {
						'ScreenName': {
							'$in': username_list
						}
					}
				}, {
					'$project': {
						'_id': 0,
						'ScreenName': 1,
						'Email': 1
					}
				}
			]
			pipeline_result = self.twitter_client.credentials.aggregate(pipeline)
			dataframe = pandas.DataFrame(pipeline_result)
			filepath = os.path.join(DIRECTORIES["CSV_DATA_DIR"], self.crawler_id + ".csv")
			dataframe.to_csv(filepath)
			self.logger.info("Done building csv !")

		data = {
			"crawler_id": self.crawler_id,
			"result": {
				"users": usernames_with_emails,
				"total_usernames": len(usernames_with_emails),
				"download_link": self.dowload_link
			},
			"query": {
				"q": self.search_query,
				"retweet_usernames_per_tweet": self.retweets_usernames_per_tweet,
				"like_usernames_per_tweet": self.likes_usernames_per_tweet,
				"comment_usernames_per_tweet": self.comments_usernames_per_tweet
			},
			"stats": {
				"state": state,
				"start_time": self.process_start_time,
				"error": error
			}
		}
		json_string = json.dumps(data)
		# self.redis_client.set(self.crawler_id, json_string, ex = self.crawler_expire_time)
		self.redis_client.set(self.crawler_id, json_string)

	def get_retweet_like_usernames(self, context: BrowserContext, tweet: Dict, _type: Literal["retweet", "like"]):
		""" This method extracts all the usernames from the retweet or like """
		details_page = context.new_page()
		self.logger.info(f"Getting {_type}s usernames ...")
		tweet_url = tweet["tweet_url"].rstrip('/')
		tweet_id = tweet["tweet_id"]
		target_url: str = tweet_url + f"/{_type}s"
		likes = tweet["likes"]
		retweets = tweet["retweets"]

		if _type == "like":
			timeline_query_text = "Liked"
			target_threshold = likes
		else:
			timeline_query_text = "Retweeted"
			target_threshold = retweets
		passed = False

		if target_threshold <= 0:
			details_page.close()
			return
		if not target_url.startswith("https://twitter.com"):
			self.logger.info("Tweet url does not point to the twitter server ...")
			details_page.close()
			return

		details_page.goto(target_url)
		target_viewport = details_page.wait_for_selector("div [data-viewportview='true']",
														 state="visible", timeout=0)

		for r in range(5):
			details_page.goto(target_url)
			target_viewport = details_page.wait_for_selector("div [data-viewportview='true']",
															 state="visible", timeout=0)
			viewport_text = target_viewport.text_content()
			if viewport_text != 'Retweeted bySomething went wrong. Try reloading.Retry':
				passed = True
				break
		if not passed:
			details_page.close()
			return

		check_element = target_viewport.wait_for_selector(
			f"div[aria-label='Timeline: {timeline_query_text} by'] > div > div[data-testid]")
		self.screenshot(page=details_page, filename=f"sweepytrink_{_type}.png", full_page=False)

		target_usernames = []
		if _type == "likes":
			usernames_threshold = self.likes_usernames_per_tweet
		else:
			usernames_threshold = self.retweets_usernames_per_tweet
		scroll_timeline = True
		idle_time = 0
		start_time = time.time()
		# if text == 'Retweeted bySomething went wrong. Try reloading.Retry':

		while scroll_timeline and len(target_usernames) <= usernames_threshold:
			idle_time = abs(start_time - time.time())
			# Get the retweets / likes
			parser = HTMLParser(target_viewport.inner_html())
			self.screenshot(page=details_page, filename=f"sweepytrink_{_type}.png", full_page=False)

			timeline_elements: List[Node] = parser.css(
				f"div[aria-label='Timeline: {timeline_query_text} by'] > div > div[data-testid]")

			if not timeline_elements:
				continue

			# Get all usernames in retweets / likes
			for timeline_element in timeline_elements:
				if len(target_usernames) > usernames_threshold:
					details_page.close()
					scroll_timeline = False
					return target_usernames

				account_hyperlink = timeline_element.css_first("a[href][role='link']")
				if account_hyperlink is None:
					continue
				username = account_hyperlink.attrs["href"].lstrip("/")
				if username not in target_usernames:
					start_time = time.time()
					idle_time = 0
					target_usernames.append(username)
				if _type == "like":
					self.update_user(username, "like", keyword=self.search_query,
									 like_id=target_url)
				else:
					self.update_user(username, "retweet", keyword=self.search_query,
									 retweet_id=target_url)

			# Get last retweet/like element and scroll_into_view

			if _type == "like":
				last_timeline_element = target_viewport.query_selector(
					"div[aria-label='Timeline: Liked by'] > div > div[data-testid]:last-child")
			else:
				last_timeline_element = \
					target_viewport.query_selector(
						"div[aria-label='Timeline: Retweeted by'] > div > div[data-testid]:last-child")

			try:
				# self.logger.info(f"retweet scroll idle time => {idle_time}s")
				if idle_time > self.default_timeout:
					scroll_timeline = False
					break
				last_timeline_element.scroll_into_view_if_needed()
			except:
				pass
		try:
			details_page.close()
		except Error:
			pass
		return target_usernames

	def parse_graphql_data(self, graphql_data: dict, tweet_id: str, search_keyword: str):
		""" This function receives and parses the data from the graphql api
		then returns the cursor for getting next results if available otherwise None"""

		instructions = graphql_data["data"]["threaded_conversation_with_injections_v2"]["instructions"]
		cursor: Optional[str] = None
		cursor_type = None
		# Extract first badge of comments:
		"""
		Tweet Entry types:
		There are 2 categories of tweet comments:

		 - TimelineTimelineItem > itemContent{}
			 - {
				 "itemType":"TimelineTweet",
				 "tweet_results":{}
			 }

		- TimelineTimelineModule > items[]
			- {
				'item':{
					'itemContent':{
						"tweet_results":{},
						"itemType":"TimelineTweet"
					}
				}
			}
		"""

		if instructions:
			entries = instructions[0]["entries"]
			for entry in entries:
				entry_content = entry["content"]
				entry_type = entry_content["entryType"]
				if entry_type == "TimelineTimelineModule":
					items = entry_content["items"]
					for item_object in items:
						item = item_object["item"]["itemContent"]
						item_type = item["itemType"]
						if item_type == "TimelineTweet":
							self.extract_tweet_username(item, tweet_id)

				elif entry_type == "TimelineTimelineItem":
					item_content = entry_content["itemContent"]
					item_type = item_content["itemType"]
					if item_type == "TimelineTweet":  # is tweet
						self.extract_tweet_username(item_content, tweet_id)
					elif item_type == "TimelineTimelineCursor":
						cursor_type = item_content['cursorType']
						if cursor_type not in ['Top']:
							cursor = item_content["value"]
		return cursor

	def extract_tweet_username(self, item: dict, tweet_id: str) -> None:
		""" Extract the username from the give tweet json data """
		try:
			username = item["tweet_results"]["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"]
			self.update_user(username, "comment", keyword=self.search_query, tweet_id=tweet_id)
			if username not in self.tweet_comment_usernames:
				self.tweet_comment_usernames.append(username)
				self.comments_count += 1
		except KeyError:
			self.logger.info("Could not extract username")

	def handle_response(self, response, tweet_id):
		""" This method intercepts all responses as soon as they come in """
		url: str = response.url
		if self.tweet_detail_url_pattern.findall(url).__len__() > 0:
			""" Intercepting only the tweetDetails response from the graphql"""
			self.tweet_graphql_url = url.rsplit("?")[0]
			self.response_headers = response.headers
			self.request_headers = response.request.headers
			json_data = json.loads(response.body())
			self.parse_graphql_data(json_data, search_keyword=self.search_query, tweet_id=tweet_id)
			if self.comments_start_time > 0:
				self.comments_start_time = time.time()
				self.comments_scroll_idle = 0

	def get_comments_usernames(self, context: BrowserContext, tweet: Dict):
		""" This method extract the commented usernames from a single tweet """
		self.tweet_comment_usernames = []
		self.json_data = {}

		self.response_headers = {}
		self.request_headers = {}
		self.tweet_graphql_url = ""

		self.comments_count = 0

		tweet_url = tweet["tweet_url"].rstrip('/')
		search_keyword = tweet.get("search_keyword", None)
		tweet_id = tweet["tweet_id"]
		self.logger.info(f"Scraping tweet comments => {tweet_id}")

		page = context.new_page()
		page.set_default_timeout(10000)

		self.on_response_callback = lambda response: self.handle_response(response, tweet_id)

		page.on("response", self.on_response_callback)
		page.goto(tweet_url, timeout=0)

		try:
			page.wait_for_selector('#credential_picker_container')
		except TimeoutError:
			pass
		scripts = [
			# Remove google login popup
			"document.querySelector('#credential_picker_container').style.display='none'",

			# Remove twitter-notification consent popup
			"document.querySelector(\"div[role='group'][tabindex]\").remove()",
			"document.querySelector(\"div[data-testid='mask']\").remove()",

			# Enable scrolling in conversation timeline
			"document.querySelector(\"section[role='region'] > div[aria-label='Timeline: "
			"Conversation']\").style.overflowY='scroll'"
		]
		for script in scripts:
			try:
				page.evaluate(script)
			except Error:
				pass

		timeline_conversation_container = page.wait_for_selector("div[aria-label='Timeline: Conversation']")

		self.comments_start_time = time.time()
		self.comments_scroll_idle = 0

		scroll_comments = True
		while self.comments_count <= self.comments_usernames_per_tweet and scroll_comments:
			self.comments_scroll_idle = abs(time.time() - self.comments_start_time)
			conversation_containers = []
			try:
				conversation_containers = timeline_conversation_container.query_selector_all(
					"div[data-testid='cellInnerDiv']")
			except (Error, AttributeError):
				pass
			if conversation_containers:
				last_conversation_container = conversation_containers[-1]
				try:
					if self.comments_scroll_idle > self.default_timeout:
						scroll_comments = False
						self.comments_start_time = 0
						self.comments_scroll_idle = 0
						break
					last_conversation_container.scroll_into_view_if_needed()
				except:
					pass
		page.close()

	def create_csv(self):
		pass


if __name__ == "__main__":
	search_query = os.environ["SEARCH_QUERY"]
	_id = os.environ["WORKER_ID"]
	crawler = ContainerizedCrawler(_id=_id, search_query=search_query)
	crawler.run()
