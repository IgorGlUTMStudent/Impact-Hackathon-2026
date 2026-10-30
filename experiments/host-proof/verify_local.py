"""Local HTTP-only smoke; creates and deletes a synthetic temporary SQLite DB."""
import http.cookiejar
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="host-proof-") as temp:
    env = os.environ.copy()
    env.update(DJANGO_SECRET_KEY=secrets.token_urlsafe(32), PROOF_USERNAME="synthetic",
               PROOF_PASSWORD=secrets.token_urlsafe(24), DATABASE_URL="sqlite:///" + (Path(temp) / "test.sqlite3").as_posix(),
               ALLOWED_HOSTS="127.0.0.1,localhost")
    env.pop("RENDER", None)
    env.pop("RENDER_EXTERNAL_HOSTNAME", None)
    env.pop("RENDER_EXTERNAL_URL", None)
    for args in (["migrate", "--noinput"], ["init-value"]):
        subprocess.run([sys.executable, "smoke.py", *args], cwd=BASE, env=env, check=True, stdout=subprocess.DEVNULL)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    def start():
        p = subprocess.Popen([sys.executable, "smoke.py", "runserver", f"127.0.0.1:{port}", "--noreload"], cwd=BASE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if p.poll() is not None:
                raise RuntimeError("server exited")
            try:
                if urllib.request.urlopen(url + "/health/", timeout=1).read() == b"ok":
                    return p
            except OSError:
                time.sleep(.1)
        p.terminate()
        p.wait()
        raise RuntimeError("server did not start")
    def get(opener, path):
        return opener.open(url + path).read().decode()
    def post(opener, path, data):
        return opener.open(url + path, urllib.parse.urlencode(data).encode()).read().decode()
    def token(html):
        return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)', html).group(1)
    def auth():
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        csrf = token(get(opener, "/login/"))
        post(opener, "/login/", {"username": env["PROOF_USERNAME"], "password": env["PROOF_PASSWORD"], "csrfmiddlewaretoken": csrf})
        return opener
    p = start()
    try:
        a = auth()
        assert "Value: 17" in post(a, "/value/", {"value": 17, "csrfmiddlewaretoken": token(get(a, "/value/"))})
        b = auth()
        assert "Value: 17" in get(b, "/value/")
        assert "Value: 35" in post(b, "/value/", {"value": 35, "csrfmiddlewaretoken": token(get(b, "/value/"))})
    finally:
        p.terminate()
        p.wait()
    p = start()
    try:
        assert "Value: 35" in get(auth(), "/value/")
    finally:
        p.terminate()
        p.wait()
    print("PASS: localhost HTTP, two independent sessions, 17 -> 35, server restart -> 35")
