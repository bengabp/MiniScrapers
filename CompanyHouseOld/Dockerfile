FROM sleekybadger/libpostal:1.1-alpha-alpine as libpostal-build
FROM python:3.8-alpine

RUN pip install --upgrade pip

# Set working directory in the container
WORKDIR /app

COPY --from=libpostal-build /data /data
COPY --from=libpostal-build /usr/lib/libpostal.so /usr/lib/libpostal.so
COPY --from=libpostal-build /usr/lib/libpostal.so.1 /usr/lib/libpostal.so.1
COPY --from=libpostal-build /usr/include/libpostal /usr/include/libpostal

RUN apk add --no-cache build-base

# Copy all files from local directory to app container directory
COPY . /app/CompanyHouse

# Change working directory to project dir
WORKDIR /app/CompanyHouse

# Install dependencies
RUN pip install -r requirements.txt
