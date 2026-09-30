.PHONY: doctor test lint validate

doctor:
	./bin/labctl doctor

test:
	python -m pytest

lint:
	python -m ruff check .

validate:
	./bin/labctl validate
