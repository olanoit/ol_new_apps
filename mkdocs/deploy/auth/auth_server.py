#!/usr/bin/env python3
"""Acceso a la documentación (docs.altalatam.com) con página de inicio de sesión.

nginx protege el sitio con ``auth_request``: cada petición consulta ``/auth``
y, si la sesión no es válida, redirige a ``/_login/``. Solo biblioteca
estándar (sin dependencias que mantener).

- Usuarios en ``users.json``: ``{"usuario": "pbkdf2_sha256$iter$sal$hash"}``.
- Sesión en una cookie firmada (HMAC-SHA256 con ``secret``): usuario,
  vencimiento y una huella del hash de la contraseña, para que cambiar la
  contraseña cierre las sesiones abiertas.
- Límite de intentos: lo pone nginx (``limit_req`` en ``/_login/``).

Uso:
    python3 auth_server.py serve                 # servicio (puerto 8000)
    python3 auth_server.py passwd <usuario>      # crea o cambia un usuario
    python3 auth_server.py deluser <usuario>
"""
import base64
import getpass
import hashlib
import hmac
import html
import json
import os
import secrets
import sys
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DATA = Path(os.environ.get('DOCS_AUTH_DATA', Path(__file__).resolve().parent / 'data'))
USERS = DATA / 'users.json'
SECRET = DATA / 'secret'
LOGO = Path(os.environ.get('DOCS_LOGO', '/www/latest/assets/logo.png'))
COOKIE = 'ol_docs_session'
SESSION_HOURS = 12
REMEMBER_DAYS = 30
ITERATIONS = 600_000
LOGIN = '/_login/'


# ---------------------------------------------------------------- contraseñas

