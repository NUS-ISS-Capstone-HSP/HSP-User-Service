PYTHON ?= python

.PHONY: install lint test-unit test coverage sast proto-gen swagger run run-local docker-build

install:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	ruff check .
	mypy hsp_user_service

test-unit:
	pytest tests/unit -q

test:
	pytest -q

coverage:
	pytest --cov=hsp_user_service --cov-report=term-missing --cov-fail-under=70 -q

sast:
	semgrep scan --config=p/python --config=p/owasp-top-ten --config=p/secrets --metrics=off --error hsp_user_service scripts

proto-gen:
	$(PYTHON) -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. \
		rpc/echo/v1/echo.proto \
		rpc/user/v1/user.proto

swagger:
	$(PYTHON) -m scripts.generate_openapi

run:
	$(PYTHON) -m hsp_user_service.main

run-local:
	@set -a; \
	if [ -f .env ]; then . ./.env; fi; \
	if [ -f .env.local ]; then . ./.env.local; fi; \
	set +a; \
	$(PYTHON) -m hsp_user_service.main

docker-build:
	docker build -t hsp-execution-record-service:local .
