.PHONY: all setup test agent web e2e verify clean

VENV ?= .venv
PYTHON = $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)

all: test

setup:
	test -d $(VENV) || python3 -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) backend/tests/run_tests.py

agent:
	$(PYTHON) -m backend.uagent_app

web:
	$(PYTHON) backend/app.py

e2e:
	$(PYTHON) scripts/e2e_chat_simulation.py

verify:
	$(PYTHON) scripts/verify_setup.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
