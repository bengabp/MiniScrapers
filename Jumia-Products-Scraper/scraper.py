from lxml import etree, html
import requests
import random
import json
from pprint import pprint
import asyncio
from httpx import AsyncClient

from config import USER_AGENTS


class CategoriesIncompleteError(Exception):
	pass


class Scraper:
	def __init__(self):
		""" Initializes all attributes and configurations """

		self.jumia_url = "https://www.jumia.com.ng"
		self.categories_file = "categories.json"
		self.categories = self.load_categories()

	def load_categories(self):
		""" Loads all categories from json file or extracts them from the jumia landing page"""
		print("Loading categories ... ")
		with open(self.categories_file) as saved:
			categories = None
			try:
				categories = json.load(saved)
				for key, value in categories.items():
					if not value: raise CategoriesIncompleteError(
							"Categories not complete, Please re-extract from page")

			except (json.JSONDecodeError, CategoriesIncompleteError):
				print("Error loading categories, Extracting from Jumia")
				self.extract_categories()
				return self.load_categories()

			return categories

	def random_useragent(func):
		def wrapper(self, *args):
			print(f"Called {func.__name__}")
			random_user_agent = random.choice(USER_AGENTS)
			return func(self, random_user_agent, *args)

		return wrapper

	def get_random_useragent(self):
		return random.choice(USER_AGENTS)

	def save_html_to_file(self, html, filename):
		with open(filename, "w") as save:
			print(html, file=save)

	@random_useragent
	def extract_categories(self, user_agent: str):
		landing_page_response = requests.get(headers={"User-Agent": user_agent}, url=self.jumia_url)
		parser = html.fromstring(landing_page_response.text)
		flyout_container = parser.xpath('//*[@id="jm"]/main/div[1]/div[1]/div[1]/div')
		if len(flyout_container) > 0:
			flyout_container = flyout_container[0]
			a_tags = flyout_container.findall("a")
			categories = {}
			for a_tag in a_tags:
				href: str = a_tag.get("href")
				name = a_tag.find("span").text
				if href is not None:
					if href.startswith("/"):
						href = self.jumia_url + href
					sub_categories = self.get_category_subcategory(href)
					categories[name] = sub_categories
			with open("categories.json", "w") as save:
				json.dump(categories, save, indent=4)
		else:
			print("No data found ... RE-STARTING...")
			self.extract_categories()

	@random_useragent
	def get_category_subcategory(self, user_agent, category_link):
		while True:
			a_tags_csslector = "div.row a[data-id^='catalog_category_category']"
			landing_page_response = requests.get(headers={"User-Agent": user_agent}, url=category_link)
			parser = html.fromstring(landing_page_response.text)
			atags = parser.cssselect(a_tags_csslector)
			datas = {}
			i = 0
			for a in atags:
				p = a.find("p")
				if p is not None and i < 12:
					href = a.get("href")
					datas[p.text] = href
					i += 1
			if datas: return datas
			user_agent = self.get_random_useragent()

	async def scrape_products(self, session, category, subcategory, link):
		print(subcategory)
		i = 1
		product_cssselector = f"a.core"
		not_found_xpath = '//*[@id="jm"]/main/div/div[1]/h2'
		category_products = []
		scrape = True
		while scrape:
			formatted_url = f"{link}?page={i}"
			user_agent = self.get_random_useragent()
			products_page = await session.get(formatted_url, headers={"User-Agent": user_agent})
			results = products_page.read().decode("utf-8")
			try:
				parser = html.fromstring(results)
				not_found = parser.xpath(not_found_xpath)
				products = parser.cssselect(product_cssselector)
				if len(not_found) == 0:
					for product in products:
						img, info = product.findall("div")
						name = info.find("h3").text
						price = info.cssselect(".prc")
						if len(price)>0:
							price = price[0].text
							naira,price = price.split(" ")
							price = price.replace(",","")
							category_products.append({
								"name": name,
								"price": price,
								"category":f"{category}/{subcategory}"
							})
				else:
					scrape = False
			except Exception:
				pass

			i += 1
			print("I => ",i)

		return category_products

	async def scrape_asynchronously(self):
		session = AsyncClient()
		tasks = []
		for key, value in self.categories.items():
			for subkey, link in value.items():
				tasks.append(self.scrape_products(session, key, subkey, link))
		session.aclose()
		results = await asyncio.gather(*tasks)
		with open("results.json","w") as s:
			json.dump(results,s,indent=4)

	def run(self):
		r = asyncio.run(self.scrape_asynchronously())


if __name__ == "__main__":
	scraper = Scraper()
	scraper.run()
# print(result)
