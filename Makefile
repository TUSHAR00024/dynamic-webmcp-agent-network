.PHONY: all test run verify clean

all: test

verify:
	python3 scripts/verify_setup.py

test:
	python3 backend/tests/run_phase2_tests.py

run:
	python3 backend/app.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
