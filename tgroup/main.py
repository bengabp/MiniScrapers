import pandas
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest
from telethon.tl.types import ChannelParticipantsSearch, User, InputUser, InputPeerChannel, InputChannel
from telethon.errors.rpcerrorlist import UserPrivacyRestrictedError, FloodError, FloodWaitError, PhoneNumberBannedError
import os
from typing import Optional, List, Dict
from dotenv import load_dotenv
from schemas import Member, Client
import pandas
from config import BASE_PATH

load_dotenv(".env")


class Scraper:
	def __init__(self):
		""" Main initialization method """
		self.target_group_username = "stock_group"
		self.add_to_group_id = "mems3763"
		
		self.session_df = pandas.read_csv("data/sessions.csv")
		print(self.session_df)
		self.clients: List[TelegramClient] = []
		self.init_clients()
	
	def init_clients(self):
		""" Initializes and authenticates all clients from the csv file """
		
		for client_dict in self.session_df.to_dict(orient = "records"):
			name = client_dict["SessionName"]
			phone_number = client_dict["PhoneNumber"]
			api_id = int(client_dict["ApiId"])
			api_hash = client_dict["ApiHash"]
			print(f"Initializing client => {name} => {phone_number}")
			client = TelegramClient(os.path.join("sessions", name), api_id, api_hash)
			try:
				client = self.connect(client, phone_number)
				self.clients.append(client)
			except PhoneNumberBannedError:
				pass
	
	def connect(self, client: TelegramClient, phone_number: str):
		""" initializes a connection to the telegram server """
		print("Connecting ...")
		client.connect()
		# Ensure user is logged in
		if not client.is_user_authorized():
			client.send_code_request(phone_number)
			client.sign_in(phone_number, input("Enter verification code: "))
		else:
			print(f"{phone_number} is Logged in")
			
		return client
	
	def run(self):
		""" This method starts the crawler """
		
		# Get all participants from the group
		group_entity = self.clients[0].get_entity(self.target_group_username)
		participants = self.clients[0].get_participants(group_entity, search = "", aggressive = True)
		
		# Extract username and phone number from each participant
		participant: Optional[User] = None
		
		print("Extracting members ...")
		data = []
		input_users = []
		for participant in participants:
			member = Member(
				uid = participant.id,
				username = participant.username,
				firstname = participant.first_name,
				lastname = participant.last_name,
				phone_number = participant.phone
			)
			data.append(member.model_dump())
			input_user = InputUser(
				participant.id, participant.access_hash
			)
			input_users.append(input_user)
		
		# Convert to dataframe
		df = pandas.DataFrame(data)
		df.to_csv(os.path.join(BASE_PATH, "groups", f"{self.target_group_username}_members.csv"), index = False)
		print(f"Extracted {len(data)} members to csv file")
		
		# Add members to group
		# self.add_members_to_group(input_users)
		
		# Disconnect clients from server
		for client in self.clients:
			client.disconnect()
	
	def add_members_to_group(self, members: List[InputUser]):
		# self.connect()
		print(f"Adding {len(members)} to group ...")
		entity = self.clients[0].get_entity(self.add_to_group_id)
		channel = InputChannel(entity.id, entity.access_hash)
		
		# TODO : Implementing account switching
		for input_user in members:
			print(f"Sending request for {len(members)} members")
			add_request = AddChatUserRequest(
				1635652607, "bengabp"
			)
			try:
				self.clients[0](add_request)
			
			except UserPrivacyRestrictedError:
				pass
			print("Success !")
			# self.client(InviteToChannelRequest(
			# 	channel,
			# 	input_members
			# ))
			# print("success !")


if __name__ == "__main__":
	scraper = Scraper()
	scraper.run()
# scraper.add_members_to_group([])
