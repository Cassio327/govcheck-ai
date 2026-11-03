SHELL := /bin/bash
API_DIR := apps/api
WEB_DIR := apps/web
API_PYTHON ?= $(if $(wildcard $(API_DIR)/.venv/bin/python),$(abspath $(API_DIR)/.venv/bin/python),python)

.PHONY: install test-api test-db test-retrieval lint-api smoke-embeddings test-web build-web verify dev

install:
	cd $(API_DIR) && python -m pip install -e '.[dev]'
	pnpm --dir $(WEB_DIR) install

test-api:
	cd $(API_DIR) && $(API_PYTHON) -m pytest

test-db:
	cd $(API_DIR) && $(API_PYTHON) -m pytest tests/integration/db -v

test-retrieval:
	cd $(API_DIR) && $(API_PYTHON) -m pytest tests/infrastructure/retrieval tests/integration/retrieval -v

lint-api:
	cd $(API_DIR) && $(API_PYTHON) -m ruff check src tests

smoke-embeddings:
	cd $(API_DIR) && $(API_PYTHON) -m govcheck.infrastructure.embeddings.smoke

test-web:
	pnpm --dir $(WEB_DIR) test

build-web:
	pnpm --dir $(WEB_DIR) build

verify: lint-api test-api build-web

dev:
	docker compose up --build
