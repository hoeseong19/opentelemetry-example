freeze:
	pip freeze > requirements.txt

up:
	docker-compose up --build
