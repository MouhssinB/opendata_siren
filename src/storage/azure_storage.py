"""Gestionnaire de stockage Azure Blob Storage"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceExistsError, AzureError


logger = logging.getLogger(__name__)


class AzureStorageHandler:
    """Gestionnaire pour stocker les données dans Azure Blob Storage"""

    def __init__(self, storage_account_name: str, storage_account_key: str,
                 container_name: str, connection_string: Optional[str] = None):
        """
        Initialise le gestionnaire Azure Storage

        Args:
            storage_account_name: Nom du compte de stockage
            storage_account_key: Clé du compte de stockage
            container_name: Nom du conteneur
            connection_string: Connection string complète (optionnel)
        """
        self.container_name = container_name

        # Utiliser la connection string si fournie, sinon construire à partir des credentials
        if connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        else:
            account_url = f"https://{storage_account_name}.blob.core.windows.net"
            self.blob_service_client = BlobServiceClient(
                account_url=account_url,
                credential=storage_account_key
            )

        self.container_client: ContainerClient = None
        self._ensure_container()

        logger.info(f"Gestionnaire Azure Storage initialisé (conteneur: {container_name})")

    def _ensure_container(self):
        """Crée le conteneur s'il n'existe pas"""
        try:
            self.container_client = self.blob_service_client.get_container_client(self.container_name)

            # Vérifier si le conteneur existe
            if not self.container_client.exists():
                logger.info(f"Création du conteneur {self.container_name}")
                self.container_client.create_container()
            else:
                logger.info(f"Conteneur {self.container_name} existe déjà")

        except ResourceExistsError:
            logger.info(f"Conteneur {self.container_name} existe déjà")
            self.container_client = self.blob_service_client.get_container_client(self.container_name)
        except AzureError as e:
            logger.error(f"Erreur lors de la création du conteneur: {e}")
            raise

    def upload_json(self, data: List[Dict], blob_path: str, overwrite: bool = True) -> bool:
        """
        Upload des données JSON vers Azure Blob Storage

        Args:
            data: Données à uploader
            blob_path: Chemin du blob (ex: "siren/dept_75/2024-01-01.json")
            overwrite: Si True, écrase le blob existant

        Returns:
            True si succès
        """
        try:
            # Convertir les données en JSON
            json_data = json.dumps(data, ensure_ascii=False, indent=2)

            # Créer le blob client
            blob_client = self.container_client.get_blob_client(blob_path)

            # Upload
            logger.info(f"Upload de {len(data)} enregistrements vers {blob_path}")
            blob_client.upload_blob(json_data, overwrite=overwrite, encoding='utf-8')

            logger.info(f"Upload réussi: {blob_path}")
            return True

        except AzureError as e:
            logger.error(f"Erreur lors de l'upload vers {blob_path}: {e}")
            return False

    def upload_file(self, local_file_path: str, blob_path: str, overwrite: bool = True) -> bool:
        """
        Upload un fichier local vers Azure Blob Storage

        Args:
            local_file_path: Chemin du fichier local
            blob_path: Chemin du blob de destination
            overwrite: Si True, écrase le blob existant

        Returns:
            True si succès
        """
        try:
            local_path = Path(local_file_path)

            if not local_path.exists():
                logger.error(f"Fichier local non trouvé: {local_file_path}")
                return False

            blob_client = self.container_client.get_blob_client(blob_path)

            logger.info(f"Upload du fichier {local_file_path} vers {blob_path}")

            with open(local_path, 'rb') as data:
                blob_client.upload_blob(data, overwrite=overwrite)

            logger.info(f"Upload réussi: {blob_path}")
            return True

        except AzureError as e:
            logger.error(f"Erreur lors de l'upload du fichier {local_file_path}: {e}")
            return False

    def download_json(self, blob_path: str) -> Optional[List[Dict]]:
        """
        Télécharge et parse un fichier JSON depuis Azure

        Args:
            blob_path: Chemin du blob

        Returns:
            Données JSON ou None si erreur
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_path)

            logger.info(f"Téléchargement de {blob_path}")

            blob_data = blob_client.download_blob()
            content = blob_data.readall().decode('utf-8')

            data = json.loads(content)
            logger.info(f"Téléchargement réussi: {blob_path}")

            return data

        except AzureError as e:
            logger.error(f"Erreur lors du téléchargement de {blob_path}: {e}")
            return None

    def list_blobs(self, prefix: str = "") -> List[str]:
        """
        Liste les blobs dans le conteneur

        Args:
            prefix: Préfixe pour filtrer les blobs

        Returns:
            Liste des noms de blobs
        """
        try:
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            blob_names = [blob.name for blob in blobs]

            logger.info(f"Trouvé {len(blob_names)} blobs avec le préfixe '{prefix}'")
            return blob_names

        except AzureError as e:
            logger.error(f"Erreur lors du listing des blobs: {e}")
            return []

    def delete_blob(self, blob_path: str) -> bool:
        """
        Supprime un blob

        Args:
            blob_path: Chemin du blob à supprimer

        Returns:
            True si succès
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_path)
            blob_client.delete_blob()

            logger.info(f"Blob supprimé: {blob_path}")
            return True

        except AzureError as e:
            logger.error(f"Erreur lors de la suppression de {blob_path}: {e}")
            return False

    def blob_exists(self, blob_path: str) -> bool:
        """
        Vérifie si un blob existe

        Args:
            blob_path: Chemin du blob

        Returns:
            True si le blob existe
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_path)
            return blob_client.exists()

        except AzureError as e:
            logger.error(f"Erreur lors de la vérification de {blob_path}: {e}")
            return False

    def generate_blob_path(self, department: str, mode: str,
                          date: Optional[datetime] = None, data_type: str = "siret") -> str:
        """
        Génère un chemin de blob standardisé

        Args:
            department: Code département
            mode: Mode d'exécution (full ou delta)
            date: Date d'exécution (par défaut: maintenant)
            data_type: Type de données (siret ou siren)

        Returns:
            Chemin du blob (ex: "siret/dept_75/full/2024-01-01T10-30-00.json")
        """
        if date is None:
            date = datetime.now()

        # Format: YYYY-MM-DDTHH-MM-SS
        date_str = date.strftime("%Y-%m-%dT%H-%M-%S")

        # Construire le chemin: data_type/dept_XX/mode/date.json
        blob_path = f"{data_type}/dept_{department}/{mode}/{date_str}.json"

        return blob_path

    def get_metadata(self, blob_path: str) -> Optional[Dict]:
        """
        Récupère les métadonnées d'un blob

        Args:
            blob_path: Chemin du blob

        Returns:
            Dictionnaire des métadonnées ou None
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_path)
            properties = blob_client.get_blob_properties()

            metadata = {
                'name': blob_path,
                'size': properties.size,
                'last_modified': properties.last_modified,
                'content_type': properties.content_settings.content_type,
                'metadata': properties.metadata
            }

            return metadata

        except AzureError as e:
            logger.error(f"Erreur lors de la récupération des métadonnées de {blob_path}: {e}")
            return None

    def close(self):
        """Ferme les connexions"""
        if hasattr(self, 'blob_service_client'):
            self.blob_service_client.close()
        logger.info("Connexions Azure Storage fermées")
