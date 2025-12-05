"""Configuration loader module"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import load_dotenv


class ConfigLoader:
    """Charge et gère la configuration de l'application"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialise le chargeur de configuration

        Args:
            config_path: Chemin vers le fichier de configuration YAML
        """
        # Charger les variables d'environnement depuis .env
        load_dotenv()

        # Définir le chemin par défaut
        if config_path is None:
            config_path = os.getenv('CONFIG_PATH', 'config.yaml')

        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self._load_config()
        self._override_with_env()

    def _load_config(self):
        """Charge le fichier de configuration YAML"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Fichier de configuration non trouvé: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

    def _override_with_env(self):
        """Override la configuration avec les variables d'environnement"""
        # Azure
        if os.getenv('AZURE_STORAGE_ACCOUNT_NAME'):
            if 'azure' not in self.config:
                self.config['azure'] = {}
            self.config['azure']['storage_account_name'] = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
        if os.getenv('AZURE_STORAGE_ACCOUNT_KEY'):
            if 'azure' not in self.config:
                self.config['azure'] = {}
            self.config['azure']['storage_account_key'] = os.getenv('AZURE_STORAGE_ACCOUNT_KEY')
        if os.getenv('AZURE_CONTAINER_NAME'):
            if 'azure' not in self.config:
                self.config['azure'] = {}
            self.config['azure']['container_name'] = os.getenv('AZURE_CONTAINER_NAME')
        if os.getenv('AZURE_CONNECTION_STRING'):
            if 'azure' not in self.config:
                self.config['azure'] = {}
            self.config['azure']['connection_string'] = os.getenv('AZURE_CONNECTION_STRING')

        # Planification mensuelle
        if os.getenv('MONTHLY_DAY'):
            if 'execution' not in self.config:
                self.config['execution'] = {}
            self.config['execution']['monthly_day'] = int(os.getenv('MONTHLY_DAY'))
        if os.getenv('MONTHLY_HOUR'):
            if 'execution' not in self.config:
                self.config['execution'] = {}
            self.config['execution']['monthly_hour'] = int(os.getenv('MONTHLY_HOUR'))

    def get(self, key: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration

        Args:
            key: Clé de configuration (supporte la notation pointée, ex: 'api.base_url')
            default: Valeur par défaut si la clé n'existe pas

        Returns:
            Valeur de configuration
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_api_config(self) -> Dict[str, Any]:
        """Retourne la configuration API"""
        return self.config.get('api', {})

    def get_azure_config(self) -> Dict[str, Any]:
        """Retourne la configuration Azure"""
        return self.config.get('azure', {})

    def get_execution_mode(self) -> str:
        """Retourne le mode d'exécution (full ou delta)"""
        return self.config.get('execution', {}).get('mode', 'full')

    def get_departments(self) -> list:
        """Retourne la liste des départements à traiter"""
        deps = self.config.get('departments', [])
        if deps == "all" or (isinstance(deps, list) and len(deps) == 1 and deps[0] == "all"):
            # Retourner tous les départements français (01-95 + DOM-TOM)
            return [f"{i:02d}" for i in range(1, 96)] + ['971', '972', '973', '974', '976']
        return deps

    def get_directories(self) -> Dict[str, str]:
        """Retourne la configuration des répertoires"""
        return self.config.get('directories', {})

    def validate(self) -> bool:
        """
        Valide la configuration

        Returns:
            True si la configuration est valide

        Raises:
            ValueError: Si la configuration est invalide
        """
        # Vérifier Azure
        storage_account = self.config.get('azure', {}).get('storage_account_name')
        storage_key = self.config.get('azure', {}).get('storage_account_key')
        connection_string = self.config.get('azure', {}).get('connection_string')

        if not connection_string:
            if not storage_account or storage_account == 'YOUR_STORAGE_ACCOUNT':
                raise ValueError("Azure storage_account_name non configuré")

            if not storage_key or storage_key == 'YOUR_STORAGE_ACCOUNT_KEY':
                raise ValueError("Azure storage_account_key non configuré")

        # Vérifier la planification mensuelle
        monthly_day = self.config.get('execution', {}).get('monthly_day', 2)
        if not isinstance(monthly_day, int) or monthly_day < 1 or monthly_day > 31:
            raise ValueError(f"monthly_day invalide: {monthly_day}. Doit être entre 1 et 31")

        monthly_hour = self.config.get('execution', {}).get('monthly_hour', 2)
        if not isinstance(monthly_hour, int) or monthly_hour < 0 or monthly_hour > 23:
            raise ValueError(f"monthly_hour invalide: {monthly_hour}. Doit être entre 0 et 23")

        return True
