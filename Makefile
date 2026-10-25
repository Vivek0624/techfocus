API=services/api
PY=$(API)/.venv/bin

.PHONY: install dev stop test test-api test-web lint typecheck fmt migrate evals key rotate-keys build-agentcore smoke

install:
	cd $(API) && ([ -d .venv ] || uv venv -p 3.13 .venv) && uv pip install --python .venv/bin/python -e ".[agents,dev]"
	cd apps/web && npm ci || (cd apps/web && npm install)

dev:
	./dev.sh

stop:
	./stop.sh

migrate:
	cd $(API) && .venv/bin/alembic upgrade head

test: test-api test-web

test-api:
	cd $(API) && .venv/bin/pytest -q

test-web:
	cd apps/web && npm test

lint:
	cd $(API) && .venv/bin/ruff check app tests evals
	cd apps/web && npm run lint

fmt:
	cd $(API) && .venv/bin/ruff check --fix app tests evals && .venv/bin/ruff format app tests evals

typecheck:
	cd $(API) && .venv/bin/mypy app
	cd apps/web && npm run typecheck

evals:
	cd $(API) && DATABASE_URL=sqlite:///./data/evals.db .venv/bin/python -m evals.run_evals

key:
	$(PY)/python scripts/gen_key.py

rotate-keys:
	$(PY)/python scripts/rotate_keys.py

build-agentcore:
	services/agents/build.sh
