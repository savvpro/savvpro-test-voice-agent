.PHONY: test run api ui docker seed

test:
	cd backend && .venv/bin/pytest -v || (cd backend && python -m pytest -v)

api:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

ui:
	cd frontend && npm run dev

docker:
	docker compose up --build

seed:
	curl -s -X POST -H "X-Admin-Password: $${ADMIN_PASSWORD:-admin}" http://127.0.0.1:8000/api/admin/seed
