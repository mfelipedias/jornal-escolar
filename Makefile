# Jornal Escolar — atalhos de desenvolvimento.
# Os comandos são simples de propósito: funcionam no terminal do Windows e no Linux.
# Novos alvos entram conforme as etapas do docs/26 (dev, test, build, deploy, release, backup).

UV = uv run --directory backend

.DEFAULT_GOAL := help
.PHONY: help install hooks lint format

help:
	@echo Jornal Escolar - comandos disponiveis:
	@echo   make install   instala Python 3.13 e as dependencias do backend
	@echo   make hooks     ativa o pre-commit no git
	@echo   make lint      verifica codigo Python e templates sem alterar nada
	@echo   make format    formata codigo Python e templates

install:
	uv sync --directory backend

hooks: install
	$(UV) pre-commit install

lint:
	$(UV) ruff check .
	$(UV) ruff format --check .
	$(UV) djlint templates --lint

format:
	$(UV) ruff check --fix .
	$(UV) ruff format .
	$(UV) djlint templates --reformat
