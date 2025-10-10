SHELL := /bin/bash

.PHONY: lint typecheck test ci

lint:
	./scripts/ci/lint.sh

typecheck:
	./scripts/ci/typecheck.sh

test:
	./scripts/ci/test.sh

ci: lint typecheck test
