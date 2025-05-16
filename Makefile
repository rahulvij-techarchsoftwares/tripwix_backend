.PHONY: help

help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help
HEAD = 1

run: ## Run docker compose up as daemon
	docker compose up web db redis

run-dev: ## Run docker compose up as daemon
	docker compose -f docker-compose.devcontainer.yml up

makemigrations:  ## Run the makemigrations inside the container
	docker compose run --rm web python3 manage.py makemigrations $(app)

migrate: ## Run the migrate inside the container
	docker compose run --rm web python3 manage.py migrate $(app) $(migration)

test: ## Run test coverage and generate html report
	docker compose run --rm -e "DJANGO_SETTINGS_MODULE=tripwix_backend.settings.testing" web coverage run manage.py test -v 2
	docker compose run --rm web coverage report
	docker compose run --rm web coverage html

lint_black: ## Run black on latest changed files, add a HEAD arg to specify the range of commited changes
	docker compose run --rm web black $$(git diff --name-only --diff-filter=ACMR HEAD~$(HEAD) HEAD~0 ':(exclude)*/migrations/*' | grep .py)

lint_black-check: ## Run black but dont affect files
	docker compose run --rm web black $$(git diff --name-only --diff-filter=ACMR HEAD~$(HEAD) HEAD~0 ':(exclude)*/migrations/*' | grep .py) --check

lint_flake8: ## Run flake8 on latest changed files, add a HEAD arg to specify the range of commited changes
	docker compose run --rm web flake8 $$(git diff --name-only --diff-filter=ACMR HEAD~$(HEAD) HEAD~0 ':(exclude)*/migrations/*' | grep .py)

lint_isort: ## Run isort on latest changed files, add a HEAD arg to specify the range of commited changes
	docker compose run --rm web isort $$(git diff --name-only --diff-filter=ACMR HEAD~$(HEAD) HEAD~0 ':(exclude)*/migrations/*' | grep .py)

init_db: makemigrations migrate

flush: ## Run the flush inside the container
	docker compose run --rm web python3 manage.py flush

createsuperuser: ## Run the createsuperuser inside the container
	docker compose run --rm web python3 manage.py createsuperuser

build: ## Build the container
	docker compose build

init: build init_db 

down: docker compose down

shell: ## Run Django shell inside the container
	docker compose run --rm web python3 manage.py shell

showmigrations: ## Run the showmigrations inside the container
	docker compose run --rm web python3 manage.py showmigrations
