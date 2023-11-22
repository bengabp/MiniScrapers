import scrapy
from booktoscrape.items import BooktoscrapeItem


class BookSpider(scrapy.Spider):
	name = "bookspider"
	start_urls = ["https://books.toscrape.com/catalogue/category/books_1/index.html"]
	RATINGS = {
		"one":1,
		"two":2,
		"three":3,
		"four":4,
		"five":5
	}

	def parse(self,response):
		item = BooktoscrapeItem()

		for book in response.css("article.product_pod"):
			book_title = book.css(".image_container img").attrib["alt"]
			book_rating = self.RATINGS[book.css("p.star-rating")[0].attrib["class"].split(" ")[1].lower()]
			book_price = book.css(".price_color::text").get()

			item["name"] = book_title
			item["rating"] = book_rating
			item["price"] = book_price

			yield item

		burl = "https://books.toscrape.com/catalogue/category/books_1/"
		next_page = response.css(".next>a").attrib["href"]
		if next_page is not None:
			print("Scraping next page")
			yield response.follow(f"{burl}{next_page}",callback=self.parse)
