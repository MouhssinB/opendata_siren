# Architecture - SIREN Data Collector

## Vue d'ensemble

L'application SIREN Data Collector est une application Python conteneurisée qui récupère les données du registre SIREN via l'API INSEE et les stocke dans Azure Blob Storage.

## 🏗️ Architecture technique

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Container                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │              Main Application                       │    │
│  │                 (src/main.py)                       │    │
│  └──────────────┬──────────────────────────────────────┘    │
│                 │                                            │
│  ┌──────────────▼──────────────────────────────────────┐    │
│  │           SirenCollector                             │    │
│  │          (src/collector.py)                          │    │
│  │  - Orchestre la collecte                             │    │
│  │  - Gère les modes full/delta                         │    │
│  │  - Traitement parallèle                              │    │
│  └─┬──────────┬──────────────┬────────────────────────┘    │
│    │          │              │                              │
│    │          │              │                              │
│  ┌─▼──────┐ ┌─▼──────────┐ ┌─▼────────────┐               │
│  │ API    │ │  Storage   │ │    State     │               │
│  │ Client │ │  Handler   │ │   Manager    │               │
│  └────────┘ └────────────┘ └──────────────┘               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │              │                │
         │              │                │
         ▼              ▼                ▼
   ┌──────────┐   ┌──────────┐    ┌──────────┐
   │   API    │   │  Azure   │    │  Local   │
   │  INSEE   │   │ Storage  │    │  State   │
   │  SIREN   │   │   Blob   │    │  File    │
   └──────────┘   └──────────┘    └──────────┘
```

## 📦 Modules

### 1. Config Module (`src/config/`)

**Responsabilité** : Gestion de la configuration

- `ConfigLoader` : Charge et valide la configuration depuis YAML et variables d'environnement
- Supporte le override par variables d'environnement
- Validation des paramètres obligatoires

### 2. API Module (`src/api/`)

**Responsabilité** : Communication avec l'API SIREN

- `SirenAPIClient` : Client HTTP pour l'API INSEE
- Authentification OAuth2
- Gestion du rate limiting
- Pagination automatique
- Retry en cas d'erreur

**Endpoints utilisés** :
- `/siret` : Établissements
- `/siren` : Unités légales

### 3. Storage Module (`src/storage/`)

**Responsabilité** : Stockage des données dans Azure

- `AzureStorageHandler` : Gestion des opérations Azure Blob Storage
- Upload de fichiers JSON
- Organisation hiérarchique des données
- Gestion des métadonnées

### 4. Models Module (`src/models/`)

**Responsabilité** : Gestion de l'état

- `StateManager` : Tracking de l'état des exécutions
- Stockage des dates de dernière exécution
- Statistiques d'exécution

### 5. Collector (`src/collector.py`)

**Responsabilité** : Orchestration principale

- Coordination des modules
- Logique full/delta
- Traitement parallèle des départements
- Gestion des batches

### 6. Main (`src/main.py`)

**Responsabilité** : Point d'entrée

- Parsing des arguments CLI
- Configuration du logging
- Initialisation des composants
- Gestion des erreurs

## 🔄 Flux de données

### Mode FULL

```
1. Démarrage
   ↓
2. Chargement config
   ↓
3. Initialisation des composants
   ↓
4. Pour chaque département:
   ├─ Récupération de toutes les données (pagination)
   ├─ Upload par batch vers Azure
   └─ Mise à jour de l'état
   ↓
5. Statistiques et nettoyage
```

### Mode DELTA

```
1. Démarrage
   ↓
2. Chargement config + état précédent
   ↓
3. Calcul de la date de début (last_execution)
   ↓
4. Pour chaque département:
   ├─ Récupération des modifications depuis last_execution
   ├─ Upload par batch vers Azure
   └─ Mise à jour de l'état
   ↓
