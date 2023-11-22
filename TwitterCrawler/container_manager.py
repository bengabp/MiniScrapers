import docker
from docker.errors import NotFound
from dotenv import dotenv_values
from uuid import uuid4

client = docker.from_env()


def start_crawler_instance(task_id, search_query, comments, retweets, likes, env_path=".env", image_name="crawler:v1"):
	# Set environment variables as key-value pairs
	env = dotenv_values(env_path)

	env["SEARCH_QUERY"] = search_query
	env["WORKER_ID"] = task_id
	env["COMMENTS_USERNAMES_PER_TWEET"] = comments
	env["RETWEETS_USERNAMES_PER_TWEET"] = retweets
	env["LIKES_USERNAMES_PER_TWEET"] = likes

	# Create the container

	container = client.containers.run(name=task_id, image=image_name, environment=env, detach=True,
									  command="python3 /app/TwitterCrawler/crawler.py", network="crawlernet")
	return {"container_id": container.id, "container_name": container.name}


def delete_container(container_name: str):
	""" This function stops and removes the specified docker container """

	try:
		target_container = client.containers.get(container_name)
		target_container.stop()
		target_container.remove()

	except NotFound:
		pass


def get_containers():
	containers = client.containers.list(all=True, filters={"name": "crawler-"})
	return containers
