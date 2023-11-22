import selenium.common.exceptions
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import requests
from selenium.webdriver.support.wait import WebDriverWait, TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from telethon.sync import TelegramClient, events
from telethon.tl.types import PeerChat, PeerUser, User, PeerChannel
from telethon import types, functions
from dotenv import load_dotenv
import os
from pprint import pprint
import json
import re
import pickle
import random
import time
from lxml import etree, html
import urllib
import asyncio

from whatsapp_service import broadcast_product_to_magalu_whatsapp_group

load_dotenv(".env")

API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
PHONE_NUMBER = os.environ.get("PHONE_NUMBER")


class MagaluAffiliateBot:
	def __init__(self, client: TelegramClient, channel_entity):
		self.client = client
		self.channel_entity = channel_entity

		self.password = os.environ['MAGALU_ACCOUNT_PASSWORD']
		self.cuttly_apikey = os.environ["CURTLY_APIKEY"]
		self.email = os.environ['MAGALU_ACCOUNT_EMAIL']
		self.magalu_affiliate_group_id = os.environ['MAGALU_WHATSAPP_GROUP_ID']
		self.TOP_PHRASES = [
			"📢 DESCONTÃO ROLANDO 🚨",
			"📢 PROMO IMPERDÍVEL 🚨",
			"📢 MUUUITO BARATO 😱",
			"📢 VALENDO MUUUITO A PENA 😱",
			"📢 DESCONTO TOP 🚨",
			"📢 DESCONTÃO INCRÍVELLLL!!! 😱👏🏻",
			"📢 NO PRECINHOOOO 🚨"
		]
		self.BOTTOM_PHRASES = [
			"⚠️ CORRE QUE O ESTOQUE É LIMITADO ⚠️",
			"⚠️ TÁ SAINDO MUITO RÁPIDO ⚠️",
			"⚠️ DESCONTO POR TEMPO LIMITADO ⚠️",
			"⚠️ ÚLTIMAS UNIDADES ⚠️",
			"⚠️ JÁ COM DESCONTO ⚠️",
			"⚠️ NÃO FIQUE SEM O SEU ⚠️",
			"⚠️ ÚLTIMA HORA DE DESCONTO ⚠️"
		]

		self.magalu_url = "https://www.magazinevoce.com.br/magazinecostasilvestre/"
		self.magalu_login_url = "https://www.magazinevoce.com.br/magazinecostasilvestre/login/?next=/magazinecostasilvestre/"
		self.product_details_url = "https://www.magazinevoce.com.br/magazinecostasilvestre/busca/"
		self.magalu_product_id_pattern = re.compile(r"(Código: [a-z0-9]{9,10})")

		options = ChromeOptions()
		options.add_argument("-start-maximized")

		self.driver = uc.Chrome(version_main=108, options=options)
		self.initialize_session()

	def initialize_session(self) -> bool:
		self.driver.get(self.magalu_login_url)
		email_input = self.driver.find_element(By.ID, "email")
		password_input = self.driver.find_element(By.ID, "password")

		email_input.send_keys(self.email)
		password_input.send_keys(self.password)

		while True:
			print(
					"Waiting for user to login... Please complete the login, the email and password has been entered accordingly.")
			status = input("Have you logged in: y or n ?  ")
			if status == "y":
				print("Logged in, Starting Message WatchDog :] ...")
				self.client.add_event_handler(self.on_new_message, events.NewMessage(channel_entity))
				print("Waiting for new messages ...")
				return True
			elif status == "n":
				print("Please login from the browser and do not close this browser..")
			else:
				print("Valid responses are 'y' or 'n'")

	async def on_new_message(self, event):
		print("New message captured !")
		codigo = [(text.strip()) for text in self.magalu_product_id_pattern.findall(event.message.message)]
		if codigo:
			codigo = codigo[0].split(" ")[1]
			self.driver.get(self.product_details_url + codigo)
			await asyncio.sleep(10)
			product_details = None

			items = self.driver.find_elements(By.CSS_SELECTOR, "li.g-item")

			if len(items) > 1:
				return False

			redirected = False
			product_name = ""
			product_image = ""
			installments = ""

			try:
				product_details = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(
						(By.CSS_SELECTOR, '.g-item a img')))
				product_image = product_details.get_dom_attribute("src")
				product_name = self.driver.find_element(By.CSS_SELECTOR, ".g-item .g-title").text.strip()
				product_details.click()
				redirected = True
			except Exception as error:
				pass

			if product_details is not None and redirected:
				await asyncio.sleep(10)
				# Getting personalized affiliate link
				personalized_affiliate_link = ""

				def get_affiliate_link():
					try:
						affiliate_link = self.driver.find_element(By.XPATH, '//*[@id="copy"]')
						affiliate_link = affiliate_link.get_attribute("data-clipboard-text")
						affiliate_link = self.shorten_link(affiliate_link)
						return affiliate_link
					except selenium.common.exceptions.NoSuchElementException:
						return None

				while True:
					personalized_affiliate_link = get_affiliate_link()
					if personalized_affiliate_link:
						break
					else:
						if self.driver.title.lower() == 'magazine costasilvestre':
							print("Unable to find personalized affiliate link element")
							print("Retrying..")
							product_details.click()
							await asyncio.sleep(5)
						else:
							break

				# Price and Discount Information
				before_price = ""
				after_price = ""
				discount = ""
				try:
					p_image = self.driver.find_element(By.CSS_SELECTOR, f"img[alt^='{product_name}']")
					product_image = p_image.get_dom_attribute("src")
				except:
					pass

				try:
					before_price = self.driver.find_element(By.XPATH,
					                                        '//*[@id="pdetail"]/div[3]/div/div[2]/div[2]/div/div[3]/div[1]/small').text.split(
							" ", 1)[1]
				except:
					pass
				try:
					after_price = self.driver.find_element(By.CSS_SELECTOR, ".p-price > strong").text
				except:
					pass
				try:
					pattern = re.compile(r"à vista \([0-9]+% Desc. já calculado.\)")
					parser = html.fromstring(self.driver.page_source)
					matches = pattern.findall(parser.body.text_content())
					if len(matches) > 0:
						discount = matches[0]
				except:
					pass

				try:
					installments_e = self.driver.find_element(By.CSS_SELECTOR,".info .p-installment span")
					installments = installments_e.text.strip()
				except:
					pass

				self.send_to_whatsapp(personalized_affiliate_link, product_image=product_image,
				                      product_name=product_name, before_price=before_price, after_price=after_price,
				                      discount=discount,installments=installments)

			else:
				print("Not found")
		print("Run completed !", end="\n\n")

	def shorten_link(self, link) -> str:
		url = urllib.parse.quote(link)
		r = requests.get('http://cutt.ly/api/api.php?key={}&short={}'.format(self.cuttly_apikey, url))
		try:
			return r.json()["url"]["shortLink"]
		except json.JSONDecodeError:
			print(response.text)
			return link

	def send_to_whatsapp(self, personalized_affiliate_link, product_image, product_name, before_price, after_price,
	                     discount,installments) -> bool:
		before_price_string = f"\n\nDE ~{before_price}~" if before_price else ""
		discount_string = f'\n*{discount.removeprefix("à vista").strip()}*' if discount else ""

		message = f"*{random.choice(self.TOP_PHRASES)}*" \
		          f"\n\n{product_name.upper()}\n" \
		          f"{before_price_string}" \
		          f"\n*🔥🔥 POR APENAS {after_price} à vista*" \
		          f"{discount_string}" \
				  f"\nou {installments}" \
		          f"\n\n*{random.choice(self.BOTTOM_PHRASES)}*" \
		          f"\n\n```LINK DE COMPRA```" \
		          f"\n*🔗 {personalized_affiliate_link}*" \
		          f"\n*🔗 {personalized_affiliate_link}*" \
		          f"\n*🔗 {personalized_affiliate_link}*"

		response = broadcast_product_to_magalu_whatsapp_group(product_image, message, self.magalu_affiliate_group_id)
		print("Whatsapp Broadcast complete => ", response)
		return False


if __name__ == "__main__":
	with TelegramClient(PHONE_NUMBER, int(API_ID), API_HASH) as client:
		# MAGALU_TELEGRAM_GROUP_ID = os.environ["MAGALU_TELEGRAM_GROUP_ID"]
		# channel_entity = client.get_entity(MAGALU_TELEGRAM_GROUP_ID)
		channel_entity = PeerChannel(1217820058)
		magaluAffiliateBot = MagaluAffiliateBot(client, channel_entity)
		client.run_until_disconnected()
