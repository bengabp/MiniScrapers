# Download the helper library from https://www.twilio.com/docs/python/install
import os
from twilio.rest import Client
from dotenv import load_dotenv
import requests
import json
import base64


load_dotenv(".env")

MAYTAPI_URL = os.environ["MAYTAPI_URL"]
MAYTAPI_APIKEY = os.environ["MAYTAPI_APIKEY"]


def broadcast_product_to_magalu_whatsapp_group(product_image, message: str,
                                               group_id: str = "120363046709726131@g.us") -> dict:
	""" Sends product to whatsapp magalu group """

	product_image = base64.b64encode(requests.get(product_image).content).decode('utf-8')

	payload = json.dumps({
		"to_number": group_id,
		"type": "media",
		"message": f"data:image/png;base64,{product_image}",
		"text": message
	})
	headers = {
		'x-maytapi-key': MAYTAPI_APIKEY,
		'Content-Type': 'application/json'
	}

	response = requests.request("POST", MAYTAPI_URL, headers=headers, data=payload)
	json_response: dict = response.json()
	return json_response