5. Statistiques et nettoyage
```

## 🔐 Sécurité

### Secrets Management

1. **Variables d'environnement** : Toutes les clés sensibles
2. **Fichier .env** : Non commité dans Git
3. **Config override** : Les env vars surchargent le YAML

### API Authentication

- OAuth2 avec Consumer Key/Secret
- Token avec expiration automatique
- Refresh automatique du token

### Azure Storage

- Clés d'accès via variables d'environnement
- Support des connection strings
- HTTPS uniquement

## 📊 Gestion de l'état

### Fichier state.json

```json
{
  "last_execution": "2024-01-15T10:30:00",
  "last_mode": "full",
  "departments": {
    "75": {
      "first_execution": "2024-01-15T10:30:00",
      "last_execution": "2024-01-22T10:30:00",
      "total_records": 150000,
      "executions_count": 2
    }
  },
  "statistics": {
    "total_executions": 2,
    "total_records_fetched": 300000,
    "last_execution_records": 150000
  }
}
```

### Utilisation

- **Première exécution** : Force le mode FULL
- **Mode delta** : Utilise `last_execution` pour filtrer
- **Statistiques** : Monitoring et métriques

## 🐳 Containerisation

### Image Docker

- **Base** : `python:3.11-slim`
- **Taille** : ~200 MB
- **Dépendances** : Installées via pip
- **Volumes** : data/, logs/

### Docker Compose

Deux services :

1. **siren-collector** : Exécution unique
2. **siren-scheduler** : Exécution planifiée (profile)

## ⚡ Performance

### Traitement parallèle

- Thread pool pour les départements
- Configurable via `max_workers`
- Limitation pour éviter le rate limiting API

### Batching

- Upload par lots de 10 000 enregistrements
- Évite les fichiers trop gros
- Optimise les transferts Azure

### Rate Limiting

- Délai configurable entre les appels API
- Respect des limites INSEE
- Retry avec backoff exponentiel

## 📈 Scalabilité

### Limitations actuelles

- **API INSEE** : Rate limit (~100 req/min)
- **Mémoire** : Batching pour limiter l'usage
- **Stockage** : Illimité côté Azure

### Optimisations possibles

1. **Parallélisation** : Augmenter max_workers si rate limit le permet
2. **Cache** : Mettre en cache les départements déjà traités
3. **Compression** : Compresser les JSON avant upload
4. **Streaming** : Streaming direct vers Azure sans stockage local

## 🔍 Monitoring

### Logs

- **Niveau** : Configurable (DEBUG, INFO, etc.)
- **Destination** : STDOUT + fichier avec rotation
- **Format** : Timestamp + Level + Message

### Métriques

- Nombre d'enregistrements par département
- Temps d'exécution
- Taux de succès
- Erreurs API

### État

- Fichier JSON persistant
- Historique des exécutions
- Statistiques cumulatives

## 🛠️ Extensibilité

### Ajouter un nouveau type de données

1. Créer une méthode dans `SirenAPIClient`
2. Ajouter l'option dans `collector.py`
3. Mettre à jour la CLI dans `main.py`

### Ajouter un nouveau storage backend

1. Créer un nouveau handler dans `src/storage/`
2. Implémenter l'interface : `upload_json()`, `download_json()`, etc.
3. Configurer dans `config.yaml`

### Ajouter des notifications

1. Créer un module `src/notifications/`
2. Implémenter : email, Slack, Teams, etc.
3. Appeler depuis `collector.py` après exécution

## 🧪 Tests

### Tests unitaires

- Configuration : `tests/test_config.py`
- API Client : `tests/test_api.py` (à créer)
- Storage : `tests/test_storage.py` (à créer)

### Tests d'intégration

- Exécution complète avec mock API
- Validation des données uploadées

## 📝 Dépendances principales

- **requests** : Appels HTTP
- **azure-storage-blob** : Stockage Azure
- **pyyaml** : Configuration
- **python-dotenv** : Variables d'environnement
- **schedule** : Planification (scheduler)

## 🔄 Cycle de vie

```
┌─────────────┐
│   Build     │ → docker build
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Config    │ → .env + config.yaml
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ First Run   │ → Mode FULL automatique
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Scheduler  │ → Exécutions DELTA hebdomadaires
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Monitoring │ → Logs + State + Azure
└─────────────┘
```

## 🎯 Bonnes pratiques

1. **Configuration** : Toujours via fichier YAML + env vars
2. **Secrets** : Jamais dans le code ou Git
3. **Logs** : Niveau INFO en production, DEBUG pour debug
4. **État** : Vérifier régulièrement state.json
5. **Azure** : Vérifier les données uploadées après chaque exécution
6. **Mode** : FULL pour la première fois, DELTA ensuite
7. **Départements** : Tester avec 1-2 départements avant de lancer tous
8. **Monitoring** : Surveiller les logs du scheduler

## 📚 Références

- [API SIREN Documentation](https://api.insee.fr/catalogue/)
- [Azure Blob Storage SDK](https://docs.microsoft.com/python/api/azure-storage-blob/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
