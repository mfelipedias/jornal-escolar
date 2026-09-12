# Jornal Escolar — atalhos de desenvolvimento.
# Os comandos são simples de propósito: funcionam no terminal do Windows e no Linux.
# Novos alvos entram conforme as etapas do docs/26 (build, deploy, release, backup).

UV = uv run --directory backend
MANAGE = $(UV) python manage.py
COMPOSE = docker compose -f infra/docker-compose.dev.yml --env-file infra/env/.env

.DEFAULT_GOAL := help
.PHONY: help install assets-install assets-dev assets hooks lint format test secret-key dev dev-native db down db-reset logs migrate makemigrations shell superuser

help:
	@echo Jornal Escolar - comandos disponiveis:
	@echo   make install          instala Python 3.13 e as dependencias do backend
	@echo   make hooks            ativa o pre-commit no git
	@echo   make lint             verifica codigo Python e templates sem alterar nada
	@echo   make format           formata codigo Python e templates
	@echo   make test             roda os testes (precisa do banco: make db)
	@echo   make secret-key       gera um SECRET_KEY para o .env
	@echo   make assets-install   instala os pacotes do frontend (npm)
	@echo   make assets-dev       servidor do Vite com recarga automatica (deixe aberto em outro terminal)
	@echo   make assets           gera CSS e JS finais em backend/static/dist
	@echo   make dev              sobe banco e Django no Docker (http://localhost:8000)
	@echo   make dev-native       sobe o banco no Docker e o Django no Windows
	@echo   make db               sobe so o banco no Docker, em segundo plano
	@echo   make down             para os containers de desenvolvimento
	@echo   make db-reset         APAGA o banco de desenvolvimento e cria de novo vazio
	@echo   make logs             mostra os logs dos containers
	@echo   make migrate          aplica migracoes
	@echo   make makemigrations   cria migracoes a partir dos modelos
	@echo   make shell            abre o shell do Django
	@echo   make superuser        cria um usuario administrador

install: assets-install
	uv sync --directory backend

assets-install:
	npm install --prefix frontend

assets-dev:
	npm run dev --prefix frontend

assets:
	npm run build --prefix frontend

hooks: install
	$(UV) pre-commit install

lint:
	$(UV) ruff check .
	$(UV) ruff format --check .
	$(UV) djlint templates --lint

# djlint --reformat sai com erro quando altera arquivos; o "-" evita que isso pare o make.
format:
	$(UV) ruff format .
	$(UV) ruff check --fix .
	-$(UV) djlint templates --reformat

test:
	$(UV) pytest

secret-key:
	@$(UV) python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

dev:
	$(COMPOSE) up

dev-native: db migrate
	$(MANAGE) runserver

db:
	$(COMPOSE) up -d --wait db

down:
	$(COMPOSE) down

db-reset:
	$(COMPOSE) down
	-docker volume rm jornal_escolar_dev_pgdata_dev
	$(COMPOSE) up -d --wait db
	$(MANAGE) migrate

logs:
	$(COMPOSE) logs -f

migrate:
	$(MANAGE) migrate

makemigrations:
	$(MANAGE) makemigrations

shell:
	$(MANAGE) shell

superuser:
	$(MANAGE) createsuperuser
