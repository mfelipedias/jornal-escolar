# Jornal Escolar — atalhos de desenvolvimento.
# Os comandos são simples de propósito: funcionam no terminal do Windows e no Linux.
# Os alvos "prod-*", deploy, backup e restore rodam NO SERVIDOR de produção (docs/34).

UV = uv run --directory backend
MANAGE = $(UV) python manage.py
COMPOSE = docker compose
PROD = docker compose -f infra/docker-compose.yml --env-file infra/env/.env

.DEFAULT_GOAL := help
.PHONY: help install assets-install assets-dev assets hooks lint format test secret-key dev dev-native db down db-reset logs migrate makemigrations shell superuser release screenshots
.PHONY: build deploy prod-check prod-logs prod-down prod-superuser backup backups restore

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
	@echo   make dev              sobe TUDO no Docker: banco, Django e Vite (http://localhost:8000)
	@echo   make dev-native       sobe o banco no Docker e o Django no Windows (use com make assets-dev)
	@echo   make db               sobe so o banco no Docker, em segundo plano
	@echo   make down             para os containers de desenvolvimento
	@echo   make db-reset         APAGA o banco de desenvolvimento e cria de novo vazio
	@echo   make logs             mostra os logs dos containers
	@echo   make migrate          aplica migracoes
	@echo   make makemigrations   cria migracoes a partir dos modelos
	@echo   make shell            abre o shell do Django
	@echo   make superuser        cria um usuario administrador
	@echo   make release VERSION=x.y.z   cria a versao: VERSION, CHANGELOG, commit e tag (docs/30)
	@echo   make screenshots      refaz as imagens do README (precisa de make assets e seed_demo)
	@echo Producao (docs/34, rodar no servidor):
	@echo   make build            confere que as imagens compilam para x86 e ARM
	@echo   make deploy           baixa o codigo novo do GitHub e sobe/atualiza o site
	@echo   make prod-check       verificacoes de seguranca e do SITE_URL
	@echo   make prod-logs        mostra os logs do site em producao
	@echo   make prod-down        desliga o site (os dados ficam guardados)
	@echo   make prod-superuser   cria o primeiro administrador em producao
	@echo   make backup           faz um backup agora (banco e fotos, docs/31)
	@echo   make backups          lista os backups disponiveis
	@echo   make restore FILE=mais-recente   restaura um backup (APAGA o banco atual)

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

release:
	$(UV) python ../scripts/release.py $(VERSION)

# --- Produção (docs/24 e docs/34) ---

# Só confere a compilação nas duas arquiteturas; o servidor constrói a própria imagem no deploy.
build:
	docker buildx build --platform linux/amd64,linux/arm64 -f infra/Dockerfile .
	docker buildx build --platform linux/amd64,linux/arm64 infra/backup

deploy:
	git pull --ff-only
	$(PROD) up -d --build --wait --remove-orphans

prod-check:
	$(PROD) exec web python manage.py check --deploy

prod-logs:
	$(PROD) logs -f --tail 200

prod-down:
	$(PROD) down

prod-superuser:
	$(PROD) exec web python manage.py createsuperuser

backup:
	$(PROD) exec backup python backup.py

backups:
	$(PROD) exec backup python restore.py

restore:
	$(PROD) exec backup python restore.py $(FILE)
	$(PROD) restart web

screenshots:
	$(MANAGE) screenshots
