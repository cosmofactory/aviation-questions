lint:
	uv run ruff format .
	uv run ruff check . --fix
	uv run ruff check .

type:
# typechecker of ty https://docs.astral.sh/ty/
	uv run ty check
run:
	uv run fastapi dev src/main.py

run_container:
	docker compose up --build

# Alembic block:
# To create a new migration, run the following command:
makemigrations:
	uv run alembic revision --autogenerate
# To apply the migration, run the following command:
migrate:
	uv run alembic upgrade head
# To revert last migration, run the following command:
revert_migration:
	uv run alembic downgrade -1

test:
	uv run pytest
