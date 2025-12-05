# Image de base Python
FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Installer les dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le code de l'application
COPY src/ ./src/
COPY config.yaml .

# Créer les répertoires de données
RUN mkdir -p /app/data /app/logs /app/data/temp

# Exposer le volume pour les données persistantes
VOLUME ["/app/data", "/app/logs"]

# Point d'entrée
ENTRYPOINT ["python", "-m", "src.main"]

# Arguments par défaut (peuvent être overridés)
CMD ["--config", "config.yaml"]
