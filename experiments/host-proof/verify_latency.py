"""Measure a synthetic save of the existing 35; never print credentials or cookies."""
import argparse
import getpass
import http.cookiejar
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PUBLIC = "https://gustul-host-proof-h-20261030.onrender.com"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=PUBLIC, help="Test service, or loopback HTTP for local verification")
    args = parser.parse_args()
    parsed = urllib.parse.urlsplit(args.base)
    if args.base != PUBLIC and not (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost") and not parsed.path and not parsed.query and not parsed.fragment and not parsed.username):
        parser.error("Only the isolated public probe or a loopback HTTP address is allowed")
    base = args.base.rstrip("/")
    user = input("Test username: ")
    password = getpass.getpass("Test password: ")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())
    def request(path, data=None):
        body = None if data is None else urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(base + path, data=body, headers={"Referer": base + path})
        try:
            response = opener.open(req, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.code, response.headers.get("Location", ""), response.read().decode("utf-8", "replace")
    def token(body):
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', body)
        if not match:
            raise ValueError("CSRF form missing")
        return match.group(1)
    status, _, body = request("/login/")
    if status != 200:
        raise ValueError(f"login GET status {status}")
    status, location, _ = request("/login/", {"username": user, "password": password, "csrfmiddlewaretoken": token(body)})
    if status != 303 or location != "/value/":
        raise ValueError(f"login POST status {status}, unexpected redirect")
    status, _, body = request("/value/")
    if status != 200 or not re.search(r"Value:\s*35\b", body):
        raise ValueError("Current value is not 35; no write attempted")
    csrf = token(body)
    print("Current value is 35. The next request writes 35 again; use only while no other tester is writing.")
    if input("Type YES to perform one synthetic write: ") != "YES":
        print("No write performed")
        return
    start = time.perf_counter()
    status, location, _ = request("/value/", {"value": "35", "csrfmiddlewaretoken": csrf})
    post_ms = (time.perf_counter() - start) * 1000
    if status != 303 or location != "/value/":
        raise ValueError(f"save POST status {status}, unexpected redirect")
    status, _, body = request("/value/")
    total_ms = (time.perf_counter() - start) * 1000
    if status != 200 or not re.search(r"Value:\s*35\b", body):
        raise ValueError(f"readback status {status}, value not confirmed")
    print(f"PASS: save POST=303 ({post_ms:.1f} ms), redirect GET=200, value=35, total={total_ms:.1f} ms")

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Verification failed: {error.__class__.__name__}; check service and test credentials", file=sys.stderr)
        sys.exit(1)
