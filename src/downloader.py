"""Module pour télécharger les fichiers INSEE depuis data.gouv.fr"""
import logging
import requests
import tempfile
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class InseeFileDownloader:
    """Télécharge les fichiers INSEE depuis data.gouv.fr"""

    DATASET_SLUG = "base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret"
    API_BASE_URL = "https://www.data.gouv.fr/api/1/datasets"

    def __init__(self, timeout: int = 60):
        """
        Initialise le téléchargeur

        Args:
            timeout: Timeout pour les requêtes HTTP en secondes
        """
        self.timeout = timeout
        self.session = requests.Session()

        logger.info("InseeFileDownloader initialisé")

    def get_available_files(self) -> List[Dict[str, str]]:
        """
        Récupère la liste des fichiers disponibles depuis data.gouv.fr

        Returns:
            Liste de dictionnaires avec 'url' et 'title' pour chaque fichier
        """
        logger.info("Récupération de la liste des fichiers disponibles...")

        try:
            api_url = f"{self.API_BASE_URL}/{self.DATASET_SLUG}/"
            response = self.session.get(api_url, timeout=self.timeout)
            response.raise_for_status()

            dataset = response.json()

            files = []
            for resource in dataset.get("resources", []):
                url = resource.get("url")
                title = resource.get("title", "")
                file_id = resource.get("id", "")

                if url:
                    files.append({
                        "url": url,
                        "title": title or f"resource_{file_id}",
                        "id": file_id
                    })

            # Trier par URL pour avoir un ordre cohérent
            files.sort(key=lambda x: x["url"])

            logger.info(f"{len(files)} fichiers disponibles")
            return files

        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération de la liste des fichiers: {e}")
            raise

    def download_file(self, url: str, local_path: Optional[Path] = None) -> Path:
        """
        Télécharge un fichier

        Args:
            url: URL du fichier à télécharger
            local_path: Chemin local où sauvegarder le fichier (optionnel)

        Returns:
            Path vers le fichier téléchargé
        """
        # Extraire le nom du fichier depuis l'URL
        parsed_url = urlparse(url)
        filename = Path(parsed_url.path).name

        if not filename:
            filename = "downloaded_file"

        # Si pas de chemin spécifié, utiliser un répertoire temporaire
        if local_path is None:
            temp_dir = Path(tempfile.gettempdir()) / "insee_downloads"
            temp_dir.mkdir(parents=True, exist_ok=True)
            local_path = temp_dir / filename

        logger.info(f"Téléchargement de {url} vers {local_path}...")

        try:
            # Télécharger avec streaming pour gérer les gros fichiers
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()

            # Récupérer la taille totale si disponible
            total_size = int(response.headers.get('content-length', 0))

            # Écrire le fichier par chunks
            chunk_size = 8192
            downloaded = 0

            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Log de progression tous les 100 MB
                        if total_size > 0 and downloaded % (100 * 1024 * 1024) < chunk_size:
                            progress = (downloaded / total_size) * 100
                            logger.info(f"Progression: {progress:.1f}% ({downloaded / (1024*1024):.1f} MB)")

            file_size_mb = local_path.stat().st_size / (1024 * 1024)
            logger.info(f"Téléchargement terminé: {local_path} ({file_size_mb:.2f} MB)")

            return local_path

        except requests.RequestException as e:
            logger.error(f"Erreur lors du téléchargement de {url}: {e}")
            raise

    def download_all_files(self, download_dir: Optional[Path] = None) -> List[Path]:
        """
        Télécharge tous les fichiers disponibles

        Args:
            download_dir: Répertoire où télécharger les fichiers

        Returns:
            Liste des chemins des fichiers téléchargés
        """
        files_info = self.get_available_files()

        if not files_info:
            logger.warning("Aucun fichier à télécharger")
            return []

        logger.info(f"Début du téléchargement de {len(files_info)} fichiers...")

        downloaded_files = []
        errors = []

        for idx, file_info in enumerate(files_info, 1):
            url = file_info["url"]
            title = file_info["title"]

            logger.info(f"[{idx}/{len(files_info)}] Téléchargement: {title}")

            try:
                # Déterminer le chemin local
                if download_dir:
                    filename = Path(urlparse(url).path).name
                    local_path = download_dir / filename
                else:
                    local_path = None

                downloaded_path = self.download_file(url, local_path)
                downloaded_files.append(downloaded_path)

            except Exception as e:
                error_msg = f"Échec du téléchargement de {title} ({url}): {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        logger.info(f"Téléchargement terminé: {len(downloaded_files)} succès, {len(errors)} échecs")

        if errors:
            logger.warning(f"Erreurs rencontrées:\n" + "\n".join(errors))

        return downloaded_files

    def close(self):
        """Ferme la session"""
        if self.session:
            self.session.close()
        logger.info("Session fermée")
