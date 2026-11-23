#!/bin/sh
# Point d'entrée de l'image : secrets -> migrations -> application.
# Aucune valeur d'environnement n'est figée dans l'image ; tout vient de l'exécution (variables
# d'environnement ou secrets Swarm montés dans /run/secrets).
set -eu

log() { printf '[entrypoint] %s\n' "$*"; }

# Secrets Swarm : VAR_FILE=/run/secrets/<nom> alimente VAR avec le contenu du fichier (fin de ligne
# retirée). Refus si VAR et VAR_FILE sont tous deux définis, pour ne pas choisir en silence.
for name in DATABASE_URL API_TOKEN BITCOIN_RPC_PASSWORD SHOP_WEBHOOK_SECRET XPUB; do
  file=$(printenv "${name}_FILE" || true)
  [ -n "$file" ] || continue
  if [ -n "$(printenv "$name" || true)" ]; then
    log "ERREUR : ${name} et ${name}_FILE sont tous deux définis, n'en garder qu'un."
    exit 1
  fi
  if [ ! -r "$file" ]; then
    log "ERREUR : ${name}_FILE pointe vers un fichier illisible (${file})."
    exit 1
  fi
  value=$(cat "$file")
  export "$name=$value"
  unset "${name}_FILE"
done

# DATABASE_URL construite depuis DB_HOST / DB_USER / DB_NAME (et DB_PORT, 5432 par défaut), comme les autres
# services du cluster Postgres HA : le mot de passe vient du secret db_password (ou DB_PASSWORD_FILE). Ignorée
# si DATABASE_URL est déjà définie (ou lue depuis DATABASE_URL_FILE ci-dessus).
if [ -z "$(printenv DATABASE_URL || true)" ] && [ -n "$(printenv DB_HOST || true)" ]; then
  for name in DB_USER DB_NAME; do
    if [ -z "$(printenv "$name" || true)" ]; then
      log "ERREUR : DB_HOST est défini, ${name} aussi doit l'être."
      exit 1
    fi
  done
  export DB_PASSWORD_FILE="${DB_PASSWORD_FILE:-/run/secrets/db_password}"
  if [ ! -r "$DB_PASSWORD_FILE" ]; then
    log "ERREUR : mot de passe de la base illisible (${DB_PASSWORD_FILE})."
    exit 1
  fi
  # Python pour l'encodage : un mot de passe peut contenir @, :, / ou %
  DATABASE_URL=$(python -c '
import os
from urllib.parse import quote

def q(value):
    return quote(value, safe="")

password = open(os.environ["DB_PASSWORD_FILE"]).read().rstrip("\r\n")
user, host, name = (os.environ[k] for k in ("DB_USER", "DB_HOST", "DB_NAME"))
port = os.environ.get("DB_PORT", "5432")
print("postgresql://" + q(user) + ":" + q(password) + "@" + host + ":" + port + "/" + q(name))
')
  export DATABASE_URL
  unset DB_PASSWORD_FILE
fi

# Migrations : Prisma pose lui-même un verrou consultatif, plusieurs réplicas qui démarrent
# ensemble s'attendent. set -e : un échec arrête le conteneur.
log "Application des migrations (prisma migrate deploy)..."
prisma migrate deploy
log "Migrations appliquées."

exec python main.py