def hash_password(password, salt=None, iterations=ITERATIONS):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    return 'pbkdf2_sha256$%d$%s$%s' % (
        iterations, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def check_password(password, encoded):
    try:
        _algo, iterations, salt, digest = encoded.split('$')
        expected = base64.b64decode(digest)
        got = hashlib.pbkdf2_hmac('sha256', password.encode(), base64.b64decode(salt),
                                  int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, expected)


# Hash de referencia para gastar el mismo tiempo con usuarios inexistentes.
_DUMMY = hash_password(secrets.token_urlsafe(12))


def load_users():
    try:
        return json.loads(USERS.read_text())
    except FileNotFoundError:
        return {}


def save_users(users):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = USERS.with_suffix('.tmp')
    tmp.write_text(json.dumps(users, indent=1, sort_keys=True))
    os.chmod(tmp, 0o600)
    tmp.replace(USERS)


def secret_key():
    if not SECRET.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        SECRET.write_bytes(secrets.token_bytes(32))
        os.chmod(SECRET, 0o600)
    return SECRET.read_bytes()


# -------------------------------------------------------------------- sesión

def _fingerprint(encoded):
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


def _sign(payload):
    return hmac.new(secret_key(), payload.encode(), hashlib.sha256).hexdigest()


def make_session(user, encoded, seconds):
    payload = '%s|%d|%s' % (user, int(time.time()) + seconds, _fingerprint(encoded))
    token = '%s|%s' % (payload, _sign(payload))
    return base64.urlsafe_b64encode(token.encode()).decode()


def session_user(value):
    """Usuario de una cookie de sesión válida, o None."""
    try:
        token = base64.urlsafe_b64decode(value.encode()).decode()
        user, expires, fingerprint, signature = token.split('|')
    except (ValueError, UnicodeDecodeError):
        return None
    payload = '%s|%s|%s' % (user, expires, fingerprint)
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    if int(expires) < time.time():
        return None
    encoded = load_users().get(user)
    if not encoded or not hmac.compare_digest(fingerprint, _fingerprint(encoded)):
        return None
    return user


def safe_next(value):
    """Solo rutas del propio sitio (evita redirecciones abiertas)."""
    if not value or not value.startswith('/') or value.startswith('//') or '\\' in value:
        return '/latest/'
    if value.startswith(LOGIN):
        return '/latest/'
    return value


# ------------------------------------------------------------------- página

PAGE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Documentación · Suite OL para Odoo</title>
<link rel="icon" href="/_login/logo.png">
<style>
:root {
  --brand: #b45309; --brand-dark: #92400e; --accent: #0f766e;
  --bg: #f6f3ee; --card: #ffffff; --text: #1f2933; --muted: #5b6570;
  --border: #e3ddd3; --input: #ffffff; --error-bg: #fdecea; --error: #b42318;
  --shadow: 0 18px 45px rgba(31, 41, 51, 0.12);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14181d; --card: #1e242b; --text: #e6e9ec; --muted: #a8b3bd;
    --border: #323a44; --input: #161b21; --error-bg: #3a1d1b; --error: #f4a29a;
    --accent: #2dd4bf; --shadow: 0 18px 45px rgba(0, 0, 0, 0.45);
  }
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body {
  font-family: Inter, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 15px; line-height: 1.5; color: var(--text); background: var(--bg);
  display: flex; align-items: center; justify-content: center; padding: 24px 16px;
}
body::before {
  content: ""; position: fixed; inset: 0 0 auto 0; height: 38vh; z-index: -1;
  background: linear-gradient(135deg, var(--brand) 0%, var(--brand-dark) 100%);
}
main { width: 100%; max-width: 400px; }
.card {
  background: var(--card); border: 1px solid var(--border); border-radius: 14px;
  box-shadow: var(--shadow); padding: 32px 30px 26px;
}
.brand { display: flex; align-items: center; gap: 12px; margin-bottom: 22px; }
.brand img { width: 44px; height: 44px; border-radius: 10px; }
.brand strong { display: block; font-size: 17px; }
.brand span { display: block; font-size: 13px; color: var(--muted); }
h1 { font-size: 21px; margin: 0 0 4px; letter-spacing: -0.01em; }
p.lead { margin: 0 0 22px; color: var(--muted); font-size: 14px; }
label { display: block; font-size: 13px; font-weight: 600; margin: 0 0 6px; }
input[type=text], input[type=password] {
  width: 100%; padding: 11px 12px; margin-bottom: 16px; font: inherit; color: var(--text);
  background: var(--input); border: 1px solid var(--border); border-radius: 8px;
}
input:focus { outline: none; border-color: var(--accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 25%, transparent); }
.row { display: flex; align-items: center; justify-content: space-between; margin: 2px 0 20px; }
.check { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 400; margin: 0; }
.check input { width: 16px; height: 16px; accent-color: var(--brand); }
button {
  width: 100%; padding: 12px; font: inherit; font-weight: 600; color: #fff; cursor: pointer;
  background: var(--brand); border: 0; border-radius: 8px; transition: background .15s;
}
button:hover { background: var(--brand-dark); }
button:focus-visible { outline: 3px solid color-mix(in srgb, var(--brand) 40%, transparent); outline-offset: 2px; }
.error {
  background: var(--error-bg); color: var(--error); border-radius: 8px;
  padding: 10px 12px; font-size: 14px; margin-bottom: 18px;
}
.note { margin: 16px 0 0; font-size: 13px; color: var(--muted); text-align: center; }
footer { margin-top: 18px; text-align: center; font-size: 12px; color: var(--muted); }
footer a { color: inherit; }
</style>
</head>
<body>
<main>
  <div class="card">
    <div class="brand">
      <img src="/_login/logo.png" alt="">
      <div><strong>Suite OL para Odoo</strong><span>Documentación funcional y técnica</span></div>
    </div>
    <h1>Iniciar sesión</h1>
    <p class="lead">Guías, fichas y novedades de todos los módulos de la suite.</p>
    {{error}}
    <form method="post" action="/_login/" autocomplete="on">
      <input type="hidden" name="next" value="{{next}}">
      <label for="user">Usuario</label>
      <input id="user" name="user" type="text" autocomplete="username" autocapitalize="none"
             spellcheck="false" required{{focus_user}} value="{{user}}">
      <label for="password">Contraseña</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required{{focus_password}}>
      <div class="row">
        <label class="check"><input type="checkbox" name="remember" value="1"{{remember}}> Mantener la sesión 30 días</label>
      </div>
      <button type="submit">Entrar</button>
    </form>
    <p class="note">¿Sin acceso? Pídelo al equipo de ALTA Latam.</p>
  </div>
  <footer>© ALTA Latam · <a href="https://www.altabpo.com" rel="noopener">altabpo.com</a></footer>
</main>
</body>
</html>
"""


def render(next_url, error='', user='', remember=False):
    values = {
        'error': '<div class="error" role="alert">%s</div>' % html.escape(error) if error else '',
        'next': html.escape(next_url, quote=True),
        'user': html.escape(user, quote=True),
        'remember': ' checked' if remember else '',
        # Tras un error con el usuario escrito, el cursor va a la contraseña.
        'focus_user': '' if user else ' autofocus',
        'focus_password': ' autofocus' if user else '',
    }
    page = PAGE
    for key, value in values.items():
        page = page.replace('{{%s}}' % key, value)
    return page


# ------------------------------------------------------------------ servicio

class Handler(BaseHTTPRequestHandler):
    server_version = 'ol-docs-auth'
    sys_version = ''

    def log_message(self, fmt, *args):
        # Una línea por intento de acceso; las comprobaciones de /auth no.
        if not self.path.startswith('/auth'):
            sys.stderr.write('%s %s\n' % (self.headers.get('X-Real-IP', '-'), fmt % args))

    def _cookie(self):
        cookie = SimpleCookie(self.headers.get('Cookie', ''))
        return cookie[COOKIE].value if COOKIE in cookie else ''

    def _send(self, status, body=b'', headers=()):
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        if body:
            self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if body and self.command != 'HEAD':
            self.wfile.write(body)

    def _page(self, body, status=200):
        self._send(status, body.encode(), [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'),
            ('X-Frame-Options', 'DENY'),
            ('Content-Security-Policy',
             "default-src 'none'; style-src 'unsafe-inline'; img-src 'self'; "
             "form-action 'self'; frame-ancestors 'none'; base-uri 'none'"),
        ])

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/auth':
            user = session_user(self._cookie())
            return self._send(200 if user else 401, headers=[('X-Docs-User', user or '')])
        if url.path == LOGIN + 'logo.png':
            try:
                data = LOGO.read_bytes()
            except OSError:
                return self._send(404)
            return self._send(200, data, [('Content-Type', 'image/png'),
                                          ('Cache-Control', 'public, max-age=86400')])
        if url.path == LOGIN + 'logout':
            return self._send(302, headers=[
                ('Location', LOGIN),
                ('Set-Cookie', '%s=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Lax' % COOKIE)])
        if url.path == LOGIN:
            next_url = safe_next(parse_qs(url.query).get('next', [''])[0])
            if session_user(self._cookie()):
                return self._send(302, headers=[('Location', next_url)])
            return self._page(render(next_url))
        return self._send(404)

    do_HEAD = do_GET

    def do_POST(self):
        if urlsplit(self.path).path != LOGIN:
            return self._send(404)
        length = min(int(self.headers.get('Content-Length') or 0), 8192)
        form = parse_qs(self.rfile.read(length).decode('utf-8', 'replace'))
        user = form.get('user', [''])[0].strip()
        password = form.get('password', [''])[0]
        remember = form.get('remember', [''])[0] == '1'
        next_url = safe_next(form.get('next', [''])[0])
        encoded = load_users().get(user)
        ok = check_password(password, encoded or _DUMMY) and bool(encoded)
        if not ok:
            self.log_message('acceso rechazado para %r', user)
            return self._page(render(next_url, 'Usuario o contraseña incorrectos.', user, remember), 401)
        seconds = REMEMBER_DAYS * 86400 if remember else SESSION_HOURS * 3600
        cookie = '%s=%s; Path=/; Secure; HttpOnly; SameSite=Lax' % (
            COOKIE, make_session(user, encoded, seconds))
        if remember:
            cookie += '; Max-Age=%d' % seconds
        self.log_message('acceso de %r', user)
        return self._send(303, headers=[('Location', next_url), ('Set-Cookie', cookie)])


def main(argv):
    command = argv[1] if len(argv) > 1 else 'serve'
    if command == 'serve':
        secret_key()
        ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', 8000))), Handler).serve_forever()
    elif command == 'passwd' and len(argv) == 3:
        password = os.environ.get('DOCS_PASSWORD') or getpass.getpass('Contraseña para %s: ' % argv[2])
        if len(password) < 10:
            sys.exit('La contraseña debe tener al menos 10 caracteres.')
        users = load_users()
        users[argv[2]] = hash_password(password)
        save_users(users)
        print('Usuario %s guardado (sus sesiones abiertas se cierran).' % argv[2])
    elif command == 'deluser' and len(argv) == 3:
        users = load_users()
        users.pop(argv[2], None)
        save_users(users)
        print('Usuario %s eliminado.' % argv[2])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main(sys.argv)
