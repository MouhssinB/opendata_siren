# Makefile pour faciliter les commandes courantes

.PHONY: help build up down logs clean validate test run-full run-delta

help:
	@echo "Commandes disponibles:"
	@echo "  make build        - Construire l'image Docker"
	@echo "  make validate     - Valider la configuration"
	@echo "  make run-full     - Exécuter en mode FULL"
	@echo "  make run-delta    - Exécuter en mode DELTA"
	@echo "  make scheduler    - Démarrer le scheduler"
	@echo "  make logs         - Voir les logs"
	@echo "  make clean        - Nettoyer les conteneurs et volumes"
	@echo "  make setup        - Configuration initiale"

build:
	docker-compose build

validate:
	docker-compose run --rm siren-collector --validate-only

run-full:
	docker-compose run --rm siren-collector --mode full

run-delta:
	docker-compose run --rm siren-collector --mode delta

scheduler:
	docker-compose --profile scheduler up -d siren-scheduler

scheduler-logs:
	docker-compose --profile scheduler logs -f siren-scheduler

scheduler-stop:
	docker-compose --profile scheduler down

logs:
	docker-compose logs -f

clean:
	docker-compose down -v
	rm -rf data/*.json
	rm -rf logs/*.log

setup:
	@echo "Configuration initiale..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Fichier .env créé - Veuillez le remplir avec vos identifiants"; \
	else \
		echo "✓ Fichier .env existe déjà"; \
	fi
	@mkdir -p data logs
	@echo "✓ Répertoires créés"
	@echo ""
	@echo "Prochaines étapes:"
	@echo "  1. Éditez le fichier .env avec vos identifiants"
	@echo "  2. Éditez config.yaml pour configurer les départements"
	@echo "  3. Exécutez 'make validate' pour vérifier la configuration"
	@echo "  4. Exécutez 'make run-full' pour la première collecte"
