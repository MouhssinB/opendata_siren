"""Scheduler pour exécuter l'application de manière périodique"""
import os
import sys
import time
import logging
import schedule
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, '/app')

from src.config import ConfigLoader
from src.collector import SirenCollector
from src.main import setup_logging, ensure_directories


logger = logging.getLogger(__name__)


def run_collection():
    """Exécute la collecte des données"""
    try:
        logger.info("=" * 80)
        logger.info(f"DÉBUT DE LA COLLECTE PROGRAMMÉE - {datetime.now().isoformat()}")
        logger.info("=" * 80)

        # Charger la configuration
        config_path = os.getenv('CONFIG_PATH', 'config.yaml')
        config = ConfigLoader(config_path)

        # Valider la configuration
        config.validate()

        # Initialiser le collecteur
        collector = SirenCollector(config)

        # Déterminer le mode (delta pour les exécutions planifiées)
        mode = os.getenv('EXECUTION_MODE', 'delta')

        # Vérifier si c'est la première exécution
        if collector.state_manager.is_first_execution():
            logger.info("Première exécution détectée - passage en mode FULL")
            mode = 'full'

        logger.info(f"Mode d'exécution: {mode}")

        # Collecter les données SIRET
        logger.info("Collecte des données SIRET")
        results_siret = collector.collect_all_departments(
            mode=mode,
            data_type='siret',
            parallel=True
        )

        # Afficher les résultats
        success_count = sum(1 for r in results_siret.values() if r['success'])
        total_records = sum(r.get('records_count', 0) for r in results_siret.values() if r['success'])

        logger.info("=" * 80)
        logger.info("RÉSULTATS DE LA COLLECTE")
        logger.info("=" * 80)
        logger.info(f"Départements traités avec succès: {success_count}/{len(results_siret)}")
        logger.info(f"Total d'enregistrements SIRET: {total_records}")

        # Statistiques
        stats = collector.get_statistics()
        logger.info(f"Total d'exécutions (historique): {stats.get('total_executions', 0)}")
        logger.info(f"Total d'enregistrements (historique): {stats.get('total_records_fetched', 0)}")

        # Nettoyage
        collector.cleanup()

        logger.info("=" * 80)
        logger.info(f"FIN DE LA COLLECTE - {datetime.now().isoformat()}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Erreur lors de la collecte programmée: {e}")
        logger.exception("Détails de l'erreur:")


def main():
    """Point d'entrée du scheduler"""
    # Charger la configuration pour le logging
    config_path = os.getenv('CONFIG_PATH', 'config.yaml')
    config = ConfigLoader(config_path)

    # Setup logging
    setup_logging(config)
    ensure_directories(config)

    logger.info("=" * 80)
    logger.info("DÉMARRAGE DU SCHEDULER SIREN")
    logger.info("=" * 80)

    # Récupérer le planning depuis la config ou l'environnement
    cron_schedule = os.getenv('CRON_SCHEDULE')
    if not cron_schedule:
        cron_schedule = config.get('execution.schedule_cron', '0 2 * * 1')

    logger.info(f"Planning configuré: {cron_schedule}")

    # Parser le cron schedule (format: minute heure jour_du_mois mois jour_de_la_semaine)
    # Pour simplifier, on va supporter quelques formats courants
    parts = cron_schedule.split()

    if len(parts) >= 5:
        minute, hour, day_of_month, month, day_of_week = parts[:5]

        # Convertir le jour de la semaine (0=Dimanche en cron, 0=Lundi en schedule)
        weekdays = {
            '0': 'sunday', '1': 'monday', '2': 'tuesday', '3': 'wednesday',
            '4': 'thursday', '5': 'friday', '6': 'saturday', '7': 'sunday'
        }

        # Planifier l'exécution
        time_str = f"{hour.zfill(2)}:{minute.zfill(2)}"

        if day_of_week != '*':
            # Exécution hebdomadaire
            weekday = weekdays.get(day_of_week, 'monday')
            schedule.every().week.at(time_str).do(run_collection)
            logger.info(f"Planifié: chaque {weekday} à {time_str}")
        elif day_of_month != '*':
            # Exécution mensuelle (non supporté directement par schedule)
            logger.warning("Planification mensuelle non supportée, utilisation hebdomadaire")
            schedule.every().monday.at(time_str).do(run_collection)
        else:
            # Exécution quotidienne
            schedule.every().day.at(time_str).do(run_collection)
            logger.info(f"Planifié: chaque jour à {time_str}")

    else:
        # Par défaut: tous les lundis à 2h
        schedule.every().monday.at("02:00").do(run_collection)
        logger.info("Planifié (par défaut): chaque lundi à 02:00")

    # Optionnel: exécuter immédiatement au démarrage
    run_on_startup = os.getenv('RUN_ON_STARTUP', 'false').lower() == 'true'
    if run_on_startup:
        logger.info("Exécution immédiate au démarrage...")
        run_collection()

    logger.info("Scheduler démarré. En attente de la prochaine exécution...")

    # Boucle principale
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Vérifier chaque minute

    except KeyboardInterrupt:
        logger.info("Arrêt du scheduler demandé")
        sys.exit(0)


if __name__ == '__main__':
    main()
