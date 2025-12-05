"""Tests pour le module de configuration"""
import os
import pytest
from pathlib import Path
from src.config import ConfigLoader


def test_config_loader():
    """Test le chargement de la configuration"""
    config = ConfigLoader('config.yaml')
    assert config is not None
    assert config.config is not None


def test_get_api_config():
    """Test la récupération de la config API"""
    config = ConfigLoader('config.yaml')
    api_config = config.get_api_config()

    assert 'base_url' in api_config
    assert 'consumer_key' in api_config
    assert 'consumer_secret' in api_config


def test_get_execution_mode():
    """Test la récupération du mode d'exécution"""
    config = ConfigLoader('config.yaml')
    mode = config.get_execution_mode()

    assert mode in ['full', 'delta']


def test_get_departments():
    """Test la récupération des départements"""
    config = ConfigLoader('config.yaml')
    departments = config.get_departments()

    assert isinstance(departments, list)
    assert len(departments) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
