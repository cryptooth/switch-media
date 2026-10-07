#!/usr/bin/env python3
"""
Switch Media — yerel arayüz
  python3 server.py            -> http://localhost:8765 açılır
  python3 server.py --port 9000 --out ~/SwitchMedia

Durum dosyaları (çıktı klasöründe):
  downloaded.json  -> indirilen oyunlar ve hangi dosyaların olduğu
  settings.json    -> arayüzdeki ayarlar (yanında, script klasöründe)
"""
import argparse, gzip, hashlib, json, os, queue, threading, time, types, webbrowser
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import switch_media as sm

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(HERE, "settings.json")
THUMB_DIR = os.path.join(HERE, ".cache", "thumbs")
THUMB_ERR = []
DEFAULT_SETTINGS = {"out": os.path.join(HERE, "media"), "regions": list(sm.DEFAULT_REGIONS),
                    "music": "khinsider", "screenshots": 0, "steamgriddb_key": "", "workers": 3}

lock = threading.Lock()
state = {"catalog": [], "by_id": {}, "catalog_json": b"[]", "downloaded": {},
         "job": {"running": False, "total": 0, "done": 0, "current": [], "log": [], "cancel": False}}
jobq = queue.Queue()

# --------------------------------------------------------------------------- ayarlar / durum

def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    s.pop("region", None); s.pop("lang", None)  # eski tek-bölge ayarı
    if not s.get("regions"):
        s["regions"] = list(sm.DEFAULT_REGIONS)
    return s

def save_settings(s):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)

def dl_path(s):
    return os.path.join(os.path.expanduser(s["out"]), "downloaded.json")

def load_downloaded(s):
    try:
        with open(dl_path(s), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_downloaded(s):
    os.makedirs(os.path.expanduser(s["out"]), exist_ok=True)
    tmp = dl_path(s) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state["downloaded"], f, ensure_ascii=False, indent=1)
    os.replace(tmp, dl_path(s))

def scan_folder(folder):
    files = os.listdir(folder) if os.path.isdir(folder) else []
    has = lambda p: any(x.startswith(p) for x in files)
    return {"icon": has("icon."), "banner": has("banner."), "hero": has("hero."), "logo": has("logo."),
            "music": "theme.mp3" in files, "screenshots": sum(x.startswith("screenshot_") for x in files)}

def reconcile(s):
    """downloaded.json'u diskle eşitle: silinmiş klasörleri at, elle eklenmişleri bul."""
    out = os.path.expanduser(s["out"])
    dl = load_downloaded(s)
    if os.path.isdir(out):
        for d in os.listdir(out):
            if d.endswith("]") and "[" in d:
                tid = d[d.rfind("[") + 1:-1].upper()
                entry = dl.get(tid, {"name": d[:d.rfind("[")].strip(), "date": ""})
                entry.update(scan_folder(os.path.join(out, d)), folder=d)
                dl[tid] = entry
    for tid in list(dl):
        if not os.path.isdir(os.path.join(out, dl[tid].get("folder", ""))):
            del dl[tid]
    state["downloaded"] = dl
    save_downloaded(s)

def load_catalog(s):
    regions = s.get("regions") or list(sm.DEFAULT_REGIONS)
    cat = sm.load_catalog(regions, os.path.join(HERE, ".cache"))
    slim = []
    for g in cat:
        slim.append({"id": g["id"].upper(), "name": g["name"], "pub": g.get("publisher") or "",
                     "date": g.get("releaseDate") or 0, "icon": g.get("iconUrl") or "",
                     "banner": g.get("bannerUrl") or "", "cat": g.get("category") or [],
                     "reg": g.get("regions", []), "alt": g.get("alt", [])})
    slim.sort(key=lambda x: x["name"].lower())
    state["catalog"] = cat
    state["by_id"] = {g["id"].upper(): g for g in cat}
    body = json.dumps({"regions": [r.split(".")[0] for r in regions],
                       "labels": {k.split(".")[0]: v for k, v in sm.REGIONS.items()},
                       "games": slim}, ensure_ascii=False).encode("utf-8")
    state["catalog_json"] = body
    state["catalog_gz"] = gzip.compress(body, 6)

# --------------------------------------------------------------------------- indirme işçisi

def joblog(msg):
    j = state["job"]
    j["log"].append(f'{datetime.now().strftime("%H:%M:%S")}  {msg}')
    j["log"] = j["log"][-300:]

