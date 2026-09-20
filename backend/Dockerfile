FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Utilisateur non-root : principe du moindre privilège même dans le conteneur.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000

# ${PORT:-8000} : Railway (et d'autres PaaS) injectent un PORT dynamique à
# l'exécution — repli sur 8000 en local/Docker Compose où PORT n'est pas
# défini. Les migrations Alembic s'exécutent avant de servir, pour qu'un
# déploiement ne serve jamais un schéma obsolète.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
