BACKEND := backend
PY := .venv/bin/python

.PHONY: install models seed train test test-slow lint chat run-backend run-frontend

install:
	cd $(BACKEND) && python3 -m venv .venv && $(PY) -m pip install --upgrade pip && $(PY) -m pip install -r requirements.txt
	cd frontend && [ -f package.json ] && npm install || true

models:
	cd $(BACKEND) && $(PY) scripts/download_models.py

seed:
	cd $(BACKEND) && $(PY) -m app.db.seed

train:
	cd $(BACKEND) && $(PY) -m app.nlu.train

test:
	cd $(BACKEND) && $(PY) -m pytest

test-slow:
	cd $(BACKEND) && RUN_SLOW=1 $(PY) -m pytest -m slow

lint:
	cd $(BACKEND) && $(PY) -m ruff check . && $(PY) -m ruff format --check .

chat:
	cd $(BACKEND) && $(PY) -m app.cli

run-backend:
	cd $(BACKEND) && $(PY) -m uvicorn app.main:app --reload

run-frontend:
	cd frontend && npm run dev
