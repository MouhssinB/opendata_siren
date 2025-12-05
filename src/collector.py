"""Collecteur principal pour récupérer les données SIREN"""
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from .api import SirenAPIClient
from .storage import AzureStorageHandler
from .models import StateManager
from .config import ConfigLoader


logger = logging.getLogger(__name__)


class SirenCollector:
    """Collecteur principal pour récupérer et stocker les données SIREN"""

    def __init__(self, config: ConfigLoader):
        """
        Initialise le collecteur

        Args:
            config: Configuration de l'application
        """
        self.config = config
        self.state_manager: Optional[StateManager] = None
        self.api_client: Optional[SirenAPIClient] = None
        self.storage_handler: Optional[AzureStorageHandler] = None

        self._initialize_components()

    def _initialize_components(self):
        """Initialise les composants"""
        # Initialiser le gestionnaire d'état
        state_file = self.config.get('directories.state_file', './data/state.json')
        self.state_manager = StateManager(state_file)

        # Initialiser le client API
        api_config = self.config.get_api_config()
        self.api_client = SirenAPIClient(
            consumer_key=api_config['consumer_key'],
            consumer_secret=api_config['consumer_secret'],
            base_url=api_config.get('base_url', 'https://api.insee.fr/entreprises/sirene/V3'),
            timeout=api_config.get('timeout', 30),
            max_retries=api_config.get('max_retries', 3),
            rate_limit_delay=api_config.get('rate_limit_delay', 1.0)
        )

        # Initialiser le gestionnaire de stockage Azure
        azure_config = self.config.get_azure_config()
        self.storage_handler = AzureStorageHandler(
            storage_account_name=azure_config['storage_account_name'],
            storage_account_key=azure_config['storage_account_key'],
            container_name=azure_config['container_name'],
            connection_string=azure_config.get('connection_string')
        )

        logger.info("Composants initialisés avec succès")

    def _get_modified_since_date(self, department: str, mode: str) -> Optional[str]:
        """
        Calcule la date de début pour le mode delta

        Args:
            department: Code département
            mode: Mode d'exécution

        Returns:
            Date ISO ou None pour le mode full
        """
        if mode == 'full':
            return None

        # Mode delta
        last_execution = self.state_manager.get_last_execution_for_department(department)

        if last_execution:
            # Utiliser la date de dernière exécution
            modified_since = last_execution
            logger.info(f"Mode delta: récupération depuis {modified_since}")
        else:
            # Première exécution en mode delta, utiliser delta_days
            delta_days = self.config.get('processing.delta_days', 7)
            date = datetime.utcnow() - timedelta(days=delta_days)
            modified_since = date.strftime('%Y-%m-%dT%H:%M:%S')
            logger.info(f"Première exécution delta: récupération des {delta_days} derniers jours")

        return modified_since

    def collect_department(self, department: str, mode: str, data_type: str = "siret") -> int:
        """
        Collecte les données pour un département

        Args:
            department: Code département
            mode: Mode d'exécution (full ou delta)
            data_type: Type de données (siret ou siren)

        Returns:
            Nombre d'enregistrements récupérés
        """
        logger.info(f"Début de la collecte pour le département {department} "
                   f"(mode: {mode}, type: {data_type})")

        # Déterminer la date de début pour le mode delta
        modified_since = self._get_modified_since_date(department, mode)

        # Collecter les données
        all_records = []
        batch_size = self.config.get('processing.batch_size', 1000)

        try:
            if data_type == "siret":
                fetch_method = self.api_client.fetch_all_siret_by_department
            else:
                fetch_method = self.api_client.fetch_all_siren_by_department

            for batch in fetch_method(department, modified_since, batch_size):
                all_records.extend(batch)

                # Pour les gros volumes, on peut uploader par batch
                if len(all_records) >= 10000:
                    self._upload_batch(all_records, department, mode, data_type)
                    all_records = []

            # Upload du dernier batch
            if all_records:
                self._upload_batch(all_records, department, mode, data_type)

            total_records = len(all_records) if all_records else 0

            # Mettre à jour l'état
            self.state_manager.update_execution(mode, department, total_records)

            logger.info(f"Collecte terminée pour le département {department}: "
                       f"{total_records} enregistrements")

            return total_records

        except Exception as e:
            logger.error(f"Erreur lors de la collecte pour le département {department}: {e}")
            raise

    def _upload_batch(self, records: List, department: str, mode: str, data_type: str):
        """
        Upload un batch de données vers Azure

        Args:
            records: Enregistrements à uploader
            department: Code département
            mode: Mode d'exécution
            data_type: Type de données
        """
        if not records:
            return

        # Générer le chemin du blob
        blob_path = self.storage_handler.generate_blob_path(
            department=department,
            mode=mode,
            data_type=data_type
        )

        # Upload vers Azure
        success = self.storage_handler.upload_json(records, blob_path)

        if success:
            logger.info(f"Batch uploadé avec succès: {len(records)} enregistrements vers {blob_path}")
        else:
            logger.error(f"Échec de l'upload du batch vers {blob_path}")

    def collect_all_departments(self, mode: Optional[str] = None,
                               data_type: str = "siret",
                               parallel: bool = True) -> dict:
        """
        Collecte les données pour tous les départements configurés

        Args:
            mode: Mode d'exécution (None = utiliser la config)
            data_type: Type de données (siret ou siren)
            parallel: Si True, traite les départements en parallèle

        Returns:
            Dictionnaire avec les statistiques par département
        """
        # Déterminer le mode
        if mode is None:
            mode = self.config.get_execution_mode()

        # Vérifier si c'est la première exécution
        if self.state_manager.is_first_execution():
            logger.info("Première exécution détectée, passage en mode FULL")
            mode = 'full'

        departments = self.config.get_departments()
        logger.info(f"Démarrage de la collecte pour {len(departments)} départements "
                   f"(mode: {mode}, type: {data_type})")

        results = {}

        if parallel:
            # Traitement parallèle
            max_workers = self.config.get('processing.max_workers', 4)
            logger.info(f"Traitement parallèle avec {max_workers} workers")

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_dept = {
                    executor.submit(self.collect_department, dept, mode, data_type): dept
                    for dept in departments
                }

                for future in as_completed(future_to_dept):
                    dept = future_to_dept[future]
                    try:
                        count = future.result()
                        results[dept] = {
                            'success': True,
                            'records_count': count
                        }
                    except Exception as e:
                        logger.error(f"Erreur pour le département {dept}: {e}")
                        results[dept] = {
                            'success': False,
                            'error': str(e)
                        }
        else:
            # Traitement séquentiel
            for dept in departments:
                try:
                    count = self.collect_department(dept, mode, data_type)
                    results[dept] = {
                        'success': True,
                        'records_count': count
                    }
                except Exception as e:
                    logger.error(f"Erreur pour le département {dept}: {e}")
                    results[dept] = {
                        'success': False,
                        'error': str(e)
                    }

        # Résumé
        total_success = sum(1 for r in results.values() if r['success'])
        total_records = sum(r.get('records_count', 0) for r in results.values() if r['success'])

        logger.info(f"Collecte terminée: {total_success}/{len(departments)} départements réussis, "
                   f"{total_records} enregistrements au total")

        return results

    def get_statistics(self) -> dict:
        """
        Récupère les statistiques d'exécution

        Returns:
            Dictionnaire des statistiques
        """
        return self.state_manager.get_statistics()

    def cleanup(self):
        """Nettoie les ressources"""
        if self.api_client:
            self.api_client.close()
        if self.storage_handler:
            self.storage_handler.close()

        logger.info("Ressources nettoyées")
