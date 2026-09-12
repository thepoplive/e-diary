import io, os, re, urllib.request, http.cookiejar, urllib.parse

BASE = "http://127.0.0.1:8077"
ROOT = os.path.dirname(__file__)


def admin_password(default="4UuDuG1KI38"):
    """Detect the admin password printed in server_err.log at startup."""
    try:
        raw = io.open(os.path.join(ROOT, "server_err.log"), "rb").read()
    except OSError:
        return default
    text = raw.decode("utf-8", errors="replace")
    cands = [
        x
        for x in re.findall(r"[A-Za-z0-9]{10,}", text)
        if any(c.isdigit() for c in x) and "sqlite" not in x
    ]
    return cands[-1] if cands else default


def make_opener():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def GET(op, path, base=BASE):
    r = op.open(base + path)
    return r.status, r.geturl(), r.read().decode("utf-8", errors="replace")


def POST(op, path, data, base=BASE):
    body = urllib.parse.urlencode(data, doseq=True).encode()
    req = urllib.request.Request(base + path, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        r = op.open(req)
        return r.status, r.geturl(), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("location", ""), e.read().decode("utf-8", errors="replace")


def login(login, password, base=BASE):
    op = make_opener()
    POST(op, "/login", {"login": login, "password": password}, base=base)
    return op