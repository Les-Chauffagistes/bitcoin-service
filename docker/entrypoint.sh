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

# Migrations : Prisma pose lui-même un verrou consultatif, plusieurs réplicas qui démarrent
# ensemble s'attendent. set -e : un échec arrête le conteneur.
log "Application des migrations (prisma migrate deploy)..."
prisma migrate deploy
log "Migrations appliquées."

exec python main.py
