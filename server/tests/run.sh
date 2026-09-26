#!/bin/bash
# Applies the Supabase migrations to a throwaway local PostgreSQL and runs the market
# checks. Needs the PostgreSQL server binaries (e.g. apt install postgresql).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PGBIN="${PGBIN:-$(ls -d /usr/lib/postgresql/*/bin | tail -1)}"
DIR="$(mktemp -d)"
trap '"$PGBIN/pg_ctl" -D "$DIR/data" stop -m immediate >/dev/null 2>&1 || true; rm -rf "$DIR"' EXIT
if [ "$(id -u)" = "0" ]; then RUN="runuser -u postgres --"; chown -R postgres "$DIR"; else RUN=""; fi
$RUN "$PGBIN/initdb" -D "$DIR/data" -U postgres >/dev/null
$RUN "$PGBIN/pg_ctl" -D "$DIR/data" -o "-k $DIR -c listen_addresses=''" -w start >/dev/null
PSQL=(psql -h "$DIR" -U postgres -d postgres -v ON_ERROR_STOP=1 -q)
"${PSQL[@]}" -f "$HERE/auth_stub.sql"
for f in "$HERE"/../supabase/migrations/*.sql; do "${PSQL[@]}" -f "$f"; done
"${PSQL[@]}" -f "$HERE/market_test.sql"

# One seller sending many listings at once still stops at max_listings (5): the
# functions lock per player before counting.
C=00000000-0000-0000-0000-00000000000c
AS_C="set request.jwt.claim.sub = '$C'; set role authenticated;"
"${PSQL[@]}" -c "insert into auth.users values ('$C');" -c "$AS_C select public.market_join('Yarışçı Can');" >/dev/null
for i in $(seq 1 20); do
  "${PSQL[@]}" -c "$AS_C select public.market_create_listing('{\"uid\": \"c$i\", \"base\": \"copper_ring\",
    \"rarity\": \"common\", \"level\": 1, \"upgrade\": 0, \"affixes\": []}', 50);" >/dev/null &
done
wait
ACTIVE=$("${PSQL[@]}" -t -A -c "select count(*) from public.listings where seller = '$C' and status = 'active';")
if [ "$ACTIVE" != "5" ]; then echo "CHECK FAILED: $ACTIVE active listings after parallel creates"; exit 1; fi
echo "parallel listing limit ok"
