PYTHON := python
MANAGE := $(PYTHON) manage.py

.PHONY: run shell migrate makemigrations mm test superuser

run:
	$(MANAGE) runserver

shell:
	$(MANAGE) shell

makemigrations:
	$(MANAGE) makemigrations

migrate:
	$(MANAGE) migrate

mm: makemigrations migrate

test:
	$(MANAGE) test

superuser:
	$(MANAGE) createsuperuser