"""Collecteur mensuel pour télécharger et uploader les fichiers IGN"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

from .ign_downloader import IgnFileDownloader
from .storage import AzureStorageHandler
from .config import ConfigLoader

logger = logging.getLogger(__name__)


class MonthlyIgnCollector:
    """Collecteur mensuel qui télécharge les fichiers IGN et les upload vers Azure"""

    def __init__(self, config: ConfigLoader):
        """
        Initialise le collecteur mensuel IGN

        Args:
            config: Configuration de l'application
        """
        self.config = config

        # Initialiser le downloader
        self.downloader = IgnFileDownloader(timeout=120)

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
        self.download_dir = Path(temp_dir) / "ign"
        self.download_dir.mkdir(parents=True, exist_ok=True)

        logger.info("MonthlyIgnCollector initialisé")

    def _get_blob_prefix(self) -> str:
        """
        Retourne le préfixe pour les blobs dans Azure Storage

        Returns:
            Préfixe des blobs (ex: "IGN/")
        """
        return self.config.get('ign.blob_prefix', 'IGN/')

    def clear_existing_files(self) -> int:
        """
        Supprime tous les fichiers existants dans Azure (logique annule et remplace)

        Returns:
            Nombre de fichiers supprimés
        """
        prefix = self._get_blob_prefix()
        logger.info(f"ANNULE ET REMPLACE IGN: Suppression des fichiers existants avec le préfixe '{prefix}'")

        deleted_count = self.storage_handler.delete_all_blobs(prefix=prefix)

        logger.info(f"ANNULE ET REMPLACE IGN: {deleted_count} fichiers supprimés")
        return deleted_count

    def collect_and_upload(self) -> Dict:
        """
        Collecte mensuelle : télécharge les fichiers IGN et les upload vers Azure

        Returns:
            Dictionnaire avec les statistiques de l'exécution
        """
        start_time = datetime.now()
        logger.info("=" * 80)
        logger.info(f"DÉBUT DE LA COLLECTE MENSUELLE IGN - {start_time.isoformat()}")
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

            # ÉTAPE 2: Télécharger les fichiers depuis data.geopf.fr
            logger.info("ÉTAPE 2/3: Téléchargement des fichiers depuis data.geopf.fr...")

            # Récupérer la liste des fichiers disponibles
            available_files = self.downloader.get_available_files()
            logger.info(f"{len(available_files)} fichiers à télécharger")

            downloaded_files = []

            for idx, file_info in enumerate(available_files, 1):
                url = file_info['url']
                title = file_info['title']
                resource = file_info.get('resource', '')

                logger.info(f"[{idx}/{len(available_files)}] Téléchargement: {resource} - {title}")

                try:
                    # Déterminer le nom du fichier
                    filename = Path(url.split('/')[-1]).name
                    if not filename:
                        filename = f"ign_file_{idx}"

                    local_path = self.download_dir / filename

                    # Télécharger le fichier
                    downloaded_path = self.downloader.download_file(url, local_path)
                    downloaded_files.append({
                        'local_path': downloaded_path,
                        'title': title,
                        'resource': resource,
                        'url': url
                    })
                    stats['files_downloaded'] += 1

                except Exception as e:
                    error_msg = f"Échec du téléchargement de {resource} - {title}: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)

            # ÉTAPE 3: Upload vers Azure Storage
            logger.info("ÉTAPE 3/3: Upload vers Azure Storage...")

            prefix = self._get_blob_prefix()

            for idx, file_data in enumerate(downloaded_files, 1):
                local_path = file_data['local_path']
                title = file_data['title']
                resource = file_data.get('resource', '')

                logger.info(f"[{idx}/{len(downloaded_files)}] Upload: {resource} - {title}")

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
                        error_msg = f"Échec de l'upload de {resource} - {title}"
                        logger.error(error_msg)
                        stats['errors'].append(error_msg)

                except Exception as e:
                    error_msg = f"Erreur lors de l'upload de {resource} - {title}: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)

            # Nettoyer les fichiers temporaires
            self._cleanup_temp_files(downloaded_files)

        except Exception as e:
            error_msg = f"Erreur lors de la collecte mensuelle IGN: {e}"
            logger.error(error_msg)
            stats['errors'].append(error_msg)

        # Statistiques finales
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        stats['end_time'] = end_time
        stats['duration_seconds'] = duration

        logger.info("=" * 80)
        logger.info("RÉSULTATS DE LA COLLECTE MENSUELLE IGN")
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

        logger.info(f"FIN DE LA COLLECTE MENSUELLE IGN - {end_time.isoformat()}")

        return stats

    def _cleanup_temp_files(self, downloaded_files: List[Dict]):
        """
        Nettoie les fichiers temporaires téléchargés

        Args:
            downloaded_files: Liste des fichiers téléchargés
        """
        logger.info("Nettoyage des fichiers temporaires IGN...")

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

        logger.info("Ressources IGN nettoyées")
