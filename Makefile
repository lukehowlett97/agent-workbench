.PHONY: install lint test run compose-up compose-down

install:
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check .

test:
	python -m pytest

run:
	uvicorn agent_workbench.main:app --host 127.0.0.1 --port 8000 --reload

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down
