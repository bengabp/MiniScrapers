FROM mcr.microsoft.com/playwright/python:v1.34.0-jammy
RUN apt -y update
RUN apt -y upgrade

RUN pip install --upgrade pip

# Set working directory in the container
WORKDIR /app

# Copy all files from local directory to app container directory
COPY . /app/TwitterCrawler

# Change working directory to project dir
WORKDIR /app/TwitterCrawler

# Install dependencies
RUN pip install -r requirements.txt

RUN apt install -y docker.io
