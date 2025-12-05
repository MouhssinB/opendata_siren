"""Point d'entrée principal de l'application"""
import argparse
import logging
import sys
from pathlib import Path

from .config import ConfigLoader
from .collector import SirenCollector


def setup_logging(config: ConfigLoader):
    """
    Configure le système de logging

    Args:
        config: Configuration de l'application
    """
    log_level = config.get('logging.level', 'INFO')
    log_format = config.get('logging.format',
                           '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Configuration du logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Configurer le logging vers fichier si spécifié
    logs_dir = config.get('directories.logs_dir', './logs')
    if logs_dir:
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)

        from logging.handlers import RotatingFileHandler

        log_file = logs_path / 'siren_collector.log'
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=config.get('logging.file_max_bytes', 10485760),
            backupCount=config.get('logging.file_backup_count', 5)
        )
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)

    logger = logging.getLogger(__name__)
    logger.info("Logging configuré")


def ensure_directories(config: ConfigLoader):
    """
    Crée les répertoires nécessaires

    Args:
        config: Configuration de l'application
    """
    directories = config.get_directories()

    for dir_key, dir_path in directories.items():
        if dir_key.endswith('_dir'):
            path = Path(dir_path)
            path.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.info("Répertoires créés")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description='Collecteur de données SIREN de l\'API INSEE'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Chemin vers le fichier de configuration (défaut: config.yaml)'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['full', 'delta'],
        help='Mode d\'exécution (override la configuration)'
    )

    parser.add_argument(
        '--departments',
        type=str,
        nargs='+',
        help='Liste des départements à traiter (override la configuration)'
    )

    parser.add_argument(
        '--data-type',
        type=str,
        choices=['siret', 'siren', 'both'],
        default='siret',
        help='Type de données à récupérer (défaut: siret)'
    )

    parser.add_argument(
        '--no-parallel',
        action='store_true',
        help='Désactiver le traitement parallèle'
    )

    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Valider la configuration et quitter'
    )

    args = parser.parse_args()

    try:
        # Charger la configuration
        config = ConfigLoader(args.config)

        # Valider la configuration
        config.validate()
        print(f"✓ Configuration validée")

        if args.validate_only:
            print("Mode validation uniquement - fin du programme")
            return 0

        # Configurer le logging
        setup_logging(config)
        logger = logging.getLogger(__name__)

        # Créer les répertoires
        ensure_directories(config)

        # Initialiser le collecteur
        logger.info("Initialisation du collecteur SIREN")
        collector = SirenCollector(config)

        # Override des départements si spécifié
        if args.departments:
            config.config['departments'] = args.departments
            logger.info(f"Départements overridés: {args.departments}")

        # Déterminer le mode
        mode = args.mode if args.mode else config.get_execution_mode()
        logger.info(f"Mode d'exécution: {mode}")

        # Collecter les données
        data_types = ['siret', 'siren'] if args.data_type == 'both' else [args.data_type]

        for dtype in data_types:
            logger.info(f"Collecte des données de type: {dtype}")

            results = collector.collect_all_departments(
                mode=mode,
                data_type=dtype,
                parallel=not args.no_parallel
            )

            # Afficher les résultats
            logger.info("=" * 60)
            logger.info(f"RÉSULTATS - Type: {dtype}")
            logger.info("=" * 60)

            success_count = 0
            total_records = 0

            for dept, result in results.items():
                if result['success']:
                    success_count += 1
                    records = result['records_count']
                    total_records += records
                    logger.info(f"  ✓ Département {dept}: {records} enregistrements")
                else:
                    logger.error(f"  ✗ Département {dept}: {result.get('error', 'Erreur inconnue')}")

            logger.info("=" * 60)
            logger.info(f"Départements traités avec succès: {success_count}/{len(results)}")
            logger.info(f"Total d'enregistrements: {total_records}")

        # Afficher les statistiques globales
        stats = collector.get_statistics()
        logger.info("=" * 60)
        logger.info("STATISTIQUES GLOBALES")
        logger.info("=" * 60)
        logger.info(f"  Total d'exécutions: {stats.get('total_executions', 0)}")
        logger.info(f"  Total d'enregistrements (historique): {stats.get('total_records_fetched', 0)}")
        logger.info("=" * 60)

        # Nettoyage
        collector.cleanup()

        logger.info("Collecte terminée avec succès")
        return 0

    except Exception as e:
        print(f"Erreur: {e}", file=sys.stderr)
        if 'logger' in locals():
            logger.exception("Erreur lors de l'exécution")
        return 1


if __name__ == '__main__':
    sys.exit(main())
