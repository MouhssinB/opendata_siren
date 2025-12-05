# Guide de Déploiement - SIREN Data Collector

Ce guide détaille le déploiement de l'application SIREN Data Collector en production.

## 📋 Prérequis

### 1. Compte API INSEE

1. Créer un compte sur https://api.insee.fr/
2. S'abonner à l'API Sirene V3
3. Récupérer les credentials (Consumer Key et Consumer Secret)

### 2. Compte Azure Storage

1. Créer un compte de stockage Azure
2. Créer un conteneur blob (ex: "siren-data")
3. Récupérer les clés d'accès

### 3. Serveur de déploiement

- Docker 20.10+
- Docker Compose 2.0+
- Minimum 2 GB RAM
- Minimum 20 GB d'espace disque

## 🚀 Déploiement

### Étape 1 : Cloner le projet

```bash
git clone <your-repo>
cd opendata_siren
```

### Étape 2 : Configuration initiale

```bash
# Utiliser le Makefile pour la configuration
make setup
```

### Étape 3 : Configurer les identifiants

Éditer le fichier `.env` :

```env
# API SIREN
API_CONSUMER_KEY=votre_cle_consumer
API_CONSUMER_SECRET=votre_secret_consumer

# Azure Storage
AZURE_STORAGE_ACCOUNT_NAME=votre_compte_storage
AZURE_STORAGE_ACCOUNT_KEY=votre_cle_storage
AZURE_CONTAINER_NAME=siren-data

# Mode d'exécution
EXECUTION_MODE=full
```

### Étape 4 : Configurer les départements

Éditer `config.yaml` :

```yaml
departments:
  - "75"  # Paris
  - "92"  # Hauts-de-Seine
  - "93"  # Seine-Saint-Denis
  # ... ajoutez tous vos départements
```

**Astuce** : Pour tous les départements, utilisez `"all"` au lieu de lister tous les codes.

### Étape 5 : Valider la configuration

```bash
make validate
```

Vous devriez voir : `✓ Configuration validée`

### Étape 6 : Première exécution (mode FULL)

```bash
make run-full
```

**Important** : La première exécution peut prendre plusieurs heures selon le nombre de départements.

### Étape 7 : Activer le scheduler pour les exécutions hebdomadaires

```bash
make scheduler
```

Pour vérifier que le scheduler fonctionne :

```bash
make scheduler-logs
```

## ⚙️ Configuration du planning

### Modifier la fréquence d'exécution

Éditer `config.yaml` :

```yaml
execution:
  schedule_cron: "0 2 * * 1"  # Lundi à 2h du matin
```

Format CRON : `minute heure jour_du_mois mois jour_de_la_semaine`

Exemples :
- `0 2 * * 1` : Lundi à 2h
- `0 3 * * 0` : Dimanche à 3h
- `0 1 * * 6` : Samedi à 1h
- `0 4 1 * *` : Le 1er de chaque mois à 4h

Ou via variable d'environnement :

```env
CRON_SCHEDULE=0 2 * * 1
```

## 🔄 Gestion du cycle de vie

### Arrêter le scheduler

```bash
make scheduler-stop
```

### Redémarrer le scheduler

```bash
make scheduler-stop
make scheduler
```

### Exécution manuelle en mode DELTA

```bash
make run-delta
```

### Voir les logs en temps réel

```bash
make logs
```

## 📊 Monitoring

### Vérifier l'état de l'application

```bash
# Voir le fichier d'état
cat data/state.json
```

Ce fichier contient :
- Date de dernière exécution
- Mode de dernière exécution
- Statistiques par département
- Statistiques globales

### Vérifier les données dans Azure

Utilisez Azure Storage Explorer ou le portail Azure pour vérifier que les données sont bien uploadées.

Structure dans Azure :
```
siren-data/
├── siret/
│   ├── dept_75/
│   │   ├── full/
│   │   │   └── 2024-01-15T10-30-00.json
│   │   └── delta/
│   │       └── 2024-01-22T10-30-00.json
```

### Logs

Les logs sont sauvegardés dans `logs/siren_collector.log` avec rotation automatique.

## 🔒 Sécurité

### Recommandations

1. **Ne jamais commiter le fichier .env**
2. **Utiliser des secrets managers en production** (Azure Key Vault, AWS Secrets Manager, etc.)
3. **Restreindre l'accès au serveur**
4. **Utiliser HTTPS pour l'API Azure**
5. **Mettre à jour régulièrement les dépendances**

### Rotation des clés

Si vous devez changer les clés API ou Azure :

1. Arrêter le scheduler : `make scheduler-stop`
2. Modifier le fichier `.env`
3. Redémarrer : `make scheduler`

## 🐛 Dépannage

### Le scheduler ne démarre pas

```bash
# Vérifier les logs
docker-compose --profile scheduler logs siren-scheduler

# Vérifier que le container est running
docker ps | grep siren-scheduler
```

### Erreur "API key invalid"

- Vérifiez que les clés API sont correctes dans `.env`
- Vérifiez que vous êtes bien abonné à l'API Sirene V3 sur api.insee.fr

### Erreur "Azure Storage authentication failed"

- Vérifiez le nom du compte de stockage
- Vérifiez la clé d'accès
- Vérifiez que le conteneur existe

### Pas de données récupérées

- Vérifiez les codes département dans `config.yaml`
- Vérifiez les logs pour voir s'il y a des erreurs
- Testez avec un seul département d'abord : `make run-full --departments 75`

### Le container crash au démarrage

```bash
# Voir les logs complets
docker-compose logs siren-collector

# Valider la configuration
make validate
```

## 📈 Optimisation

### Pour de gros volumes

Si vous récupérez beaucoup de départements :

1. **Augmenter le nombre de workers** dans `config.yaml` :
```yaml
processing:
  max_workers: 8  # Au lieu de 4
```

2. **Augmenter la mémoire Docker** si nécessaire

3. **Activer le traitement par batch** (déjà configuré par défaut)

### Réduire les coûts Azure

- Utilisez le stockage "Cool" ou "Archive" pour les anciennes données
- Activez la compression des fichiers JSON
- Supprimez les anciennes données FULL si vous avez des deltas réguliers

## 🔄 Mise à jour de l'application

```bash
# Arrêter le scheduler
make scheduler-stop

# Récupérer les dernières modifications
git pull

# Reconstruire l'image
make build

# Redémarrer le scheduler
make scheduler
```

## 📞 Support

En cas de problème :

1. Vérifiez les logs : `make logs`
2. Vérifiez l'état : `cat data/state.json`
3. Validez la configuration : `make validate`
4. Consultez la documentation API INSEE
5. Ouvrez une issue sur GitHub

## 🎯 Checklist de déploiement

- [ ] Serveur avec Docker installé
- [ ] Compte API INSEE créé et clés récupérées
- [ ] Compte Azure Storage créé
- [ ] Conteneur blob créé
- [ ] Projet cloné
- [ ] Fichier .env configuré
- [ ] Départements configurés dans config.yaml
- [ ] Configuration validée (make validate)
- [ ] Première exécution FULL réussie
- [ ] Scheduler démarré
- [ ] Logs vérifiés
- [ ] Données dans Azure vérifiées
- [ ] Monitoring mis en place
