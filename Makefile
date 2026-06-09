lint:
	docker compose exec assistant ruff check app

format:
	docker compose exec assistant ruff format app
