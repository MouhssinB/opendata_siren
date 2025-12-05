"""State management for tracking execution state"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class StateManager:
    """Gère l'état des exécutions pour le mode delta"""

    def __init__(self, state_file: str):
        """
        Initialise le gestionnaire d'état

        Args:
            state_file: Chemin vers le fichier d'état
        """
        self.state_file = Path(state_file)
        self.state: Dict = {}
        self._load_state()

    def _load_state(self):
        """Charge l'état depuis le fichier"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
            except json.JSONDecodeError:
                self.state = self._get_default_state()
        else:
            self.state = self._get_default_state()

    def _get_default_state(self) -> Dict:
        """Retourne l'état par défaut"""
        return {
            'last_execution': None,
            'last_mode': None,
            'departments': {},
            'statistics': {
                'total_executions': 0,
                'total_records_fetched': 0,
                'last_execution_records': 0
            }
        }

    def save_state(self):
        """Sauvegarde l'état dans le fichier"""
        # Créer le répertoire si nécessaire
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, indent=2, fp=f)

    def get_last_execution(self) -> Optional[str]:
        """
        Récupère la date de dernière exécution

        Returns:
            Date ISO de dernière exécution ou None
        """
        return self.state.get('last_execution')

    def get_last_execution_for_department(self, department: str) -> Optional[str]:
        """
        Récupère la date de dernière exécution pour un département

        Args:
            department: Code département

        Returns:
            Date ISO de dernière exécution ou None
        """
        return self.state.get('departments', {}).get(department, {}).get('last_execution')

    def update_execution(self, mode: str, department: str, records_count: int):
        """
        Met à jour l'état après une exécution

        Args:
            mode: Mode d'exécution (full ou delta)
            department: Code département
            records_count: Nombre d'enregistrements récupérés
        """
        now = datetime.utcnow().isoformat()

        # Mettre à jour l'exécution globale
        self.state['last_execution'] = now
        self.state['last_mode'] = mode

        # Mettre à jour les statistiques
        self.state['statistics']['total_executions'] += 1
        self.state['statistics']['total_records_fetched'] += records_count
        self.state['statistics']['last_execution_records'] = records_count

        # Mettre à jour le département
        if 'departments' not in self.state:
            self.state['departments'] = {}

        if department not in self.state['departments']:
            self.state['departments'][department] = {
                'first_execution': now,
                'last_execution': now,
                'total_records': records_count,
                'executions_count': 1
            }
        else:
            self.state['departments'][department]['last_execution'] = now
            self.state['departments'][department]['total_records'] += records_count
            self.state['departments'][department]['executions_count'] += 1

        self.save_state()

    def is_first_execution(self) -> bool:
        """
        Vérifie si c'est la première exécution

        Returns:
            True si première exécution
        """
        return self.state.get('last_execution') is None

    def get_statistics(self) -> Dict:
        """
        Récupère les statistiques

        Returns:
            Dictionnaire des statistiques
        """
        return self.state.get('statistics', {})
