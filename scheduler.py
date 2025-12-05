"""Scheduler pour exécuter l'application de manière périodique"""
import os
import sys
import time
import logging
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, '/app')

from src.config import ConfigLoader
from src.monthly_collector import MonthlyInseeCollector
from src.main import setup_logging, ensure_directories


logger = logging.getLogger(__name__)

# Variable globale pour tracker si on a déjà exécuté ce mois-ci
last_execution_month = None


def run_monthly_collection():
    """Exécute la collecte mensuelle des données"""
    global last_execution_month

    try:
        logger.info("=" * 80)
        logger.info(f"DÉBUT DE LA COLLECTE MENSUELLE PROGRAMMÉE - {datetime.now().isoformat()}")
        logger.info("=" * 80)

        # Charger la configuration
        config_path = os.getenv('CONFIG_PATH', 'config.yaml')
        config = ConfigLoader(config_path)

        # Valider la configuration
        config.validate()

        # Initialiser le collecteur mensuel
        collector = MonthlyInseeCollector(config)

        # Exécuter la collecte et l'upload
        stats = collector.collect_and_upload()

        # Nettoyage
        collector.cleanup()

        # Mettre à jour le dernier mois d'exécution
        now = datetime.now()
        last_execution_month = (now.year, now.month)

        logger.info("=" * 80)
        logger.info(f"FIN DE LA COLLECTE MENSUELLE - {datetime.now().isoformat()}")
        logger.info("=" * 80)

        return stats

    except Exception as e:
        logger.error(f"Erreur lors de la collecte programmée: {e}")
        logger.exception("Détails de l'erreur:")


def should_run_monthly_collection(day_of_month: int = 2, hour: int = 2) -> bool:
    """
    Vérifie si la collecte mensuelle doit être exécutée

    Args:
        day_of_month: Jour du mois pour l'exécution (par défaut: 2)
        hour: Heure de la journée pour l'exécution (par défaut: 2h)

    Returns:
        True si la collecte doit être exécutée
    """
    global last_execution_month

    now = datetime.now()
    current_month_key = (now.year, now.month)

    # Vérifier si on a déjà exécuté ce mois-ci
    if last_execution_month == current_month_key:
        return False

    # Vérifier si c'est le bon jour et la bonne heure
    if now.day == day_of_month and now.hour == hour:
        return True

    return False


def check_and_run_monthly():
    """Vérifie et exécute la collecte mensuelle si nécessaire"""
    day_of_month = int(os.getenv('MONTHLY_DAY', '2'))
    hour = int(os.getenv('MONTHLY_HOUR', '2'))

    if should_run_monthly_collection(day_of_month, hour):
        logger.info(f"Déclenchement de la collecte mensuelle (jour {day_of_month} du mois à {hour}h)")
        run_monthly_collection()
    else:
        now = datetime.now()
        logger.debug(f"Vérification: aujourd'hui={now.day}, heure={now.hour}, "
                    f"cible=jour {day_of_month} à {hour}h")


def main():
    """Point d'entrée du scheduler"""
    global last_execution_month

    # Charger la configuration pour le logging
    config_path = os.getenv('CONFIG_PATH', 'config.yaml')
    config = ConfigLoader(config_path)

    # Setup logging
    setup_logging(config)
    ensure_directories(config)

    logger.info("=" * 80)
    logger.info("DÉMARRAGE DU SCHEDULER MENSUEL INSEE")
    logger.info("=" * 80)

    # Récupérer la configuration de planification
    day_of_month = int(os.getenv('MONTHLY_DAY', config.get('execution.monthly_day', 2)))
    hour = int(os.getenv('MONTHLY_HOUR', config.get('execution.monthly_hour', 2)))

    logger.info(f"Planning configuré: le {day_of_month} de chaque mois à {hour}h00")

    # Optionnel: exécuter immédiatement au démarrage
    run_on_startup = os.getenv('RUN_ON_STARTUP', 'false').lower() == 'true'
    if run_on_startup:
        logger.info("Exécution immédiate au démarrage...")
        run_monthly_collection()

    logger.info("Scheduler démarré. Vérification toutes les heures...")

    # Boucle principale - vérifier toutes les heures
    try:
        while True:
            check_and_run_monthly()
            # Attendre 1 heure avant la prochaine vérification
            time.sleep(3600)

    except KeyboardInterrupt:
        logger.info("Arrêt du scheduler demandé")
        sys.exit(0)


if __name__ == '__main__':
    main()
