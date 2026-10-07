# Switch Media

[English](README.md) · **Türkçe**

**Nintendo Switch oyunlarının ikonlarını, banner / arka plan görsellerini ve tema müziklerini** toplu indirmek için küçük, kendi bilgisayarında çalışan bir araç. Birden fazla eShop bölgesinden derlenmiş ~25.000 oyunluk kataloğu tarayıcında ararsın, istediklerini işaretlersin, *Download*'a basarsın; her oyun için düzenli bir klasör oluşur.

![Switch Media — koyu temada katalog görünümü](docs/screenshot.png)

Veritabanı yok, framework yok, `pip install` yok. Python'un standart kütüphanesi, tek bir HTML sayfası ve neleri indirdiğini hatırlayan bir JSON dosyası.

---

## Özellikler

- **Switch kataloğunun tamamı:** ABD, Avrupa, Japonya, Kore ve Hong Kong eShop'larından birleştirilmiş ~25 bin oyun. Avustralya ve Almanya isteğe bağlı.
- **Hızlı arama:** oyun adı, yayıncı veya Title ID ile arama. Diğer bölgelerdeki adlarla da çalışır: `ゼルダ` yazınca Zelda, `동물의 숲` yazınca Animal Crossing bulunur.
- **Filtreler:** tümü, indirilmemiş, indirilmiş ve seçili. Bölgeye göre filtreleme, ada veya çıkış tarihine göre sıralama.
- **Seç ve indir:** oyunları tek tek ya da "Select visible" ile toplu seçersin. İndirme paralel yapılır, canlı ilerleme çubuğu ve günlük gösterilir.
- **Oyun başına dosyalar**
  - `icon.jpg`: ana menüde görünen kare ikon
  - `banner.jpg`: geniş eShop banner'ı, arka plan olarak kullanılabilir
  - `screenshot_N.jpg`: isteğe bağlı, en fazla 6 tane
  - `hero.png` / `logo.png`: isteğe bağlı, SteamGridDB'den
  - `theme.mp3`: KHInsider'dan tema müziği; bulunamazsa isteğe bağlı olarak YouTube'dan
  - `info.json`: ad, yayıncı, çıkış tarihi, kategoriler, açıklama
- **Kaldığı yerden devam eder:** var olan dosyalar atlanır, tekrar çalıştırınca sadece eksikler tamamlanır.
- **Veritabanı olmadan takip:** neyin indirildiği `downloaded.json`'da tutulur. Klasör her açılışta yeniden taranır; bir oyun klasörünü elle silersen listeden de düşer.
- **Detay penceresi:** banner önizlemesi ve indirilen müzik için oynatıcı.
- **Açık / koyu tema:** sistem ayarını takip eder.
- **Komut satırı modu:** script'lerde ve toplu işlerde kullanmak için.

## Gereksinimler

- **Python 3.9+.** macOS'la gelen sürüm yeterli; ek paket gerekmez.
- *İsteğe bağlı, YouTube'dan müzik için:* [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) ve `ffmpeg`
  ```bash
  brew install yt-dlp ffmpeg
  ```
