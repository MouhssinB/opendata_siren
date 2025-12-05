"""Module pour télécharger les fichiers IGN depuis data.geopf.fr"""
import logging
import requests
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


class IgnFileDownloader:
    """Télécharge les fichiers IGN depuis data.geopf.fr"""

    CAPABILITIES_URL = "https://data.geopf.fr/telechargement/capabilities"

    # Namespaces XML pour le feed ATOM
    NAMESPACES = {
        'atom': 'http://www.w3.org/2005/Atom',
        'gpf_dl': 'https://data.geopf.fr/annexes/ressources/xsd/gpf_dl.xsd',
        'georss': 'http://www.georss.org/georss'
    }

    def __init__(self, timeout: int = 60):
        """
        Initialise le téléchargeur

        Args:
            timeout: Timeout pour les requêtes HTTP en secondes
        """
        self.timeout = timeout
        self.session = requests.Session()

        logger.info("IgnFileDownloader initialisé")

    def get_all_resources(self) -> List[Dict[str, str]]:
        """
        Récupère la liste de toutes les ressources disponibles depuis le feed ATOM
        Gère la pagination pour obtenir toutes les entrées

        Returns:
            Liste de dictionnaires avec les informations sur chaque ressource
        """
        logger.info("Récupération de la liste des ressources IGN...")

        all_resources = []
        page = 1

        try:
            # Récupérer la première page pour connaître le nombre total de pages
            first_page_url = f"{self.CAPABILITIES_URL}?page={page}"
            response = self.session.get(first_page_url, timeout=self.timeout)
            response.raise_for_status()

            # Parser le XML
            root = ET.fromstring(response.content)

            # Extraire les métadonnées de pagination
            pagecount = int(root.get('{https://data.geopf.fr/annexes/ressources/xsd/gpf_dl.xsd}pagecount', '1'))
            totalentries = int(root.get('{https://data.geopf.fr/annexes/ressources/xsd/gpf_dl.xsd}totalentries', '0'))

            logger.info(f"Total de {totalentries} ressources sur {pagecount} pages")

            # Récupérer toutes les pages
            for page in range(1, pagecount + 1):
                logger.info(f"Récupération de la page {page}/{pagecount}...")

                page_url = f"{self.CAPABILITIES_URL}?page={page}"
                response = self.session.get(page_url, timeout=self.timeout)
                response.raise_for_status()

                # Parser le XML
                root = ET.fromstring(response.content)

                # Extraire les entrées
                entries = root.findall('atom:entry', self.NAMESPACES)

                for entry in entries:
                    title = entry.find('atom:title', self.NAMESPACES)
                    link = entry.find("atom:link[@rel='alternate']", self.NAMESPACES)
                    entry_id = entry.find('atom:id', self.NAMESPACES)
                    updated = entry.find('atom:updated', self.NAMESPACES)
                    content = entry.find('atom:content', self.NAMESPACES)

                    if title is not None and link is not None:
                        resource_info = {
                            'title': title.text,
                            'url': link.get('href'),
                            'id': entry_id.text if entry_id is not None else '',
                            'updated': updated.text if updated is not None else '',
                            'description': content.text if content is not None else ''
                        }

                        all_resources.append(resource_info)
                        logger.debug(f"Ressource trouvée: {resource_info['title']}")

            logger.info(f"{len(all_resources)} ressources trouvées")
            return all_resources

        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération des ressources: {e}")
            raise
        except ET.ParseError as e:
            logger.error(f"Erreur lors du parsing XML: {e}")
            raise

    def get_resource_files(self, resource_url: str) -> List[Dict[str, str]]:
        """
        Récupère la liste des fichiers disponibles pour une ressource donnée

        Args:
            resource_url: URL de la ressource (ex: https://data.geopf.fr/telechargement/resource/ADMIN-EXPRESS)

        Returns:
            Liste de dictionnaires avec les informations sur chaque fichier téléchargeable
        """
        logger.info(f"Récupération des fichiers pour {resource_url}...")

        try:
            response = self.session.get(resource_url, timeout=self.timeout)
            response.raise_for_status()

            # Parser le XML
            root = ET.fromstring(response.content)

            files = []

            # Parcourir toutes les entrées (chaque entrée représente un fichier téléchargeable)
            entries = root.findall('atom:entry', self.NAMESPACES)

            for entry in entries:
                title = entry.find('atom:title', self.NAMESPACES)

                # Chercher le lien de téléchargement direct
                download_link = entry.find("atom:link[@rel='alternate'][@type='application/x-7z-compressed']", self.NAMESPACES)
                if download_link is None:
                    download_link = entry.find("atom:link[@rel='alternate'][@type='application/zip']", self.NAMESPACES)
                if download_link is None:
                    download_link = entry.find("atom:link[@rel='alternate'][@type='application/x-gzip']", self.NAMESPACES)
                if download_link is None:
                    # Chercher n'importe quel lien de téléchargement
                    download_link = entry.find("atom:link[@rel='alternate']", self.NAMESPACES)

                if title is not None and download_link is not None:
                    download_url = download_link.get('href')

                    # Extraire les métadonnées supplémentaires
                    zone = entry.find('gpf_dl:zone', self.NAMESPACES)
                    format_elem = entry.find('gpf_dl:format', self.NAMESPACES)

                    file_info = {
                        'title': title.text,
                        'url': download_url,
                        'zone': zone.get('label') if zone is not None else '',
                        'format': format_elem.get('label') if format_elem is not None else ''
                    }

                    files.append(file_info)
                    logger.debug(f"Fichier trouvé: {file_info['title']}")

            logger.info(f"{len(files)} fichiers trouvés pour cette ressource")
            return files

        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération des fichiers de {resource_url}: {e}")
            raise
        except ET.ParseError as e:
            logger.error(f"Erreur lors du parsing XML pour {resource_url}: {e}")
            raise

    def get_available_files(self) -> List[Dict[str, str]]:
        """
        Récupère la liste complète de tous les fichiers téléchargeables
        pour toutes les ressources IGN

        Returns:
            Liste de dictionnaires avec 'url', 'title', 'resource' pour chaque fichier
        """
        logger.info("Récupération de la liste complète des fichiers IGN disponibles...")

        all_files = []

        # Récupérer toutes les ressources
        resources = self.get_all_resources()

        # Pour chaque ressource, récupérer les fichiers
        for idx, resource in enumerate(resources, 1):
            resource_title = resource['title']
            resource_url = resource['url']

            logger.info(f"[{idx}/{len(resources)}] Analyse de la ressource: {resource_title}")

            try:
                files = self.get_resource_files(resource_url)

                # Ajouter le nom de la ressource à chaque fichier
                for file_info in files:
                    file_info['resource'] = resource_title
                    all_files.append(file_info)

            except Exception as e:
                logger.warning(f"Impossible de récupérer les fichiers pour {resource_title}: {e}")
                continue

        logger.info(f"Total: {len(all_files)} fichiers disponibles pour téléchargement")
        return all_files

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
            temp_dir = Path(tempfile.gettempdir()) / "ign_downloads"
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

        logger.info(f"Début du téléchargement de {len(files_info)} fichiers IGN...")

        downloaded_files = []
        errors = []

        for idx, file_info in enumerate(files_info, 1):
            url = file_info["url"]
            title = file_info["title"]
            resource = file_info.get("resource", "")

            logger.info(f"[{idx}/{len(files_info)}] Téléchargement: {resource} - {title}")

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
        logger.info("Session IGN fermée")
