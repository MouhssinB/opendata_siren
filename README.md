# OpenData Collector - Téléchargement Mensuel INSEE & IGN

Application Python pour télécharger automatiquement les fichiers INSEE depuis data.gouv.fr et les fichiers IGN depuis data.geopf.fr, et les stocker dans Azure Blob Storage.

## 📋 Fonctionnalités

- ✅ **Téléchargement automatique des fichiers INSEE** depuis **data.gouv.fr**
- ✅ **Téléchargement automatique des fichiers IGN** depuis **data.geopf.fr**
- ✅ Exécution mensuelle programmée (le 2 de chaque mois par défaut)
- ✅ Logique **"Annule et Remplace"** : suppression des anciens fichiers avant upload des nouveaux
- ✅ Stockage automatique dans Azure Blob Storage avec répertoires séparés (insee/ et IGN/)
- ✅ Gestion des gros fichiers avec téléchargement en streaming
- ✅ Exécution dans Docker
- ✅ Scheduler intégré pour exécutions mensuelles automatiques
- ✅ Logging complet avec rotation des fichiers

## 🚀 Installation

### Prérequis

- Docker et Docker Compose
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

3. **Éditer le fichier .env avec vos identifiants Azure**
```env
# Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=votre_compte_storage
AZURE_STORAGE_ACCOUNT_KEY=votre_cle_storage
AZURE_CONTAINER_NAME=siren-data

# Planification mensuelle (optionnel)
MONTHLY_DAY=2  # Jour du mois (1-31)
MONTHLY_HOUR=2  # Heure (0-23)
```

4. **Configurer les préfixes de stockage dans config.yaml (optionnel)**
```yaml
execution:
  monthly_day: 2  # Le 2 de chaque mois
  monthly_hour: 2  # À 2h du matin

azure:
  blob_prefix: "insee/"  # Préfixe pour les fichiers INSEE

ign:
  blob_prefix: "IGN/"    # Préfixe pour les fichiers IGN
```

## 📖 Utilisation

### Avec Docker Compose (recommandé)

#### Mode scheduler (exécution mensuelle automatique)
```bash
# Activer le service scheduler
docker-compose --profile scheduler up -d siren-scheduler

# Voir les logs
docker-compose logs -f siren-scheduler

# Arrêter le scheduler
docker-compose --profile scheduler down
```

Le scheduler s'exécutera automatiquement le 2 de chaque mois à 2h du matin (ou selon votre configuration).

#### Exécution immédiate au démarrage (pour tester)
```bash
# Exécuter immédiatement au démarrage du scheduler
RUN_ON_STARTUP=true docker-compose --profile scheduler up siren-scheduler
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

3. **Exécuter le scheduler**
```bash
# Démarrer le scheduler mensuel
python scheduler.py

# Ou avec exécution immédiate
RUN_ON_STARTUP=true python scheduler.py
```

## ⚙️ Configuration

### Fichier config.yaml

Le fichier `config.yaml` contient toutes les configurations de l'application :

```yaml
# Planification mensuelle
execution:
  monthly_day: 2  # Jour du mois (1-31)
  monthly_hour: 2  # Heure de la journée (0-23)

# Configuration Azure
azure:
  storage_account_name: "YOUR_STORAGE_ACCOUNT"
  storage_account_key: "YOUR_STORAGE_ACCOUNT_KEY"
  container_name: "siren-data"
  connection_string: ""  # Optionnel: connection string complète
  blob_prefix: "insee/"  # Préfixe pour les fichiers dans le container

# Répertoires
directories:
  data_dir: "./data"
  logs_dir: "./logs"
  temp_dir: "./data/temp"

# Logging
logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file_max_bytes: 10485760  # 10MB
  file_backup_count: 5

# Traitement
processing:
  download_timeout: 120  # Timeout pour le téléchargement des fichiers (en secondes)
