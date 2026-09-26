"""A tiny stand-in for the Supabase HTTP API, backed by a local PostgreSQL, so the
game's SupabaseMarket client can be tested end to end without a real project.

Handles only what the client uses:
  POST /auth/v1/signup                         -> new anonymous user + tokens
  POST /auth/v1/token?grant_type=refresh_token -> new access token
  POST /rest/v1/rpc/<function>                 -> runs public.<function>(named args) as that user

    python3 mock_gateway.py <port> <psql connection args...>
"""
import json
import subprocess
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PSQL = ["psql", "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1"] + sys.argv[2:]
TOKENS = {}  # access token -> user id
EXPIRED = set()


def sql_literal(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (dict, list)):
        return "'" + json.dumps(v).replace("'", "''") + "'::jsonb"
    return "'" + str(v).replace("'", "''") + "'"


def run_sql(sql):
    out = subprocess.run(PSQL + ["-c", sql], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr)
    return out.stdout.strip()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _session(self, user_id):
        token = "tok-" + uuid.uuid4().hex
        TOKENS[token] = user_id
        return {"access_token": token, "refresh_token": "ref-" + user_id, "user": {"id": user_id}}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        if not self.headers.get("apikey"):
            return self._send(401, {"message": "no apikey"})
        if self.path.startswith("/auth/v1/signup"):
            user_id = str(uuid.uuid4())
            run_sql(f"insert into auth.users (id) values ('{user_id}')")
            return self._send(200, self._session(user_id))
        if self.path.startswith("/auth/v1/token"):
            ref = body.get("refresh_token", "")
            if not ref.startswith("ref-"):
                return self._send(400, {"error": "invalid_grant"})
            return self._send(200, self._session(ref[4:]))
        if self.path.startswith("/rest/v1/rpc/"):
            fn = self.path[len("/rest/v1/rpc/"):]
            token = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if token in EXPIRED or token not in TOKENS:
                return self._send(401, {"message": "JWT expired"})
            if not fn.replace("_", "").isalnum():
                return self._send(404, {})
            args = ", ".join(f"{k} => {sql_literal(v)}" for k, v in body.items())
            sql = (f"set request.jwt.claim.sub = '{TOKENS[token]}'; set role authenticated; "
                   f"select public.{fn}({args});")
            try:
                return self._send(200, json.loads(run_sql(sql).splitlines()[-1]))
            except Exception as e:  # noqa: BLE001
                return self._send(400, {"message": str(e)})
        if self.path == "/_test/expire_tokens":
            EXPIRED.update(TOKENS.keys())
            return self._send(200, {"ok": True})
        self._send(404, {})


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
