.PHONY: test install
install:
	pip install -e ".[dev]"
test:
	pytest
