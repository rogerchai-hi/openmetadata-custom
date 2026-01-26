COMPOSE_CMD = docker compose -f docker-compose-postgres.yml -f docker-compose-postgres.datadrift.yml
INGESTION_IMAGE = openmetadata_ingestion:1.9.8-datadrift1
NGINX_IMAGE = openmetadata_nginx:1.9.8

.PHONY: all build up down

all: build up

build:
	docker build -t $(INGESTION_IMAGE) ./ingestion
	docker build -t $(NGINX_IMAGE) ./nginx

up: build
	cd ./openmetadata && $(COMPOSE_CMD) up -d

down:
	cd ./openmetadata && $(COMPOSE_CMD) down