```

### Variables d'environnement

Les variables d'environnement dans `.env` surchargent la configuration :

- `AZURE_STORAGE_ACCOUNT_NAME` : Nom du compte Azure Storage
- `AZURE_STORAGE_ACCOUNT_KEY` : Clé du compte Azure Storage
- `AZURE_CONTAINER_NAME` : Nom du conteneur
- `MONTHLY_DAY` : Jour du mois pour l'exécution (1-31)
- `MONTHLY_HOUR` : Heure de la journée pour l'exécution (0-23)
- `RUN_ON_STARTUP` : Exécuter immédiatement au démarrage (true/false)

## 🔄 Fonctionnement

### Collecte mensuelle automatique

L'application fonctionne selon le principe **"Annule et Remplace"** pour chaque source de données :

1. **Le 2 de chaque mois à 2h** (configurable)
2. **Collecte INSEE** :
   - **ÉTAPE 1** : Suppression de tous les fichiers existants dans Azure Storage (préfixe insee/)
   - **ÉTAPE 2** : Téléchargement de tous les fichiers disponibles depuis data.gouv.fr
   - **ÉTAPE 3** : Upload des fichiers téléchargés vers Azure Storage
3. **Collecte IGN** :
   - **ÉTAPE 1** : Suppression de tous les fichiers existants dans Azure Storage (préfixe IGN/)
   - **ÉTAPE 2** : Téléchargement de tous les fichiers disponibles depuis data.geopf.fr
   - **ÉTAPE 3** : Upload des fichiers téléchargés vers Azure Storage

### Sources des données

#### INSEE
Les fichiers sont récupérés depuis le dataset officiel data.gouv.fr :
- **Dataset** : "Base SIRENE des entreprises et de leurs établissements (SIREN, SIRET)"
- **URL** : https://www.data.gouv.fr/fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/

#### IGN
Les fichiers sont récupérés depuis le service de téléchargement public de la Géoplateforme IGN :
- **Service** : Public Download Service of Géoplateforme
- **URL** : https://data.geopf.fr/telechargement/capabilities
- **Ressources** : ADMIN-EXPRESS, ADMIN EXPRESS COG, BD TOPO, et bien d'autres (93 ressources au total)

## 📊 Structure des données Azure

Les données sont stockées dans Azure Blob Storage avec la structure suivante :

```
container-name/
├── insee/
│   ├── StockEtablissement_utf8.csv
│   ├── StockUniteLegale_utf8.csv
│   └── [autres fichiers INSEE...]
├── IGN/
│   ├── ADMIN-EXPRESS_*.7z
│   ├── ADMIN-EXPRESS-COG_*.7z
│   └── [autres fichiers IGN...]
```

Tous les fichiers disponibles sont téléchargés et stockés dans des préfixes séparés (configurable).

## 📁 Structure du projet

```
opendata_siren/
├── src/
│   ├── __init__.py
│   ├── main.py                   # Point d'entrée principal (legacy)
│   ├── downloader.py             # Module de téléchargement INSEE depuis data.gouv.fr
│   ├── ign_downloader.py         # Module de téléchargement IGN depuis data.geopf.fr
│   ├── monthly_collector.py      # Collecteur mensuel INSEE
│   ├── ign_monthly_collector.py  # Collecteur mensuel IGN
│   ├── collector.py              # Ancien collecteur (legacy)
│   ├── api/
│   │   ├── __init__.py
│   │   └── siren_client.py       # Client API SIREN (legacy)
│   ├── storage/
│   │   ├── __init__.py
│   │   └── azure_storage.py      # Gestionnaire Azure Storage
│   ├── config/
│   │   ├── __init__.py
│   │   └── config_loader.py      # Chargeur de configuration
│   └── models/
│       ├── __init__.py
│       └── state.py              # Gestion de l'état (legacy)
├── data/                         # Données locales (gitignored)
│   └── temp/                     # Fichiers temporaires de téléchargement
│       ├── insee/                # Fichiers temporaires INSEE
│       └── ign/                  # Fichiers temporaires IGN
├── logs/                         # Logs (gitignored)
├── config.yaml                   # Configuration principale
├── .env.example                  # Template des variables d'environnement
├── requirements.txt              # Dépendances Python
├── Dockerfile                    # Image Docker
├── docker-compose.yml            # Orchestration Docker
├── scheduler.py                  # Scheduler pour exécutions mensuelles (INSEE + IGN)
└── README.md                     # Cette documentation
```

## 🔍 Monitoring et logs

### Consulter les logs

**Avec Docker :**
```bash
# Logs du scheduler mensuel
docker-compose --profile scheduler logs -f siren-scheduler

# Logs sauvegardés localement
tail -f logs/siren_collector.log
```

### Informations de suivi

Les logs contiennent des informations détaillées sur :
- Date et heure de chaque exécution (INSEE et IGN)
- Nombre de fichiers supprimés pour chaque source (annule et remplace)
- Nombre de fichiers téléchargés pour chaque source
- Nombre de fichiers uploadés vers Azure pour chaque source
- Progression du téléchargement des gros fichiers
- Liste des ressources IGN récupérées
- Erreurs éventuelles
- Durée totale de l'exécution

## 🔐 Sécurité

- ❌ **Ne commitez jamais** le fichier `.env`
- ❌ **Ne commitez jamais** les clés Azure dans `config.yaml`
- ✅ Utilisez toujours les variables d'environnement pour les secrets
- ✅ Gardez le fichier `.env.example` à jour

## 🐛 Dépannage

### Erreur Azure Storage
```
Vérifiez que AZURE_STORAGE_ACCOUNT_NAME et AZURE_STORAGE_ACCOUNT_KEY sont corrects
```

### Erreur de téléchargement depuis data.gouv.fr
```
Vérifiez votre connexion Internet et que le site data.gouv.fr est accessible
```

### Le scheduler ne s'exécute pas
```
Vérifiez que la date et l'heure système du serveur sont correctes
Consultez les logs pour voir si des erreurs sont survenues
```

### Fichiers volumineux
```
Les fichiers INSEE peuvent être très volumineux (plusieurs GB)
Assurez-vous d'avoir suffisamment d'espace disque temporaire
Le téléchargement peut prendre plusieurs heures selon votre connexion
```

## 📚 Ressources

### INSEE
- [Dataset data.gouv.fr - Base SIRENE](https://www.data.gouv.fr/fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/)
- [Documentation SIRENE](https://www.sirene.fr/sirene/public/accueil)
- [API data.gouv.fr](https://www.data.gouv.fr/fr/apidoc/)

### IGN
- [Service de téléchargement IGN Géoplateforme](https://data.geopf.fr/telechargement/capabilities)
- [Documentation IGN](https://geoservices.ign.fr/)
- [Conditions Générales d'Utilisation IGN](https://geoservices.ign.fr/cgu-licences)

### Azure
- [Azure Blob Storage Python SDK](https://docs.microsoft.com/python/api/azure-storage-blob/)

## 📄 Licence

Ce projet est sous licence MIT.

## 👥 Support

Pour toute question ou problème, ouvrez une issue sur GitHub.
