import json
import random
import pandas as pd
import requests
import threading
import time

from user_agents import USER_AGENTS
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import selenium


class ScraperBot:
    def __init__(self, postcodes_excel_file):
        self.postcodes_json_file = "postcodes.json"
        self.postcodes_excel_file = postcodes_excel_file
        self.proxy_ips_file = "valid_proxies.txt"
        self.valid_ips = []

        try_load = True
        while try_load:
            try:
                self.postcodes = self.load_postcodes()
                try_load = False
                break
            except FileNotFoundError:
                self.generate_json_postcodes()
        print("Loaded", len(self.postcodes), "Postcodes")
        self.proxy_ips = self.load_proxy_ips()
        self.log(f"Loaded {len(self.proxy_ips)} Proxies", new_line=True)

    def create_driver(self) -> uc.Chrome:
        options = Options()
        options.add_argument('--no-sandbox')
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920x1080')
        options.add_argument(f'user-agent={self.get_random_user_agent()}')
        chrome = uc.Chrome(options=options)
        return chrome

    def validate_ip(self, ip):
        """ This method runs on its own thread """
        print("Checking ip:", ip)
        url = "http://ipinfo.io/json"
        try:
            res = requests.get(url, headers={"User-Agent": self.get_random_user_agent()},
                               proxies={"http": ip, "https": ip})
            json_ = res.json()
            country = json_["country"]
            region = json_["region"]
            print(f"Country:{country}/Region:{region}")
            self.valid_ips.append(ip)
            self.save_valid_ips()
        except Exception as error:
            pass
        self.count += 1
        self.log(f"Count=>{self.count}", new_line=True)

    def save_valid_ips(self):
        with open("valid_proxies.txt", "w") as sf:
            self.log("Saving valid ip proxies..", new_line=True)
            sf.write("\n".join(self.valid_ips))
            self.log("Done saving...", new_line=True)

    def test_ips(self):
        self.count = 0
        self.start_time = time.time()

        self.log(f"Checking ips|Total ips={len(self.proxy_ips)}", new_line=True)
        threads = [threading.Thread(target=self.validate_ip, args=[ip]).start() for ip in self.proxy_ips]

    def log(self, message, new_line=False):
        print(message)
        if new_line:
            print("-" * 100, "\n")

    def generate_json_postcodes(self):
        self.log("Loading post codes from excel file ... ")
        dataframe = pd.read_excel(self.postcodes_excel_file)
        dictionary = dataframe.to_dict()
        self.log("Done loading ... ", new_line=True)
        self.log("Writing to json file ... ")
        postcodes = list(dictionary['postcode'].values())
        with open(self.postcodes_json_file, "w") as post_codes_json:
            json.dump({"postcodes": postcodes}, post_codes_json, indent=4)
        self.log("Done writing .", new_line=True)

    def load_postcodes(self):
        self.log("Loading postcodes from json file...")
        postcodes = None
        with open(self.postcodes_json_file) as post_codes_json:
            postcodes = json.load(post_codes_json)
        self.log("Done loading postcodes from json file.", new_line=True)
        return postcodes["postcodes"]

    def load_proxy_ips(self):
        proxy_ips = []
        with open(self.proxy_ips_file) as proxy_file:
            proxy_ips = proxy_file.readlines()
        return [ip.strip() for ip in proxy_ips if len(ip.strip()) > 5]

    def get_random_proxy_ip(self):
        return random.choice(self.proxy_ips)

    def get_random_user_agent(self):
        return random.choice(USER_AGENTS)

    def get_address_data(self, address_element: selenium.webdriver.remote.webelement.WebElement) -> dict:
        link = address_element.get_dom_attribute("href")
        driver = self.create_driver()
        url = f"https://scotlis.ros.gov.uk{link}"
        driver.get(url)
        print(driver.title)

        title_number = driver.find_element(By.ID, "property-details-title-number").text
        address = driver.find_element(By.ID, "property-details-address").text
        last_purchase_price = driver.find_element(By.ID, "property-details-last-purchase-price").text.split("What")[0]
        last_purchase_date = driver.find_element(By.ID, "property-details-last-purchase-date").text
        land_registered = driver.find_element(By.ID, "property-details-land-register-status").text
        interest = driver.find_element(By.ID, "property-details-interest").text.split("What")[0]
        property_type = driver.find_element(By.ID, "property-details-property-type").text.split("What")[0]
        historical_prices_table_rows = driver.find_elements(By.CSS_SELECTOR, "[data-testid] tr")[1:]

        historical_prices = []

        for tr in historical_prices_table_rows:
            date, price = tr.find_elements(By.TAG_NAME, "td")
            historical_prices.append({
                "date": date.text,
                "price": price.text.split("What")
            })

        return {
            "title_number": title_number,
            "address": address,
            "last_purchase_price": last_purchase_price,
            "last_purchase_date": last_purchase_date,
            "land_registered": land_registered,
            "interest": interest,
            "property_type": property_type,
            "historical_prices": historical_prices
        }

    def get_postcode_addresses(self, postcode):
        self.log(f"Checking postcode {postcode}")
        url = f"https://scotlis.ros.gov.uk/results?searchType=titles&postcode={postcode}"
        try:
            driver = self.create_driver()
            driver.get(url)
            print(driver.title)
            n_results = driver.find_element(By.XPATH, '//*[@id="main-content"]/p')
            print(n_results.text)
            nr, _ = n_results.text.split(" ", 1)
            if nr.isdigit():
                self.log("Got something... scraping each address..",new_line=True)
                links_datas = [self.get_address_data(link) for link in
                               driver.find_elements(By.XPATH, "//a[@class='govuk-link']") if
                               postcode in link.text]
                self.save_data_to_json(links_datas,"result.json")

        except Exception as error:
            print("Error:", error)

    def save_data_to_json(self, data, filename):
        self.log(f"Saving data to {filename}",new_line=True)
        with open(filename, "a") as f:
            json.dump(data,f)
        self.log("Done saving..",new_line=True)


if __name__ == "__main__":
    scraper = ScraperBot("Scotland_post_codes_2.xlsx")
    for postcode in scraper.postcodes[117300:117320]: # Creates 20 requests/threads
        """ Code to create and start new thread ... """
        new_thread = threading.Thread(target=scraper.get_postcode_addresses,args=[postcode])
        new_thread.start()

        # scraper.get_postcode_addresses(postcode)
