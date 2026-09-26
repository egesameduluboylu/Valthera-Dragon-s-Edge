#!/bin/bash
# Runs the game's SupabaseMarket client against mock_gateway.py + a throwaway local
# PostgreSQL with the real migrations. Usage: run_client_check.sh <godot binary>
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
GODOT="$1"
PGBIN="${PGBIN:-$(ls -d /usr/lib/postgresql/*/bin | tail -1)}"
DIR="$(mktemp -d)"
cleanup() { kill "${GW:-0}" 2>/dev/null || true; "$PGBIN/pg_ctl" -D "$DIR/data" stop -m immediate >/dev/null 2>&1 || true; rm -rf "$DIR"; }
trap cleanup EXIT
if [ "$(id -u)" = "0" ]; then RUN="runuser -u postgres --"; chown -R postgres "$DIR"; else RUN=""; fi
$RUN "$PGBIN/initdb" -D "$DIR/data" -U postgres >/dev/null
$RUN "$PGBIN/pg_ctl" -D "$DIR/data" -o "-k $DIR -c listen_addresses=''" -w start >/dev/null
CONN=(-h "$DIR" -U postgres -d postgres)
psql "${CONN[@]}" -q -v ON_ERROR_STOP=1 -f "$HERE/auth_stub.sql"
for f in "$HERE"/../supabase/migrations/*.sql; do psql "${CONN[@]}" -q -v ON_ERROR_STOP=1 -f "$f"; done
psql "${CONN[@]}" -q -c "grant all on all tables in schema public to anon, authenticated;"
PORT=54${RANDOM:0:3}
python3 "$HERE/mock_gateway.py" "$PORT" "${CONN[@]}" &
GW=$!
sleep 1
cd "$HERE/../.."
MARKET_URL="http://127.0.0.1:$PORT" "$GODOT" --headless -s res://tests/online_client_check.gd