def worker():
    from concurrent.futures import ThreadPoolExecutor, as_completed
    while True:
        ids, s = jobq.get()
        j = state["job"]
        with lock:
            j.update(running=True, total=len(ids), done=0, current=[], cancel=False)
        a = types.SimpleNamespace(out=os.path.expanduser(s["out"]), screenshots=int(s["screenshots"]),
                                  steamgriddb_key=s.get("steamgriddb_key") or None, music=s["music"])
        os.makedirs(a.out, exist_ok=True)
        joblog(f"{len(ids)} game(s) queued")

        def one(tid):
            g = state["by_id"].get(tid)
            if not g or j["cancel"]:
                return tid, None
            with lock:
                j["current"].append(g["name"])
            try:
                return tid, sm.process(g, a)
            finally:
                with lock:
                    j["current"].remove(g["name"])

        workers = max(1, min(int(s.get("workers", 3)), 8))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for fu in as_completed([ex.submit(one, t) for t in ids]):
                try:
                    tid, row = fu.result()
                except Exception as e:
                    joblog(f"error: {e}")
                    tid, row = None, None
                with lock:
                    j["done"] += 1
                    if row:
                        folder = os.path.join(a.out, row["folder"])
                        entry = {"name": row["name"], "folder": row["folder"],
                                 "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                 "music_source": row.get("music", "")}
                        entry.update(scan_folder(folder))
                        state["downloaded"][tid] = entry
                        save_downloaded(s)
                        extra = f' — music: {row["music"]}' if s["music"] != "none" else ""
                        joblog(f'✓ {row["name"]}{extra}')
        joblog("Cancelled" if j["cancel"] else "Finished")
        with lock:
            j.update(running=False, current=[])

# --------------------------------------------------------------------------- HTTP

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        p = urlparse(self.path).path
        s = load_settings()
        if p in ("/", "/index.html"):
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self.send(200, f.read(), "text/html; charset=utf-8")
        if p == "/thumb":
            return self.thumb()
        if p == "/api/catalog":
            if "gzip" in (self.headers.get("Accept-Encoding") or ""):
                body = state["catalog_gz"]
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            return self.send(200, state["catalog_json"])
        if p == "/api/downloaded":
            return self.send(200, state["downloaded"])
        if p == "/api/settings":
            return self.send(200, s | {"all_regions": sm.REGIONS})
        if p == "/api/status":
            j = state["job"]
            with lock:
                return self.send(200, {k: j[k] for k in ("running", "total", "done", "current")} | {"log": j["log"][-60:]})
        if p.startswith("/media/"):
            # indirilen dosyaları önizleme için sun
            rel = p[len("/media/"):]
            from urllib.parse import unquote
            base = os.path.realpath(os.path.expanduser(s["out"]))
            full = os.path.realpath(os.path.join(base, unquote(rel)))
            if full.startswith(base + os.sep) and os.path.isfile(full):
                ext = os.path.splitext(full)[1].lower()
                ct = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
                      ".mp3": "audio/mpeg", ".json": "application/json"}.get(ext, "application/octet-stream")
                with open(full, "rb") as f:
                    return self.send(200, f.read(), ct)
            return self.send(404, {"error": "not found"})
        self.send(404, {"error": "not found"})

    def thumb(self):
        """Nintendo CDN görsellerini sunucu üzerinden çek ve önbelleğe al
        (CDN, tarayıcıdan localhost referer'ı ile gelen istekleri reddediyor)."""
        from urllib.parse import parse_qs
        u = (parse_qs(urlparse(self.path).query).get("u") or [""])[0]
        host = urlparse(u).hostname or ""
        if not (host.endswith("nintendo.net") or host.endswith("nintendo.com")):
            return self.send(400, {"error": "host not allowed"})
        os.makedirs(THUMB_DIR, exist_ok=True)
        path = os.path.join(THUMB_DIR, hashlib.sha1(u.encode()).hexdigest() + ".jpg")
        if not os.path.exists(path):
            try:
                data = sm.http_get(u, timeout=20, retries=2)
            except Exception as e:
                if not THUMB_ERR:
                    THUMB_ERR.append(1)
                    print(f"Görsel indirilemedi ({e}). Ağ/erişim sorunu olabilir: {u}")
                return self.send(502, {"error": str(e)})
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/download":
            ids = [i.upper() for i in self.body().get("ids", []) if i.upper() in state["by_id"]]
            if not ids:
                return self.send(400, {"error": "nothing selected"})
            if state["job"]["running"]:
                return self.send(409, {"error": "A download is already running"})
            jobq.put((ids, load_settings()))
            state["job"]["running"] = True
            return self.send(200, {"queued": len(ids)})
        if p == "/api/cancel":
            state["job"]["cancel"] = True
            return self.send(200, {"ok": True})
        if p == "/api/settings":
            s = load_settings()
            new = self.body()
            old_out, old_regions = s["out"], s.get("regions")
            for k in DEFAULT_SETTINGS:
                if k in new:
                    s[k] = new[k]
            s["regions"] = [r for r in s.get("regions", []) if r in sm.REGIONS] or list(sm.DEFAULT_REGIONS)
            save_settings(s)
            if s["out"] != old_out:
                reconcile(s)
            if s.get("regions") != old_regions:
                load_catalog(s)  # yeni bölgeler ilk seferde indirilir, biraz sürebilir
            return self.send(200, s | {"all_regions": sm.REGIONS})
        if p == "/api/rescan":
            reconcile(load_settings())
            return self.send(200, state["downloaded"])
        self.send(404, {"error": "not found"})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--out", help="Çıktı klasörü (ayarlara kaydedilir)")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    s = load_settings()
    if args.out:
        s["out"] = os.path.abspath(os.path.expanduser(args.out))
    save_settings(s)
    load_catalog(s)
    reconcile(s)
    threading.Thread(target=worker, daemon=True).start()
    url = f"http://localhost:{args.port}"
    print(f"Arayüz: {url}   (kapatmak için Ctrl+C)")
    print(f"Çıktı klasörü: {s['out']}  —  {len(state['downloaded'])} oyun indirilmiş görünüyor")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()
    except KeyboardInterrupt:
        print("\nKapatıldı.")

if __name__ == "__main__":
    main()
