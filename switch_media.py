#!/usr/bin/env python3
"""
Nintendo Switch oyun medyası toplu indirici
--------------------------------------------
Her oyun için ikon, banner (arka plan), ekran görüntüleri ve tema müziği indirir.

Kaynaklar:
  - titledb (github.com/blawar/titledb)  -> oyun listesi, ikon, banner, ekran görüntüleri
  - SteamGridDB (opsiyonel, API anahtarı) -> hero (geniş arka plan) ve logo
  - KHInsider                            -> tema müziği (soundtrack'in ilgili parçası)
  - YouTube (opsiyonel, yt-dlp gerekir)  -> KHInsider'da bulunamazsa yedek

Sadece Python 3 standart kütüphanesi kullanır. YouTube yedeği için:  brew install yt-dlp ffmpeg

Örnekler:
  python3 switch_media.py --list oyunlarim.txt
  python3 switch_media.py --list oyunlarim.txt --steamgriddb-key ANAHTAR --music both
  python3 switch_media.py --all --no-music --workers 16          # tüm katalog (~19 bin oyun, ~8 GB)
  python3 switch_media.py --search "zelda"                       # katalogda isim ara
  python3 switch_media.py --list oyunlarim.txt --regions US.en,JP.ja   # sadece ABD + Japonya

oyunlarim.txt: her satıra bir oyun adı veya Title ID (0100...). # ile başlayan satırlar yok sayılır.
"""
import argparse, csv, difflib, html, json, os, re, shutil, subprocess, sys, time, unicodedata
import urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
TITLEDB_URL = "https://raw.githubusercontent.com/blawar/titledb/master/{region}.{lang}.json"
KHI = "https://downloads.khinsider.com"
SGDB = "https://www.steamgriddb.com/api/v2"

# --------------------------------------------------------------------------- yardımcılar

def log(msg):
    print(msg, flush=True)

def http_get(url, headers=None, timeout=30, retries=3):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (404, 403, 401):
                raise
            last = e
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise last

def download(url, dest, headers=None):
    """Dosyayı indir; zaten varsa atla. True = yeni indirildi."""
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return False
    data = http_get(url, headers=headers, timeout=60)
    tmp = dest + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, dest)
    return True

def norm(s):
    s = re.sub(r"[™®©]", "", s or "")  # NFKD ™'yi "TM"ye çevirir, önce sil
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ")
    s = re.sub(r"[™®©]", "", s)
    s = re.sub(r"[\W_]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def safe_name(s):
    s = re.sub(r"[™®©]", "", s or "untitled")
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".")
    return s[:120] or "untitled"

def ext_of(url, default=".jpg"):
    e = os.path.splitext(urllib.parse.urlparse(url).path)[1].lower()
    return e if e in (".jpg", ".jpeg", ".png", ".webp", ".gif") else default

# --------------------------------------------------------------------------- titledb

REGIONS = {  # titledb dosyası -> etiket
    "US.en": "USA", "GB.en": "Europe", "JP.ja": "Japan", "KR.ko": "Korea",
    "HK.zh": "Hong Kong", "AU.en": "Australia", "DE.de": "Germany",
}
DEFAULT_REGIONS = ["US.en", "GB.en", "JP.ja", "KR.ko", "HK.zh"]
SLIM_FIELDS = ("id", "name", "publisher", "developer", "releaseDate", "category", "iconUrl", "bannerUrl",
               "screenshots", "description", "intro", "numberOfPlayers", "nsuId")

