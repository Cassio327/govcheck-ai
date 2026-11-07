SHELL := /bin/bash
API_DIR := apps/api
WEB_DIR := apps/web
EVAL_DIR := packages/evaluation
API_PYTHON ?= $(if $(wildcard $(API_DIR)/.venv/bin/python),$(abspath $(API_DIR)/.venv/bin/python),python)
EVAL_PYTHON ?= $(API_PYTHON)

.PHONY: install test-api test-db test-retrieval lint-api smoke-embeddings check-openapi generate-contracts check-contracts test-web build-web eval-test eval-fake eval-live cleanup-expired verify dev

install:
	cd $(API_DIR) && python -m pip install -e '.[dev]'
	python -m pip install -e '$(EVAL_DIR)[dev]'
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

check-openapi:
	cd $(API_DIR) && $(API_PYTHON) -m govcheck.api.openapi_check

generate-contracts:
	cd $(API_DIR) && $(API_PYTHON) -m govcheck.api.generate_web_contracts ../web/src/lib/contracts.generated.ts

check-contracts: generate-contracts
	git diff --exit-code -- $(WEB_DIR)/src/lib/contracts.generated.ts

test-web:
	pnpm --dir $(WEB_DIR) test

build-web:
	pnpm --dir $(WEB_DIR) build

eval-test:
	cd $(EVAL_DIR) && $(EVAL_PYTHON) -m pytest -v
	cd $(EVAL_DIR) && $(EVAL_PYTHON) -m ruff check govcheck_eval tests

eval-fake:
	cd $(EVAL_DIR) && $(EVAL_PYTHON) -m govcheck_eval.runner score \
		--dataset-dir datasets \
		--predictions datasets/predictions/fake-baseline.json \
		--output results/fake-baseline.json \
		--markdown-output ../../docs/evaluation.md

eval-live:
	@test -n "$(EVAL_API_BASE_URL)" || (echo "EVAL_API_BASE_URL is required" >&2; exit 2)
	@test -n "$(EVAL_DOCUMENTS_DIR)" || (echo "EVAL_DOCUMENTS_DIR is required" >&2; exit 2)
	@test -n "$(EVAL_PROVIDER)" || (echo "EVAL_PROVIDER is required" >&2; exit 2)
	cd $(EVAL_DIR) && $(EVAL_PYTHON) -m govcheck_eval.runner live \
		--dataset-dir datasets \
		--api-base-url "$(EVAL_API_BASE_URL)" \
		--documents-dir "$(EVAL_DOCUMENTS_DIR)" \
		--provider "$(EVAL_PROVIDER)" \
		--predictions-output results/live-predictions.json \
		--output results/live-result.json \
		--markdown-output ../../docs/evaluation-live.md

cleanup-expired:
	cd $(API_DIR) && $(API_PYTHON) -m govcheck.application.cleanup_expired

verify: lint-api test-api check-contracts test-web build-web eval-test

dev:
	docker compose up --build
