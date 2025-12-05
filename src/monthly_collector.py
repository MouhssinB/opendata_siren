"""Collecteur mensuel pour télécharger et uploader les fichiers INSEE"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from .downloader import InseeFileDownloader
from .storage import AzureStorageHandler
from .config import ConfigLoader

logger = logging.getLogger(__name__)


class MonthlyInseeCollector:
    """Collecteur mensuel qui télécharge les fichiers INSEE et les upload vers Azure"""

    def __init__(self, config: ConfigLoader):
        """
        Initialise le collecteur mensuel

        Args:
            config: Configuration de l'application
        """
        self.config = config

        # Initialiser le downloader
        self.downloader = InseeFileDownloader(timeout=120)

        # Initialiser le gestionnaire de stockage Azure
        azure_config = self.config.get_azure_config()
        self.storage_handler = AzureStorageHandler(
            storage_account_name=azure_config['storage_account_name'],
            storage_account_key=azure_config['storage_account_key'],
            container_name=azure_config['container_name'],
            connection_string=azure_config.get('connection_string')
        )

        # Répertoire temporaire pour les téléchargements
        temp_dir = self.config.get('directories.temp_dir', './data/temp')
        self.download_dir = Path(temp_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

        logger.info("MonthlyInseeCollector initialisé")

    def _get_blob_prefix(self) -> str:
        """
        Retourne le préfixe pour les blobs dans Azure Storage

        Returns:
            Préfixe des blobs (ex: "insee/")
        """
        return self.config.get('azure.blob_prefix', 'insee/')

    def clear_existing_files(self) -> int:
        """
        Supprime tous les fichiers existants dans Azure (logique annule et remplace)

        Returns:
            Nombre de fichiers supprimés
        """
        prefix = self._get_blob_prefix()
        logger.info(f"ANNULE ET REMPLACE: Suppression des fichiers existants avec le préfixe '{prefix}'")

        deleted_count = self.storage_handler.delete_all_blobs(prefix=prefix)

        logger.info(f"ANNULE ET REMPLACE: {deleted_count} fichiers supprimés")
        return deleted_count

    def collect_and_upload(self) -> Dict:
        """
        Collecte mensuelle : télécharge les fichiers INSEE et les upload vers Azure

        Returns:
            Dictionnaire avec les statistiques de l'exécution
        """
        start_time = datetime.now()
        logger.info("=" * 80)
        logger.info(f"DÉBUT DE LA COLLECTE MENSUELLE - {start_time.isoformat()}")
        logger.info("=" * 80)

        stats = {
            'start_time': start_time,
            'files_deleted': 0,
            'files_downloaded': 0,
            'files_uploaded': 0,
            'errors': []
        }

        try:
            # ÉTAPE 1: Supprimer les fichiers existants (annule et remplace)
            logger.info("ÉTAPE 1/3: Suppression des fichiers existants...")
            stats['files_deleted'] = self.clear_existing_files()

            # ÉTAPE 2: Télécharger les fichiers depuis data.gouv.fr
            logger.info("ÉTAPE 2/3: Téléchargement des fichiers depuis data.gouv.fr...")

            # Récupérer la liste des fichiers disponibles
            available_files = self.downloader.get_available_files()
            logger.info(f"{len(available_files)} fichiers à télécharger")

            downloaded_files = []

            for idx, file_info in enumerate(available_files, 1):
                url = file_info['url']
                title = file_info['title']

                logger.info(f"[{idx}/{len(available_files)}] Téléchargement: {title}")

                try:
                    # Télécharger le fichier
                    local_path = self.downloader.download_file(url, None)
                    downloaded_files.append({
                        'local_path': local_path,
                        'title': title,
                        'url': url
                    })
                    stats['files_downloaded'] += 1

                except Exception as e:
                    error_msg = f"Échec du téléchargement de {title}: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)

            # ÉTAPE 3: Upload vers Azure Storage
            logger.info("ÉTAPE 3/3: Upload vers Azure Storage...")

            prefix = self._get_blob_prefix()

            for idx, file_data in enumerate(downloaded_files, 1):
                local_path = file_data['local_path']
                title = file_data['title']

                logger.info(f"[{idx}/{len(downloaded_files)}] Upload: {title}")

                try:
                    # Générer le chemin du blob
                    filename = local_path.name
                    blob_path = f"{prefix}{filename}"

                    # Upload vers Azure
                    success = self.storage_handler.upload_file(
                        str(local_path),
                        blob_path,
                        overwrite=True
                    )

                    if success:
                        stats['files_uploaded'] += 1
                    else:
                        error_msg = f"Échec de l'upload de {title}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)

                except Exception as e:
                    error_msg = f"Erreur lors de l'upload de {title}: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)

            # Nettoyer les fichiers temporaires
            self._cleanup_temp_files(downloaded_files)

        except Exception as e:
            error_msg = f"Erreur lors de la collecte mensuelle: {e}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)

        # Statistiques finales
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        stats['end_time'] = end_time
        stats['duration_seconds'] = duration

        logger.info("=" * 80)
        logger.info("RÉSULTATS DE LA COLLECTE MENSUELLE")
        logger.info("=" * 80)
        logger.info(f"Fichiers supprimés: {stats['files_deleted']}")
        logger.info(f"Fichiers téléchargés: {stats['files_downloaded']}")
        logger.info(f"Fichiers uploadés: {stats['files_uploaded']}")
        logger.info(f"Erreurs: {len(stats['errors'])}")
        logger.info(f"Durée: {duration:.1f} secondes ({duration/60:.1f} minutes)")
        logger.info("=" * 80)

        if stats['errors']:
            logger.warning("Erreurs rencontrées:")
            for error in stats['errors']:
                logger.warning(f"  - {error}")

        logger.info(f"FIN DE LA COLLECTE MENSUELLE - {end_time.isoformat()}")

        return stats

    def _cleanup_temp_files(self, downloaded_files: List[Dict]):
        """
        Nettoie les fichiers temporaires téléchargés

        Args:
            downloaded_files: Liste des fichiers téléchargés
        """
        logger.info("Nettoyage des fichiers temporaires...")

        for file_data in downloaded_files:
            try:
                local_path = file_data['local_path']
                if local_path.exists():
                    local_path.unlink()
                    logger.debug(f"Fichier temporaire supprimé: {local_path}")
            except Exception as e:
                logger.warning(f"Impossible de supprimer {local_path}: {e}")

        logger.info("Nettoyage terminé")

    def cleanup(self):
        """Nettoie les ressources"""
        if self.downloader:
            self.downloader.close()
        if self.storage_handler:
            self.storage_handler.close()

        logger.info("Ressources nettoyées")
