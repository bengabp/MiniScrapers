# TwitterCrawler
Powerful crawler for scraping usernames from tweets, retweets, comments and likes. 
The playwright library was used to automate twitter using authenticated and 
non-authenticated browser sessions called `contexts`. All usernames for now
are saved in a mongodb collection for future analysis / data extraction.

### This project consists of 2 modules
- Api server
- Crawler Image

### The Api script
The api script listens for requests to create new tasks or 
get task status using its id.
When a post request for a new task is received, the api runs a docker container using the parameters for the search.
When the task has finished running, the client has to send a request to delete it. The Containerization of
each crawler instance isolates all browser instances, increasing speed and performance.

### Crawler Image
The crawler image is used by the api to run a new crawler container.To build the crawler image, Run
```commandline
docker build -t crawler:v1 . 
```
Please note that the name and tag of this image must be `crawler:v1`

### Running the api server
The api server has a few dependencies so a docker-compose file 
has been written to make it easier to deploy the whole system.

Make sure to create a network called crawlernet using `docker network create crawlernet`.
Then start the server:

```commandline
docker-compose up
```