from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
from redis import Redis
from config import REDIS_HOST, REDIS_PORT, REDIS_TASKS_DB
import json
from typing import Optional, List, Dict, Literal
import json
import pandas
from container_manager import start_crawler_instance, get_containers, delete_container
from mongo_utils import TwitterMongoClient


api = FastAPI()

api.mount("/static", StaticFiles(directory="static"), name="static")
# api.mount("/output", StaticFiles(directory="static"), name="output")

templates = Jinja2Templates(directory="templates")

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_TASKS_DB)
twitter_client = TwitterMongoClient()

origins = ['*']

api.add_middleware(
	CORSMiddleware,
	allow_origins=origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)


def get_crawler_details(crawler_id) -> Dict:
	""" Gets the crawler details from the redis database using its id """
	details = {}

	if not crawler_id:
		return details

	try:
		json_string = redis_client.get(crawler_id)
		# parse json
		details = json.loads(json_string)
	except json.JSONDecodeError:
		pass

	return details


def build_csv(crawler_details):
	pass


@api.get("/")
async def index(request: Request):
	return templates.TemplateResponse("index.html", {"request": request, "range": range(20)})


@api.get("/tasks")
async def get_tasks(request: Request, task_id: str = None):
	if task_id:
		task_details = get_crawler_details(task_id)
		return {"message": "Success", "data": task_details}

	keys = [key.decode('utf-8') for key in redis_client.keys()]
	tasks = [json.loads(redis_client.get(tid)) for tid in keys if tid.startswith("crawler-")]

	return {
		"message": "All tasks",
		"tasks": tasks,
		"total_tasks": len(tasks)
	}


@api.post("/tasks")
async def create_task(request: Request, q: Optional[str] = None):
	""" This function initializes a celery task """
	form_data = {}

	try:
		form_data = await request.json()
	except json.decoder.JSONDecodeError:
		pass
	print(form_data)

	q = form_data.get("search_q")
	max_comments = form_data.get("comments")
	max_likes = form_data.get("likes")
	max_retweets = form_data.get("retweets")

	if not q and not max_comments and not max_likes and not max_retweets:
		return {"message": "Please specify a json body", "status": "failed"}

	# Generate task id to use for new task
	task_id = "crawler-" + uuid.uuid4().hex

	conf = start_crawler_instance(task_id, q, max_comments, max_retweets, max_likes)

	# crawl.delay(task_id, q,
	# 			{"max_retweets": max_retweets,
	# 			 "max_comments": max_comments,
	# 			 "max_likes": max_likes})

	return {"message": "Task queued", "task_id": task_id, "status": "success"}


@api.get("/download/csv")
def download_as_csv(request: Request, crawler_id: str):
	crawler_details = get_crawler_details(crawler_id)
	if not crawler_details:
		# Crawler not found
		return RedirectResponse("/")

	usernames = crawler_details["result"]["usernames"]
	csv_data = [{"ScreenName":username,"Email":get_user_email(username)} for username in usernames]
	# Return file response
	return FileResponse(download_file_path,media_type="text/csv")