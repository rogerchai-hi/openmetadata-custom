up:
	docker compose -f docker\openmetadata\docker-compose-postgres.yml up --detach

# 	docker network connect om-net openmetadata_server
# 	docker network connect om-net openmetadata_ingestion