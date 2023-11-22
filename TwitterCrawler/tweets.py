# Built-in modules
import os
import sys
import json
from pprint import pprint
import re
import time
import random
from datetime import datetime
from typing import List, Dict, Optional, Literal
from urllib.parse import urlencode,quote
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
from playwright.async_api import (async_playwright,
								  Page as AsyncPage,
								  BrowserContext as AsyncBrowserContext,
								  TimeoutError as AsyncTimeoutError,
								  Locator as AsyncLocator,
								  Error as AsyncError)
from selectolax.parser import HTMLParser, Node
from pymongo.errors import DuplicateKeyError
import requests
from redis import Redis

# Custom modules
from config import logger, DIR_PATH, DIRECTORIES, REDIS_HOST, REDIS_PORT, REDIS_TASKS_DB
from mongo_utils import TwitterMongoClient
from utils import parse_humanreadable_string


class TwitterCrawler:
	def __init__(
			self,
			task_id,
			search_query,
			max_tweets=10,
			max_retweets=10,
			max_likes=10,
			max_comments=10
	):
		self.logger = logger
		self.task_id = task_id
		self.search_query = search_query
		
		# Initialize the mongodb connection
		self.twitter_client = TwitterMongoClient()
		self.twitter_client.connect()
		
		# Initialize redis connection
		# DB 2 is tasks db
		self.redis_client = Redis(host = REDIS_HOST, port = REDIS_PORT,db = REDIS_TASKS_DB)
		
		self.sessions_dir = DIRECTORIES["TWITTER_SESSIONS_DIR"]
		self.session_filename = "sweepytrink.json"
		self.session_filepath = os.path.join(DIR_PATH, self.sessions_dir, self.session_filename)
		
		self.screenshots_dir = DIRECTORIES["SCREENSHOTS_DIR"]
		self.twitter_login_url = "https://twitter.com/i/flow/login"
		
		self.tweets_threshold = max_tweets
		self.retweets_threshold = max_retweets
		self.likes_threshold = max_likes
		self.comments_threshold = max_comments
		
		self.comments_count = 0 # Holds the count of the comments for the current tweet
		self.tweet_comment_usernames = [] # Holds all commented usernames for a tweet
		
		self.tweet_usernames = []
		self.like_usernames = []
		self.retweet_usernames = []
		
		self.all_usernames = []
		
		self.new_tweets_timeout = 10  # Number of seconds for new tweets to come in before timeout
		self.new_retweets_timeout = 10  # Number of seconds for new retweets to come in before timeout
		self.new_likes_timeout = 10  # Number of seconds for new likes to come in before timeout
		self.comments_scroll_timeout = 10 # Number of seconds for new comments to come in before timeout
		
		""" This data holds all response from the unauthenticated account so as to get the cursor for making requests"""
		self.json_data = {}
		
		self.tweet_detail_url_pattern = re.compile(r"api/graphql/\S+/TweetDetail", re.IGNORECASE)
		
		self.comments_start_time = 0
		self.comments_scroll_idle = 0
		
		self.process_start_time = 0
	
		
	
	def screenshot(self, page: Page, filename = "screenshot.png", full_page = False):
		filepath = os.path.join(self.screenshots_dir, filename)
		try:
			page.screenshot(path = filepath, full_page = full_page)
		except TimeoutError:
			self.logger.info("Failed taking screenshot ...")
	
	def run(self):
		exception_details = None
		self.process_start_time = time.time()
		
		# Update process state
		current_state = "STARTING"
		self.update_process(state = current_state, error = exception_details, result = self.collect_result())
		
		try:
			self.logger.info("Running crawler ...")
			required_tweets = []
			
			# Update process state
			current_state = "RUNNING"
			self.update_process(state = current_state, error = exception_details, result = self.collect_result())
			
			with sync_playwright() as playwright_sync:
				browser = playwright_sync.chromium.launch(headless = True, args = [
					"--disable-blink-features=AutomationControlled"
				])
				# Check if the session file exists otherwise open a new page for user to login and setup session
				if not os.path.exists(self.session_filepath):
					self.logger.info(f"Session file not found at {self.session_filepath}")
					create_or_not = input("Do you want to create one ? (y/n) :")
					if create_or_not.lower() == "y":
						# Create a new session and write to file.
						new_context = browser.new_context()
						new_page = new_context.new_page()
						new_page.goto(self.twitter_login_url)
						self.logger.info("Just complete the login and let me know when you are authenticated !")
						
						while True:
							authenticated_or_not = input("Are you authenticated ? (y/n) press 'q' to quit:")
							if authenticated_or_not.lower() == "y":
								filename = input("Enter a name to save this authenticated browser session as :")
								if os.path.exists(os.path.join(self.sessions_full_dir, filename)):
									overwrite = input(
										"A session with this name already exists, do you want to overwrite it ? (y/n):")
									if overwrite.lower() == "y":
										pass
									elif overwrite.lower() == "n":
										filename = input("Now enter a different filename :")
									else:
										print("Authenticated session was not saved !")
								full_filepath = os.path.join(self.sessions_full_dir, filename + ".json")
								print(full_filepath)
								self.logger.info("Saving authenticated session to file")
								session = new_context.storage_state()
								with open(full_filepath, "w") as session_file:
									json.dump(session, session_file, indent = 4)
								self.logger.info("Done saving, you can now load this file into another browser context !")
								break
							elif authenticated_or_not.lower() == "n":
								print("Please authenticate ..")
							else:
								print("Invalid reply !")
					sys.exit()
				
				# Continue to load the session file if it exists
				self.logger.info(f"Loading saved session from file => {self.session_filepath} ...")
				
				context = browser.new_context(storage_state = self.session_filepath)
				page = context.new_page()
				page.goto(f"https://twitter.com/search?q={quote(self.search_query)}&src=typed_query&f=top", timeout = 0)
				
				tweet_links = []
				# total_tweets_obtained = 0
				
				idle_time = 0
				start_time = time.time()
				scroll_tweets = True
				
				while len(self.tweet_usernames) <= self.tweets_threshold and scroll_tweets:
					idle_time = abs(start_time - time.time())
					# self.screenshot(page = page, filename = "sweepytrink.png", full_page = False)
					tweets = page.query_selector_all("article[data-testid='tweet']")
					if not tweets:
						# self.logger.info("No tweets found,looping ...")
						time.sleep(2)
						continue
					for tweet in tweets:
						tweet_owner_profile = tweet.query_selector("div > a[role='link']").get_property("href").__str__()
						tweet_owner = tweet_owner_profile.split("/")[-1]  # Username
						tweet_url = tweet.query_selector("a[href][dir='ltr']").get_property("href").__str__()
						scraped_at = datetime.now().timestamp()
						tweet_id = tweet_url.split("/")[-1]
						
						# total_tweets_obtained += 1
						self.update_user(tweet_owner, "tweet", keyword = self.search_query,
																  own_tweet_id = tweet_id)
						
						if tweet_url not in tweet_links:
							start_time = time.time()
							idle_time = 0
							tweet_details = {
								"tweet_id": tweet_id,
								"tweet_owner": tweet_owner,
								"tweet_owner_profile": tweet_owner_profile,
								"tweet_url": tweet_url,
								"scraped_ts": scraped_at,
								"search_keyword":self.search_query
							}
							required_tweets.append(tweet_details)
							tweet_links.append(tweet_url)
							# try:
							# 	self.twitter_client.tweets.insert_one(tweet_details)
							# 	self.logger.info(f"Total tweets => {len(required_tweets)}")
							# except DuplicateKeyError:
							# 	self.logger.info("Ignoring duplicate tweets ...")
					last_tweet = tweets[-1]
					try:
						# Stop scrolling if the idle time is above the set threshold
						if idle_time >= self.new_tweets_timeout:
							scroll_tweets = False
							self.logger.info(f"No more new tweets has been recorded for the past => {idle_time} seconds. "
											 f"Exiting scroll loop with {len(required_tweets)} tweets...")
						last_tweet.scroll_into_view_if_needed()
					except Error:
						pass
				
				# Wait for some time and start scraping retweets and likes of each tweet
				
				self.scrape_retweets_and_likes(context, required_tweets)
				
				# Close page, context and browser
				for instance in [page, context, browser]:
					instance.close()
			
			self.scrape_usernames_from_comments(required_tweets)
			current_state = "COMPLETED"
			
		except Exception:
			current_state = "FAILED"
			exception_details = traceback.format_exc()
		finally:
			self.update_process(state = current_state, error = exception_details, result = self.collect_result())
		
		self.logger.info(f"Task completed => {self.task_id}")

	def collect_result(self):
		return {"usernames":self.all_usernames,"search_query":self.search_query,"total_usernames":len(self.all_usernames),"total_runtime":abs(self.process_start_time-time.time())}
	
	def scrape_retweets_and_likes(self, context: BrowserContext, required_tweets: List[Dict]):
		""" This method scrapes all usernames from the retweets and likes with the authenticated session """
		self.logger.info(f"Extracting usernames from retweets and likes of {len(required_tweets)} tweets ...")
		tweet_details_page = context.new_page()
		
		for ind_i, tweet in enumerate(required_tweets):
			self.screenshot(page = tweet_details_page, filename = "sweepytrink_tweet_details.png", full_page = False)
			tweet_url = tweet["tweet_url"].rstrip('/')
			tweet_id = tweet["tweet_id"]
			retweets_url = tweet_url + "/retweets"
			likes_url = tweet_url + "/likes"
			
			likes = 0
			retweets = 0
			
			# Scrape retweets and likes count
			tweet_details_page.goto(tweet_url)
			try:
				tweet_details_page.wait_for_selector("article[aria-labelledby] div[role='group'] a")
			except TimeoutError:
				pass
			
			# Extract tweet metadata
			links: List = []
			for _ in range(3):
				try:
					for link_o in tweet_details_page.query_selector("article[aria-labelledby]").query_selector(
							"div[role='group']").query_selector_all("a"):
						# Get the actual link and the value (retweet or like)
						link = link_o.get_property("href").__str__()
						value = parse_humanreadable_string(link_o.query_selector("span").text_content().strip())
						# Get only like and retweet
						last_endpoint: str = link.rsplit("/", 1)[-1]
						if last_endpoint.startswith("retweet"):
							retweets = value
						elif last_endpoint.startswith("like"):
							likes = value
					break
				except Exception as error:
					self.logger.info(f"Exception => {error}")
					tweet_details_page.wait_for_timeout(1)
			
			retweet_usernames = []
			
			retweets_threshold = self.retweets_threshold
			scroll_retweets = retweets > 0  # False if retweets is 0 else True
			idle_time = 0
			start_time = time.time()
			
			
			
			# Limit the number of retweets if they are above threshold
			if retweets <= retweets_threshold:
				retweets_threshold = retweets
			
			self.logger.info(f"Extracting usernames from {retweets} retweets..")
			tweet_details_page.goto(retweets_url)
			retweets_viewport = tweet_details_page.wait_for_selector("div [data-viewportview='true']",
																	 state = "visible", timeout = 0)
			
			# While the retweet usernames is less than the number of total retweets, keep scrolling to get more.
			while len(retweet_usernames) < retweets_threshold and scroll_retweets:
				idle_time = abs(start_time - time.time())
				# Get the retweets
				parser = HTMLParser(retweets_viewport.inner_html())
				retweet_elements: List[Node] = parser.css(
					"div[aria-label='Timeline: Retweeted by'] > div > div[data-testid]")
				
				if not retweet_elements:
					continue
				# Get all usernames in retweets
				for retweet_element in retweet_elements:
					account_hyperlink = retweet_element.css_first("a[href][role='link']")
					if account_hyperlink is None:
						continue
					username = account_hyperlink.attrs["href"].lstrip("/")
					if username not in retweet_usernames:
						start_time = time.time()
						idle_time = 0
						retweet_usernames.append(username)
					self.update_user(username, "retweet", keyword = self.search_query,
															  retweet_id = retweets_url)
				# Get last retweet_element and scroll_into_view
				last_retweet_element = \
					retweets_viewport.query_selector(
						"div[aria-label='Timeline: Retweeted by'] > div > div[data-testid]:last-child")
				try:
					# self.logger.info(f"retweet scroll idle time => {idle_time}s")
					if idle_time > self.new_retweets_timeout:
						scroll_retweets = False
						break
					last_retweet_element.scroll_into_view_if_needed()
				except Error:
					pass
			
			# Scrape usernames in likes
			scroll_likes = likes > 0  # False if likes is 0 else True
			idle_time = 0
			start_time = time.time()
			like_usernames = []
			likes_threshold = self.likes_threshold
			
			# Limit the number of retweets if they are above threshold
			if likes <= likes_threshold:
				likes_threshold = likes
			
			self.logger.info(f"Extracting usernames from {likes} likes..")
			tweet_details_page.goto(likes_url)
			likes_viewport = tweet_details_page.wait_for_selector("div [data-viewportview='true']",
																  state = "visible", timeout = 0)
			
			# While the like usernames is less than the number of total likes, keep scrolling to get more.
			while len(like_usernames) < likes_threshold and scroll_likes:
				idle_time = abs(start_time - time.time())
				# Get the likes
				parser = HTMLParser(likes_viewport.inner_html())
				like_elements: List[Node] = parser.css(
					"div[aria-label='Timeline: Liked by'] > div > div[data-testid]")
				
				if not like_elements:
					# self.logger.info("No likes found !")
					continue
				# Get all usernames in likes
				for like_element in like_elements:
					account_hyperlink = like_element.css_first("a[href][role='link']")
					if account_hyperlink is None:
						continue
					username = account_hyperlink.attrs["href"].lstrip("/")
					if username not in retweet_usernames:
						start_time = time.time()
						idle_time = 0
						retweet_usernames.append(username)
						like_usernames.append(username)
						# self.logger.info(f"Total like usernames => {len(like_usernames)}")
					self.update_user(username, "like", keyword = self.search_query,
															  like_id = likes_url)
				# Get last like_element and scroll_into_view
				last_like_element = \
					likes_viewport.query_selector(
						"div[aria-label='Timeline: Liked by'] > div > div[data-testid]:last-child")
				try:
					# self.logger.info(f"like scroll idle time => {idle_time}s")
					if idle_time > self.new_likes_timeout:
						scroll_likes = False
						break
					last_like_element.scroll_into_view_if_needed()
				except Error:
					pass
		tweet_details_page.close()
	
	def scrape_usernames_from_comments(self, tweets):
		""" This method uses unauthenticated sessions to scrape the usernames from the comments """
		self.logger.info(f"{'*'*50} Scraping all tweet comments {'*'*50}")
		username_sets = set()
		with sync_playwright() as playwright_sync:
			browser = playwright_sync.firefox.launch(headless = True)
			context = browser.new_context()
			for tweet in tweets:
				usernames = self.scrape_tweet_comments(context, tweet)
			context.close()
			browser.close()
	
	def update_user(self,username,_from: Literal["tweet","retweet","comment","like"],**kwargs):
		""" This method calls the create_or_update_user method while collecting some data """
		if username not in self.all_usernames:
			self.all_usernames.append(username)
			self.logger.info(f"Total usernames => {len(self.all_usernames)}")
			
		self.twitter_client.create_or_update_user(username,**kwargs)
	
	def extract_tweet_username(self,item:dict,tweet_id:str) -> str:
		""" Extract the username from the give tweet json data """
		try:
			username = item["tweet_results"]["result"]["core"]["user_results"]["result"]["legacy"]["screen_name"]
			self.update_user(username, "comment", keyword = self.search_query, tweet_id = tweet_id)
			if username not in self.tweet_comment_usernames:
				self.tweet_comment_usernames.append(username)
				self.comments_count += 1
			else:
				self.logger.info("Ignored duplicates..")
		except KeyError:
			self.logger.info("Could not extract username")

	def handle_response(self,response,tweet_id):
		""" This method intercepts all responses as soon as they come in """
		url: str = response.url
		if self.tweet_detail_url_pattern.findall(url).__len__() > 0:
			""" Intercepting only the tweetDetails response from the graphql"""
			self.tweet_graphql_url = url.rsplit("?")[0]
			self.response_headers = response.headers
			self.request_headers = response.request.headers
			json_data = json.loads(response.body())
			self.parse_graphql_data(json_data, search_keyword = self.search_query, tweet_id = tweet_id)
			if self.comments_start_time > 0:
				self.comments_start_time = time.time()
				self.comments_scroll_idle = 0
	
	def scrape_tweet_comments(self, context, tweet):
		""" This method extract the commented usernames from a single tweet """
		self.tweet_comment_usernames = []
		self.json_data = {}

		self.response_headers = {}
		self.request_headers = {}
		self.tweet_graphql_url = ""
		
		self.comments_count = 0
	
		tweet_url = tweet["tweet_url"].rstrip('/'
											  )
		search_keyword = tweet.get("search_keyword",None)
		tweet_id = tweet["tweet_id"]
		self.logger.info(f"Scraping tweet comments => {tweet_id}")
		
		page = context.new_page()
		page.set_default_timeout(10000)
		
		page.on("response", lambda response:self.handle_response(response,tweet_id))
		page.goto(tweet_url,timeout = 0)
		
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
		# try:
		# 	page.get_by_role("button", name = "Show more replies").click()
		# except TimeoutError:
		# 	self.logger.info("Unable to click show-more-replies button ..")
		
		self.comments_start_time = time.time()
		self.comments_scroll_idle = 0
		scroll_comments = True
		while self.comments_count <= self.comments_threshold and scroll_comments:
			self.comments_scroll_idle = abs(time.time()-self.comments_start_time)
			
			conversation_containers = timeline_conversation_container.query_selector_all("div[data-testid='cellInnerDiv']")
			if conversation_containers:
				last_conversation_container = conversation_containers[-1]
				try:
					if self.comments_scroll_idle > self.comments_scroll_timeout:
						scroll_comments = False
						self.comments_start_time = 0
						self.comments_scroll_idle = 0
						break
					last_conversation_container.scroll_into_view_if_needed()
				except Error:
					pass
		page.close()
		
		
	def parse_graphql_data(self,graphql_data:dict,tweet_id:str, search_keyword:str) -> List[Optional[str]]:
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
		
	
	def start_process(self) -> str:
		""" Starts a task in a new process and returns the task_id """
		new_process = Process(target=self.run,daemon=True)
		
		# Start the process
		new_process.start()
		
		return self.task_id
	
	def update_process(self,state: Literal["FAILED","COMPLETED","RUNNING","STARTING"],error:Optional[str]=None,result:Optional[Dict] = None):
		json_string = json.dumps({"state":state,"result":result,"task_id":self.task_id,"error":error})
		self.redis_client.set(self.task_id,json_string)
	

if __name__ == "__main__":
	crawler = TwitterCrawler(uuid.uuid4().hex,"tinubu", max_tweets = 500, max_retweets = 3000, max_comments = 3000, max_likes = 3000)
	task_id = crawler.run()
	
	logger.info(f"Task ID => {task_id}")
