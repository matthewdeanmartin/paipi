.EXPORT_ALL_VARIABLES:

# ---------------------------
# Python / uv virtualenv shim
# ---------------------------
ifeq ($(origin VIRTUAL_ENV),undefined)
    VENV := uv run
else
    VENV :=
endif

# Default project paths
PKG          ?= paipi
TESTS_DIR    ?= test
APP_DIR      ?= paipi-app   # Angular app location
NPM          ?= npm
NG           ?= npx ng

# ---------------------------
# Dependency install / lock
# ---------------------------
uv.lock: pyproject.toml
	@echo "Installing dependencies (uv sync)"
	@uv sync --all-extras

# ---------------------------
# Cleaning
# ---------------------------
.PHONY: clean clean-pyc clean-test

clean-pyc:
	@echo "Removing compiled files with pyclean"
	@$(VENV) pyclean . || true

clean-test:
	@echo "Removing coverage data"
	@rm -f .coverage .coverage.* coverage.xml || true
	@rm -rf htmlcov || true

clean: clean-pyc clean-test

# ---------------------------
# Tests (lint first, then tests)
# ---------------------------
.PHONY: test

test: uv.lock
	@echo "Running unit tests"
	# --cov-fail-under=48 \
	$(VENV) pytest $(TESTS_DIR) -vv -n 2 \
	  --cov=$(PKG) --cov-report=html --cov-report=xml \
	  --cov-branch \
	  --junitxml=junit.xml -o junit_family=legacy \
	  --timeout=5 --session-timeout=600
	$(VENV) bash ./scripts/basic_checks.sh

# ---------------------------
# Formatting / Linting / Static Analysis
# ---------------------------
.PHONY: isort black pre-commit bandit pylint mypy

isort:
	@echo "Formatting imports (isort)"
	$(VENV) isort .

black: isort
	@echo "Formatting code (black)"
	$(VENV) metametameta pep621 || true
	$(VENV) black $(PKG)
	$(VENV) black $(TESTS_DIR)
	$(VENV) git2md $(PKG) --ignore __init__.py __pycache__ --output SOURCE.md || true

pre-commit: black
	@echo "Running pre-commit hooks"
	$(VENV) pre-commit run --all-files

bandit:
	@echo "Security checks (bandit)"
	@echo "Too many false positives for a side project."
	# $(VENV) bandit $(PKG) -r --quiet

pylint: black
	@echo "Linting with ruff + pylint"
	$(VENV) ruff check --fix
	$(VENV) pylint $(PKG) --fail-under 9.8

mypy:
	@echo "Type checking (mypy)"
	$(VENV) mypy $(PKG) --ignore-missing-imports --check-untyped-defs

# Aggregate checks (format → lint → types → tests → sec → hooks)
.PHONY: check
check: black pylint mypy test bandit pre-commit
	@echo "All checks passed"

# ---------------------------
# Docs & Markdown Quality
# ---------------------------
.PHONY: check_docs make_docs check_md check_spelling check_changelog check_all_docs

check_docs:
	$(VENV) interrogate $(PKG) --verbose --fail-under 70
	$(VENV) pydoctest --config .pydoctest.json | grep -v "__init__" | grep -v "__main__" | grep -v "Unable to parse" || true

make_docs:
	$(VENV) pdoc $(PKG) --html -o docs --force

check_md:
	$(VENV) linkcheckMarkdown README.md
	$(VENV) markdownlint README.md --config .markdownlintrc
	$(VENV) mdformat README.md docs/*.md

check_spelling:
	$(VENV) pylint $(PKG) --enable C0402 --rcfile=.pylintrc_spell || true
	$(VENV) pylint docs --enable C0402 --rcfile=.pylintrc_spell || true
	$(VENV) codespell README.md --ignore-words=private_dictionary.txt
	$(VENV) codespell $(PKG) --ignore-words=private_dictionary.txt
	$(VENV) codespell docs --ignore-words=private_dictionary.txt

check_changelog:
	$(VENV) changelogmanager validate

check_all_docs: check_docs check_md check_spelling check_changelog

# ---------------------------
# Publish / Audit
# ---------------------------
.PHONY: publish audit

publish: test
	rm -rf dist && hatch build

audit:
	$(VENV) tool_audit single $(PKG) --version=">=2.0.0"

# ---------------------------
# Angular app helpers (paipi-app)
# ---------------------------
.PHONY: app-install app-start app-build app-lint app

app-install:
	@echo "Installing npm deps in $(APP_DIR)"
	$(NPM) ci --prefix $(APP_DIR)

app-start:
	@echo "Starting Angular dev server"
	$(NPM) start --prefix $(APP_DIR)
	# Alternatively: $(NG) serve --prefix $(APP_DIR)

app-build:
	@echo "Building Angular app"
	$(NPM) run build --prefix $(APP_DIR)

app-lint:
	@echo "Linting Angular app"
	$(NPM) run lint --prefix $(APP_DIR) || true

# Simple launcher alias
app: app-install app-start

# ---------------------------
# Convenience top-level goals
# ---------------------------
.PHONY: fmt lint all

fmt: isort black

lint: pylint bandit

all: clean uv.lock check check_all_docs
