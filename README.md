# SIREN Data Collector

Application Python pour collecter les données du portail SIREN de l'INSEE et les stocker dans Azure Blob Storage.

## 📋 Fonctionnalités

- ✅ Connexion à l'API SIREN de l'INSEE
- ✅ Deux modes de collecte : **Full** et **Delta**
- ✅ Collecte par département
- ✅ Stockage automatique dans Azure Blob Storage
- ✅ Gestion de l'état pour le mode delta
- ✅ Traitement parallèle des départements
- ✅ Exécution dans Docker
- ✅ Scheduler intégré pour exécutions hebdomadaires
- ✅ Logging complet avec rotation des fichiers

## 🚀 Installation

### Prérequis

- Docker et Docker Compose
- Compte API INSEE (https://api.insee.fr/)
- Compte Azure Storage

### Configuration rapide

1. **Cloner le projet**
```bash
git clone <votre-repo>
cd opendata_siren
```

2. **Créer le fichier .env**
```bash
cp .env.example .env
```

3. **Éditer le fichier .env avec vos identifiants**
```env
# API SIREN
API_CONSUMER_KEY=votre_cle_api
API_CONSUMER_SECRET=votre_secret_api

# Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=votre_compte_storage
AZURE_STORAGE_ACCOUNT_KEY=votre_cle_storage
AZURE_CONTAINER_NAME=siren-data

# Mode d'exécution
EXECUTION_MODE=full
```

4. **Configurer les départements dans config.yaml**
```yaml
departments:
  - "75"  # Paris
  - "92"  # Hauts-de-Seine
  # ... ajoutez vos départements
```

## 📖 Utilisation

### Avec Docker Compose (recommandé)

#### Exécution unique en mode FULL
```bash
docker-compose run --rm siren-collector --mode full
```

#### Exécution unique en mode DELTA
```bash
docker-compose run --rm siren-collector --mode delta
```

#### Exécution pour des départements spécifiques
```bash
docker-compose run --rm siren-collector --mode full --departments 75 92 93
```

#### Validation de la configuration uniquement
```bash
docker-compose run --rm siren-collector --validate-only
```

#### Mode scheduler (exécution hebdomadaire automatique)
```bash
# Activer le service scheduler
docker-compose --profile scheduler up -d siren-scheduler

# Voir les logs
docker-compose logs -f siren-scheduler

# Arrêter le scheduler
docker-compose --profile scheduler down
```

### Sans Docker (développement)

1. **Créer un environnement virtuel**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows
```

2. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

3. **Exécuter l'application**
```bash
python -m src.main --mode full
python -m src.main --mode delta --departments 75
python -m src.main --validate-only
```

## ⚙️ Configuration

### Fichier config.yaml

Le fichier `config.yaml` contient toutes les configurations de l'application :

```yaml
# Configuration API
api:
  base_url: "https://api.insee.fr/entreprises/sirene/V3"
  consumer_key: "YOUR_CONSUMER_KEY"  # Surchargé par .env
  consumer_secret: "YOUR_CONSUMER_SECRET"  # Surchargé par .env
  timeout: 30
  max_retries: 3
  rate_limit_delay: 1

# Mode d'exécution
execution:
  mode: "full"  # "full" ou "delta"
  schedule_cron: "0 2 * * 1"  # Lundi à 2h du matin

# Départements à traiter
departments:
  - "75"
  - "92"
  # Ou utilisez "all" pour tous les départements

# Configuration Azure
azure:
  storage_account_name: "YOUR_STORAGE_ACCOUNT"
  storage_account_key: "YOUR_STORAGE_ACCOUNT_KEY"
  container_name: "siren-data"

# Répertoires
directories:
  data_dir: "./data"
  logs_dir: "./logs"
  temp_dir: "./data/temp"
  state_file: "./data/state.json"

# Logging
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file_max_bytes: 10485760  # 10MB
  file_backup_count: 5

# Traitement
processing:
  batch_size: 1000
  max_workers: 4
  delta_days: 7
```

### Variables d'environnement

Les variables d'environnement dans `.env` surchargent la configuration :

- `API_CONSUMER_KEY` : Clé API INSEE
- `API_CONSUMER_SECRET` : Secret API INSEE
- `AZURE_STORAGE_ACCOUNT_NAME` : Nom du compte Azure Storage
- `AZURE_STORAGE_ACCOUNT_KEY` : Clé du compte Azure Storage
- `AZURE_CONTAINER_NAME` : Nom du conteneur
- `EXECUTION_MODE` : Mode d'exécution (full/delta)

## 🔄 Modes de fonctionnement

### Mode FULL
- Récupère **toutes** les données pour les départements configurés
- Utilisé lors de la première exécution
- Peut prendre plusieurs heures selon le nombre de départements

### Mode DELTA
- Récupère uniquement les **modifications** depuis la dernière exécution
- Beaucoup plus rapide
- Utilisé pour les exécutions hebdomadaires

### Logique automatique
- **Première exécution** : Toujours en mode FULL (même si delta est configuré)
- **Exécutions suivantes** : Utilise le mode configuré

## 📊 Structure des données Azure

Les données sont stockées dans Azure Blob Storage avec la structure suivante :

```
container-name/
├── siret/
│   ├── dept_75/
│   │   ├── full/
│   │   │   └── 2024-01-15T10-30-00.json
│   │   └── delta/
│   │       └── 2024-01-22T10-30-00.json
│   ├── dept_92/
│   │   ├── full/
│   │   └── delta/
```

## 📁 Structure du projet

```
opendata_siren/
├── src/
│   ├── __init__.py
│   ├── main.py              # Point d'entrée principal
│   ├── collector.py         # Logique de collecte
│   ├── api/
│   │   ├── __init__.py
│   │   └── siren_client.py  # Client API SIREN
│   ├── storage/
│   │   ├── __init__.py
│   │   └── azure_storage.py # Gestionnaire Azure Storage
│   ├── config/
│   │   ├── __init__.py
│   │   └── config_loader.py # Chargeur de configuration
│   └── models/
│       ├── __init__.py
│       └── state.py         # Gestion de l'état
├── data/                    # Données locales (gitignored)
├── logs/                    # Logs (gitignored)
├── config.yaml              # Configuration principale
├── .env.example             # Template des variables d'environnement
├── requirements.txt         # Dépendances Python
├── Dockerfile              # Image Docker
├── docker-compose.yml      # Orchestration Docker
├── scheduler.py            # Scheduler pour exécutions planifiées
└── README.md              # Cette documentation
```

## 🔍 Monitoring et logs

### Consulter les logs

**Avec Docker :**
```bash
# Logs du collecteur
docker-compose logs -f siren-collector

# Logs du scheduler
docker-compose --profile scheduler logs -f siren-scheduler

# Logs sauvegardés localement
tail -f logs/siren_collector.log
```

### État de l'application

L'application maintient un fichier d'état `data/state.json` qui contient :
- Date de dernière exécution
- Statistiques par département
- Nombre total d'enregistrements récupérés

## 🛠️ Options de ligne de commande

```bash
python -m src.main [OPTIONS]

Options:
  --config PATH              Chemin vers le fichier de configuration
                            (défaut: config.yaml)

  --mode {full,delta}       Mode d'exécution (override la config)

  --departments DEPT [DEPT ...]
                            Liste des départements à traiter
                            (override la config)

  --data-type {siret,siren,both}
                            Type de données à récupérer
                            (défaut: siret)

  --no-parallel            Désactiver le traitement parallèle

  --validate-only          Valider la configuration et quitter
```

## 📝 Exemples d'utilisation

### Exécution complète avec tous les départements configurés
```bash
docker-compose run --rm siren-collector --mode full
```

### Exécution delta pour Paris uniquement
```bash
docker-compose run --rm siren-collector --mode delta --departments 75
```

### Récupérer à la fois SIRET et SIREN
```bash
docker-compose run --rm siren-collector --mode full --data-type both
```

### Test de configuration
```bash
docker-compose run --rm siren-collector --validate-only
```

## 🔐 Sécurité

- ❌ **Ne commitez jamais** le fichier `.env`
- ❌ **Ne commitez jamais** les clés API dans `config.yaml`
- ✅ Utilisez toujours les variables d'environnement pour les secrets
- ✅ Gardez le fichier `.env.example` à jour

## 🐛 Dépannage

### Erreur d'authentification API
```
Vérifiez que vos clés API_CONSUMER_KEY et API_CONSUMER_SECRET sont correctes
```

### Erreur Azure Storage
```
Vérifiez que AZURE_STORAGE_ACCOUNT_NAME et AZURE_STORAGE_ACCOUNT_KEY sont corrects
```

### Aucune donnée récupérée
```
Vérifiez que les codes département sont corrects (ex: "75" pour Paris)
```

## 📚 Ressources

- [API SIREN INSEE](https://api.insee.fr/catalogue/)
- [Documentation API Sirene](https://www.sirene.fr/sirene/public/accueil)
- [Azure Blob Storage Python SDK](https://docs.microsoft.com/python/api/azure-storage-blob/)

## 📄 Licence

Ce projet est sous licence MIT.

## 👥 Support

Pour toute question ou problème, ouvrez une issue sur GitHub.