def _region_slim(code, cache_dir, refresh=False):
    """Bir bölgenin titledb dosyasını indirip sadece ana oyunları ve gereken alanları saklar
    (~90 MB'lık ham dosya diske yazılmaz, bellekte de kısa süre kalır)."""
    os.makedirs(cache_dir, exist_ok=True)
    slim = os.path.join(cache_dir, f"{code}.slim.json")
    if not refresh and os.path.exists(slim) and time.time() - os.path.getmtime(slim) < 7 * 86400:
        with open(slim, encoding="utf-8") as f:
            return json.load(f)
    region, lang = code.split(".")
    log(f"titledb indiriliyor: {code} ({REGIONS.get(code, code)})...")
    raw = json.loads(http_get(TITLEDB_URL.format(region=region, lang=lang), timeout=600))
    games = {}
    for g in raw.values():
        tid = (g.get("id") or "").upper()
        if not tid or not tid.endswith("000") or g.get("isDemo") or not g.get("name"):
            continue  # sadece ana oyunlar (DLC/update/demo hariç)
        if re.search(r"\b(demo|kiosk)\b", g["name"], re.I):
            continue
        cur = games.get(tid)
        # aynı Title ID'ye birden çok kayıt olabilir: ikonu olanı, sonra kısa adı tercih et
        if cur is None or (bool(g.get("iconUrl")), -len(g["name"])) > (bool(cur.get("iconUrl")), -len(cur["name"])):
            games[tid] = {k: g.get(k) for k in SLIM_FIELDS} | {"id": tid}
    del raw
    with open(slim + ".tmp", "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False)
    os.replace(slim + ".tmp", slim)
    old = os.path.join(cache_dir, f"{code}.json")  # eski sürümün ham önbelleği
    if os.path.exists(old):
        os.remove(old)
    return games

def load_catalog(regions, cache_dir, refresh=False):
    """Bölgeleri sırayla birleştirir. İlk bölge ana bölgedir: aynı oyun birden çok bölgede varsa
    adı/görselleri oradan gelir; diğer bölgelerdeki adları 'alt' olarak aramaya eklenir."""
    games = {}
    for code in regions:
        try:
            part = _region_slim(code, cache_dir, refresh)
        except Exception as e:
            log(f"  {code} yüklenemedi: {e}")
            continue
        r = code.split(".")[0]
        added = 0
        for tid, g in part.items():
            cur = games.get(tid)
            if cur is None:
                g["regions"] = [r]
                games[tid] = g
                added += 1
            else:
                cur["regions"].append(r)
                if not cur.get("iconUrl") and g.get("iconUrl"):
                    cur["iconUrl"], cur["bannerUrl"] = g["iconUrl"], g.get("bannerUrl")
                if g["name"] != cur["name"] and len(cur.setdefault("alt", [])) < 4:
                    cur["alt"].append(g["name"])
        log(f"  {code}: {len(part)} oyun, {added} yeni")
    log(f"Katalogda {len(games)} oyun var.")
    return list(games.values())

def load_titledb(region, lang, cache_dir, refresh=False):
    return load_catalog([f"{region}.{lang}"], cache_dir, refresh)

def match_games(catalog, wanted):
    by_id = {g["id"].upper(): g for g in catalog}
    by_norm = {}
    for g in catalog:
        by_norm.setdefault(norm(g["name"]), g)
    names = list(by_norm.keys())
    found, missing = [], []
    for w in wanted:
        if re.fullmatch(r"0100[0-9A-Fa-f]{12}", w):
            g = by_id.get(w.upper())
            (found.append((w, g)) if g else missing.append(w))
            continue
        n = norm(w)
        g = by_norm.get(n)
        if not g:
            # içeren eşleşmeler: en kısa isim genelde ana oyundur
            cands = [k for k in names if n and (n in k)]
            if cands:
                g = by_norm[min(cands, key=len)]
        if not g:
            close = difflib.get_close_matches(n, names, n=1, cutoff=0.75)
            if close:
                g = by_norm[close[0]]
        (found.append((w, g)) if g else missing.append(w))
    return found, missing

# --------------------------------------------------------------------------- SteamGridDB

def sgdb_media(name, key, outdir):
    hdr = {"Authorization": f"Bearer {key}"}
    q = urllib.parse.quote(re.sub(r"[™®©]", "", name))
    res = json.loads(http_get(f"{SGDB}/search/autocomplete/{q}", headers=hdr))
    if not res.get("data"):
        return []
    gid = res["data"][0]["id"]
    got = []
    for kind, fname in (("heroes", "hero"), ("logos", "logo")):
        try:
            items = json.loads(http_get(f"{SGDB}/{kind}/game/{gid}", headers=hdr)).get("data") or []
        except Exception:
            continue
        if items:
            url = items[0]["url"]
            download(url, os.path.join(outdir, fname + ext_of(url, ".png")))
            got.append(fname)
    return got

# --------------------------------------------------------------------------- KHInsider

THEME_WORDS = ["main theme", "title theme", "title screen", "title", "theme", "opening", "main menu", "prologue", "intro"]

def khi_find_album(name):
    q = urllib.parse.quote_plus(re.sub(r"[™®©:]", " ", name))
    page = http_get(f"{KHI}/search?search={q}").decode("utf-8", "ignore")
    # Tek sonuçta doğrudan albüm sayfasına yönlenebilir
    if 'id="songlist"' in page:
        m = re.search(r'<link rel="canonical" href="([^"]+)"', page)
        return (m.group(1) if m else None), page
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', page, re.S)
    target = norm(name)
    best, best_score = None, 0.0
    for r in rows:
        # satırda ikon linki + başlık linki olabilir; metni olan linki al
        links = [(h, norm(html.unescape(re.sub("<[^>]+>", "", t))))
                 for h, t in re.findall(r'href="(/game-soundtracks/album/[^"]+)"[^>]*>(.*?)</a>', r, re.S)]
        links = [l for l in links if l[1]]
        if not links:
            continue
        href, title = links[0]
        score = difflib.SequenceMatcher(None, target, title).ratio()
        if "switch" in r.lower():
            score += 0.15
        if any(x in title for x in ("arrangement", "remix", "piano", "orchestra", "vinyl")):
            score -= 0.1
        if score > best_score:
            best, best_score = KHI + href, score
    if not best or best_score < 0.55:
        return None, None
    return best, http_get(best).decode("utf-8", "ignore")

def khi_theme(name, outdir):
    album_url, page = khi_find_album(name)
    if not album_url:
        return None
    songlist = re.search(r'id="songlist"(.*?)</table>', page, re.S)
    if not songlist:
        return None
    tracks, seen = [], set()
    for href, label in re.findall(r'<td class="clickable-row"[^>]*><a href="([^"]+)"[^>]*>(.*?)</a>', songlist.group(1), re.S):
        if href in seen:
            continue
        seen.add(href)
        label = html.unescape(re.sub("<[^>]+>", "", label)).strip()
        if re.fullmatch(r"[\d:.\s]+(MB|KB)?", label):  # süre/boyut sütunları
            continue
        tracks.append((href, label))
    if not tracks:
        return None
    pick = tracks[0]
    for w in THEME_WORDS:
        hit = [t for t in tracks if w in t[1].lower()]
        if hit:
            pick = hit[0]
            break
    track_page = http_get(urllib.parse.urljoin(KHI, pick[0])).decode("utf-8", "ignore")
    m = re.search(r'<audio[^>]+src="([^"]+\.mp3)"', track_page) or re.search(r'href="([^"]+\.mp3)"', track_page)
    if not m:
        return None
    download(html.unescape(m.group(1)), os.path.join(outdir, "theme.mp3"))
    return f"khinsider: {pick[1]}"

# --------------------------------------------------------------------------- YouTube (yt-dlp)

def yt_theme(name, outdir):
    if not shutil.which("yt-dlp"):
        return None
    clean = re.sub(r"[™®©]", "", name)
    cmd = ["yt-dlp", f"ytsearch1:{clean} nintendo switch main theme OST",
           "-x", "--audio-format", "mp3", "--audio-quality", "2",
           "--match-filter", "duration < 600", "--no-playlist", "--quiet", "--no-warnings",
           "-o", os.path.join(outdir, "theme.%(ext)s")]
    subprocess.run(cmd, timeout=300, check=False)
    return "youtube" if os.path.exists(os.path.join(outdir, "theme.mp3")) else None

# --------------------------------------------------------------------------- ana iş

def process(g, a):
    name, tid = g["name"], g["id"].upper()
    outdir = os.path.join(a.out, safe_name(name) + f" [{tid}]")
    os.makedirs(outdir, exist_ok=True)
    row = {"title_id": tid, "name": name, "folder": os.path.basename(outdir),
           "icon": "", "banner": "", "screenshots": 0, "steamgriddb": "", "music": ""}
    try:
        if g.get("iconUrl"):
            download(g["iconUrl"], os.path.join(outdir, "icon" + ext_of(g["iconUrl"])))
            row["icon"] = "ok"
        if g.get("bannerUrl"):
            download(g["bannerUrl"], os.path.join(outdir, "banner" + ext_of(g["bannerUrl"])))
            row["banner"] = "ok"
        if a.screenshots:
            for i, u in enumerate((g.get("screenshots") or [])[: a.screenshots], 1):
                download(u, os.path.join(outdir, f"screenshot_{i}" + ext_of(u)))
                row["screenshots"] = i
    except Exception as e:
        row["icon"] = row["icon"] or f"error: {e}"
    if a.steamgriddb_key:
        try:
            row["steamgriddb"] = ",".join(sgdb_media(name, a.steamgriddb_key, outdir)) or "none"
        except Exception as e:
            row["steamgriddb"] = f"error: {e}"
    if a.music != "none":
        if os.path.exists(os.path.join(outdir, "theme.mp3")):
            row["music"] = "already present"
        else:
            src = None
            if a.music in ("khinsider", "both"):
                try:
                    src = khi_theme(name, outdir)
                except Exception as e:
                    row["music"] = f"khinsider error: {e}"
            if not src and a.music in ("youtube", "both"):
                try:
                    src = yt_theme(name, outdir)
                except Exception as e:
                    row["music"] = f"youtube error: {e}"
            row["music"] = src or row["music"] or "not found"
    meta = {k: g.get(k) for k in ("id", "name", "publisher", "developer", "releaseDate",
                                    "category", "numberOfPlayers", "description", "intro", "nsuId")}
    with open(os.path.join(outdir, "info.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return row

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(description="Nintendo Switch ikon / arka plan / tema müziği indirici")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--list", help="Oyun adları veya Title ID'leri içeren txt dosyası")
    src.add_argument("--all", action="store_true", help="Tüm katalog (~19 bin oyun)")
    src.add_argument("--search", help="Katalogda isim ara ve çık")
    p.add_argument("--out", default=os.path.join(here, "media"), help="Çıktı klasörü (varsayılan: ./media)")
    p.add_argument("--regions", default=",".join(DEFAULT_REGIONS),
                   help="Birleştirilecek bölgeler, ilk yazılan ana bölge. Seçenekler: " + ", ".join(REGIONS))
    p.add_argument("--screenshots", type=int, default=0, help="Oyun başına kaç ekran görüntüsü (0-6)")
    p.add_argument("--music", choices=["khinsider", "youtube", "both", "none"], default="khinsider")
    p.add_argument("--no-music", action="store_true")
    p.add_argument("--steamgriddb-key", default=os.environ.get("SGDB_KEY"),
                   help="SteamGridDB API anahtarı (veya SGDB_KEY ortam değişkeni)")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--limit", type=int, default=0, help="Test için ilk N oyun")
    p.add_argument("--refresh", action="store_true", help="titledb'yi yeniden indir")
    a = p.parse_args()
    if a.no_music:
        a.music = "none"

    catalog = load_catalog([r.strip() for r in a.regions.split(",") if r.strip()], os.path.join(here, ".cache"), a.refresh)

    if a.search:
        n = norm(a.search)
        hit = lambda g: n in norm(g["name"]) or any(n in norm(x) for x in g.get("alt", []))
        for g in sorted((g for g in catalog if hit(g)), key=lambda g: g["name"])[:50]:
            print(f'{g["id"]}  {",".join(g.get("regions", [])):12} {g["name"]}')
        return

    if a.all:
        games = sorted(catalog, key=lambda g: g["name"].lower())
        if a.music != "none":
            log("Uyarı: tüm katalog için müzik çok uzun sürer ve siteleri yorar. --no-music önerilir.")
    else:
        with open(a.list, encoding="utf-8") as f:
            wanted = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
        found, missing = match_games(catalog, wanted)
        for w, g in found:
            if norm(w) != norm(g["name"]) and not w.upper().startswith("0100"):
                log(f'  eşleşti: "{w}"  ->  {g["name"]}  [{g["id"]}]')
        for w in missing:
            log(f'  BULUNAMADI: "{w}"  (--search ile adını kontrol et ya da Title ID yaz)')
        seen, games = set(), []
        for _, g in found:
            if g["id"] not in seen:
                seen.add(g["id"]); games.append(g)
    if a.limit:
        games = games[: a.limit]

    os.makedirs(a.out, exist_ok=True)
    # müzik siteleri için daha az paralellik
    workers = a.workers if a.music == "none" else min(a.workers, 3)
    log(f"{len(games)} oyun işlenecek -> {a.out}")
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(process, g, a): g for g in games}
        for i, fu in enumerate(as_completed(futs), 1):
            g = futs[fu]
            try:
                r = fu.result()
            except Exception as e:
                r = {"title_id": g["id"], "name": g["name"], "icon": f"error: {e}"}
            rows.append(r)
            mus = f' | müzik: {r.get("music")}' if a.music != "none" else ""
            log(f'[{i}/{len(games)}] {r["name"]}{mus}')

    idx = os.path.join(a.out, "index.csv")
    fields = ["title_id", "name", "folder", "icon", "banner", "screenshots", "steamgriddb", "music"]
    with open(idx, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["name"].lower()):
            w.writerow(r)
    nomusic = sum(1 for r in rows if r.get("music") == "not found" or str(r.get("music", "")).startswith(("khinsider error", "youtube error")))
    log(f"\nBitti. Özet: {idx}")
    if a.music != "none":
        log(f"Müziği bulunamayan: {nomusic} oyun (index.csv'de 'music' sütununa bak).")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nDurduruldu. Tekrar çalıştırınca kaldığı yerden devam eder.")