- *İsteğe bağlı:* hero ve logo görselleri için ücretsiz bir SteamGridDB API anahtarı. Bkz. [SteamGridDB API anahtarı](#steamgriddb-api-anahtarı-isteğe-bağlı).

## Hızlı başlangıç

```bash
git clone https://github.com/<kullanici-adin>/switch-media.git
cd switch-media
python3 server.py
```

Tarayıcında <http://localhost:8765> açılır. macOS'ta **`Switch Media.command`** dosyasına çift tıklamak da yeterli.

İlk açılışta seçili her bölgenin oyun listesi indirilir. Bölge başına ~50–90 MB, bir iki dakika sürer. Sadece gereken alanlar saklanır (beş bölge için diskte ~175 MB) ve katalog haftada bir kendini yeniler.

### Arayüzün kullanımı

1. Bir oyun **ara** ya da filtreleri ve bölge menüsünü kullan.
2. Seçmek için **karta tıkla**. Tüm sonuçları seçmek için *Select visible*'a bas.
3. Alttaki **Download** butonuna bas. İlerleme alt çubukta, ayrıntılar **Log** penceresinde görünür.
4. Detaylar, banner ve (indirildiyse) müzik oynatıcı için karttaki **i** butonuna tıkla.
5. **Settings**'ten şunları değiştirebilirsin: çıktı klasörü, müzik kaynağı, ekran görüntüsü sayısı, SteamGridDB anahtarı, bölgeler ve aynı anda indirilecek oyun sayısı.

> **İpucu:** Tüm kataloğu indireceksen (19 binden fazla oyun, müziksiz ~8 GB) iCloud veya Dropbox dışında bir çıktı klasörü seç, örneğin `~/SwitchMedia`.

## SteamGridDB API anahtarı (isteğe bağlı)

İkonlar, banner'lar ve ekran görüntüleri Nintendo eShop'tan gelir ve anahtar gerektirmez. Her oyun için ayrıca **hero görselleri** (geniş, yüksek kaliteli arka planlar) ve **şeffaf zeminli logolar** da istiyorsan, araç bunları ücretsiz API'si olan topluluk görsel sitesi [SteamGridDB](https://www.steamgriddb.com/)'den çekebilir.

1. [steamgriddb.com](https://www.steamgriddb.com/)'a giriş yap. Giriş Steam hesabıyla yapılıyor; ücretsiz bir hesap yeterli.
2. **Profile → Preferences → API** sayfasına git ya da doğrudan <https://www.steamgriddb.com/profile/preferences/api> adresini aç.
3. **Generate API Key**'e tıklayıp anahtarı kopyala.
4. Anahtarı şu yerlerden birine gir:
   - **Arayüz:** *Settings → SteamGridDB API key*, sonra *Save*.
   - **Komut satırı:** `--steamgriddb-key ANAHTARIN` ya da `export SGDB_KEY=ANAHTARIN`.

Anahtar girildiğinde indirdiğin her oyun için `hero.png` ve `logo.png` de iner (SteamGridDB'de varsa). Detay penceresinde hangilerinin bulunduğunu görürsün.

> 🔒 Anahtarın sadece kendi bilgisayarında kalır. Arayüz onu `.gitignore`'da listelenen `settings.json` dosyasına kaydeder, yani GitHub'a gönderilmez. SteamGridDB'yi kapatmak için alanı boş bırakman yeterli.

## Komut satırı kullanımı

`switch_media.py` arayüz olmadan da çalışır:

```bash
# Bir oyunun tam adını / Title ID'sini bul
python3 switch_media.py --search "zelda"

# Bir oyun listesini indir (her satıra bir ad veya Title ID)
python3 switch_media.py --list games.example.txt

# SteamGridDB görselleri, YouTube yedeği ve 3 ekran görüntüsüyle
python3 switch_media.py --list games.example.txt --steamgriddb-key ANAHTARIN --music both --screenshots 3

# Sadece ABD + Japonya katalogları
python3 switch_media.py --list games.example.txt --regions US.en,JP.ja

# Tüm katalog, sadece görseller
python3 switch_media.py --all --no-music --workers 16 --out ~/SwitchMedia
```

| Seçenek | Açıklama |
|---|---|
| `--list DOSYA` | Her satırda bir oyun adı veya Title ID (`0100…`) olan metin dosyası. `#` ile başlayan satırlar yok sayılır. Adlar yaklaşık eşleştirilir. |
| `--all` | Katalogdaki tüm oyunlar. |
| `--search METİN` | Katalogda arama yapıp çıkar. |
| `--out KLASÖR` | Çıktı klasörü (varsayılan `./media`). |
| `--regions` | Virgülle ayrılmış katalog bölgeleri; ilk yazılan ana bölge olur (varsayılan `US.en,GB.en,JP.ja,KR.ko,HK.zh`). |
| `--music` | `khinsider` (varsayılan), `youtube`, `both` veya `none`. `--no-music`, `none` ile aynı. |
| `--screenshots N` | Oyun başına ekran görüntüsü sayısı (0–6). |
| `--steamgriddb-key` | SteamGridDB API anahtarı. `SGDB_KEY` ortam değişkeni de kullanılabilir. |
| `--workers N` | Paralel indirme sayısı (varsayılan 6). Müzik açıkken sitelere yük bindirmemek için en fazla 3. |
| `--limit N` | Test için sadece ilk N oyun. |
| `--refresh` | Kataloğu zorla yeniden indirir. |

`server.py` seçenekleri: `--port 8765`, `--out KLASÖR`, `--no-browser`.

## Çıktı

```
media/
├── downloaded.json                       ← neyin indirildiği (arayüz kullanır)
├── index.csv                             ← komut satırının yazdığı özet
└── Hollow Knight [0100633007D48000]/
    ├── icon.jpg
    ├── banner.jpg
    ├── screenshot_1.jpg                  (isteğe bağlı)
    ├── hero.png  logo.png                (isteğe bağlı, SteamGridDB)
    ├── theme.mp3
    └── info.json
```

Klasör adları `Oyun Adı [TitleID]` şeklinde. Böylece hepsi benzersiz olur ve başka araçlarla kolayca eşleştirilir.

## Veriler nereden geliyor

| Ne | Kaynak | Not |
|---|---|---|
| Oyun listesi, ikonlar, banner'lar, ekran görüntüleri | [blawar/titledb](https://github.com/blawar/titledb) → Nintendo eShop CDN | API anahtarı gerekmez. Her bölge için bir JSON dosyası. |
| Hero ve logo görselleri | [SteamGridDB API](https://www.steamgriddb.com/api/v2) | Ücretsiz API anahtarı, isteğe bağlı. |
| Tema müziği | [KHInsider](https://downloads.khinsider.com/) | En iyi eşleşen soundtrack'ten "Main Theme" / "Title" gibi adı olan parçayı, yoksa ilk parçayı seçer. |
| Yedek müzik kaynağı | `yt-dlp` ile YouTube | "*oyun adı* main theme OST" diye arar, isabeti daha düşük. |

### Bölgeler

| Kod | Bölge | Eklediği yeni oyun* |
|---|---|---|
| `US.en` | ABD (ana bölge) | ~19.400 |
| `GB.en` | Avrupa | ~440 |
| `JP.ja` | Japonya | ~4.100 |
| `KR.ko` | Kore | ~590 |
| `HK.zh` | Hong Kong | ~235 |
| `AU.en` | Avustralya (varsayılan kapalı) | ~10 |
| `DE.de` | Almanya (varsayılan kapalı) | ~25 |

<sub>*Üstteki bölgelerde olmayan oyunlar, Ekim 2026 itibarıyla.</sub>

Bir oyun birden fazla bölgede varsa adı ve görselleri ilk (ana) bölgeden alınır; diğer bölgelerdeki adları arama için saklanır. Japonya, Kore ve Hong Kong oyunlarının çoğunun sadece yerel dilde adı olduğundan KHInsider'da müzikleri nadiren bulunur. Bu oyunlar için YouTube yedeğini kullan.

### Ağ erişimi

Oyun sitelerini engelleyen bir firewall'un veya DNS filtren varsa şu adreslere izin ver:

`raw.githubusercontent.com` · `img-eshop.cdn.nintendo.net` · `downloads.khinsider.com` · `vgmsite.com` · `www.steamgriddb.com` · `cdn2.steamgriddb.com` · YouTube için: `youtube.com`, `googlevideo.com`

## Nasıl çalışıyor

```
tarayıcı (index.html)  ──HTTP──▶  server.py  ──▶  switch_media.py  ──▶  titledb / Nintendo CDN / KHInsider / SteamGridDB / YouTube
                                     │
                                     ├── .cache/          bölge katalogları + küçük resim önbelleği
                                     ├── settings.json    arayüz ayarları (yerelde kalır, git'e girmez)
                                     └── media/downloaded.json
```

- `server.py` küçük bir `http.server` uygulaması. Dört şey yapıyor:
  - sayfayı sunuyor
  - birleştirilmiş kataloğu gzip'li olarak gönderiyor
  - küçük resimleri kendi üzerinden çekip önbelleğe alıyor (Nintendo CDN'i tarayıcının `localhost`'tan doğrudan resim yüklemesine izin vermiyor, önbellek de bant genişliğinden tasarruf sağlıyor)
  - arka planda bir indirme kuyruğu çalıştırıyor
- `switch_media.py` tüm indirme mantığını içeriyor ve aynı zamanda komut satırı aracı.
- `index.html` hiçbir bağımlılığı olmayan tek bir sayfa.

## Proje yapısı

```
switch-media/
├── server.py              yerel web sunucusu + indirme kuyruğu
├── switch_media.py        katalog, eşleştirme, indiriciler, komut satırı
├── index.html             arayüz
├── Switch Media.command   macOS için çift tıklamalı başlatıcı
├── docs/screenshot.png    README'deki ekran görüntüsü
├── games.example.txt      komut satırı için örnek liste
├── README.md / README.tr.md
└── .gitignore             media/, .cache/ ve settings.json'u git dışında tutar
```

## Sorumluluk reddi

Bu kişisel bir hobi projesidir; Nintendo, KHInsider, SteamGridDB veya YouTube ile bağlantısı yoktur ve onlar tarafından desteklenmez. Tüm oyun görselleri ve müzikleri sahiplerine aittir. İndirilen dosyaları kişisel amaçlarla (launcher, dashboard, frontend) kullan ve yeniden dağıtma. Topluluk tarafından işletilen sitelere karşı nazik ol: müzik indirirken paralel indirme sayısını düşük tut.

## Teşekkürler

- Switch oyun veritabanı için [blawar/titledb](https://github.com/blawar/titledb)
- Topluluk görselleri için [SteamGridDB](https://www.steamgriddb.com/)
- Oyun müziği arşivi için [KHInsider](https://downloads.khinsider.com/)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
