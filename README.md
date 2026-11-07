# 🎬 CineNode

> **Yüksek performanslı, sıfır donanımsal transcode (Direct Play) politikasıyla çalışan, zaman paylaşımlı ve Telegram Botu ile tam otomatize edilmiş kişisel 4K/1080p medya sunucusu.**

---

## 📌 Genel Bakış

**CineNode**, asimetrik ev interneti (1000 Mbps Download / 60 Mbps Upload) ve CGNAT arkasındaki bir altyapıda, arkadaş grubuna kesintisiz ve yüksek kaliteli film deneyimi sunmak üzere tasarlanmıştır.

Donanım maliyetini ve transcode kaynaklı CPU/GPU yükünü sıfıra indirmek için **Sıfır Transcode (Direct Play)** mimarisi benimsenmiştir. Upload darboğazını engellemek için ise kullanıcı trafiği **Zaman Paylaşımı (Time-Sharing)** ve **Puan Kotası Bazlı Depo Yönetimi** ile Telegram Botu üzerinden yönetilir.

---

## 🏗️ Mimari & Yazılım Katmanı (Docker Stack)

Sistem Linux/Windows ortamında Docker konteynerleri ve Python tabanlı otomasyon servisleri üzerinden çalışır:

```
[ Telegram Kullanıcısı ]
          │
          ▼
   [ CineBot (Python) ] ──────────┐
    ├── Telegram Bot API          │
    ├── Zaman Paylaşımı (Cron)    │
    └── Depo & Favori Yöneticisi  │
          │                       │
          ├── Radarr API (7878)   ├── Prowlarr API (9996)
          │         │             │         │
          │         ▼             │         ▼
          │   [ qBittorrent ] ◄───┘   [ Torrent Tracker'lar ]
          │         │ (İndirme Tamamlandı)
          ▼         ▼
     [ Medya Kütüphanesi ] (movies_1080p / movies_4k)
          │
          ▼
    [ Plex Media Server ] (32400) ──► [ TV / Mobil Cihazlar (Direct Play) ]
```

### Konteynerler ve Servisler:
1. **Plex Media Server (`cinenode_plex`):**
   - Medya akışı ve kütüphane yönetimi (Port: `32400`).
   - Host LAN IP otomatik algılama ve senkronizasyonu (Superonline/Modem DNS Rebinding engeline karşı dayanıklı bağlantı).
2. **qBittorrent-nox (`cinenode_qbittorrent`):**
   - Arka plan torrent indirme motoru (WebUI: `8080`, Torrent Portu: `6881`).
3. **Radarr (`cinenode_radarr`):**
   - Film takibi, kalite profilleri ve kütüphane düzenleme beyni (Port: `7878`).
4. **Prowlarr (`cinenode_prowlarr`):**
   - Torrent indeksleyicileri ve tracker entegrasyonu (Port: `9996`).
5. **CineBot (`bot/main.py`):**
   - Kullanıcı etkileşimi, canlı indirme takibi, seeder analiz motoru, disk/favori koruması ve zaman paylaşımı scheduler'ı.

---

## 🤖 CineBot Yetenekleri & Telegram Komutları

| Komut | Açıklama |
| :--- | :--- |
| `/istek <Film Adı>` | Film arar, torrent swarm seeder analizi yapar ve süreye göre kalite seçtirir. |
| `/durum` | Aktif indirmeleri gerçek zamanlı (canlı ilerleme çubuğuyla) takip eder; anında iptal butonu sunar. |
| `/depo` | Disk kullanımını, inen/inmiş filmleri listeler; film silme ve favori işlemlerini yönetir. |
| `/vardiya` | Aktif yayın vardiyasını ve şu anda Plex'te film izleyen kullanıcıları gösterir. |
| `/yardim` | Direct Play altın kurallarını ve oynatıcı ayarlarını hatırlatır. |

---

### 1. Akıllı Torrent Analizi & Tahmini İndirme Süresi (`/istek`)

Film arandığında Prowlarr üzerinden 3 kalite profili taranır:
- **1080p Full HD** (`/media/movies_1080p`)
- **Kompakt 2160p (4K Hafif - ≤15 GB)** (`/media/movies_4k`)
- **Full 2160p (4K Master - >15 GB)** (`/media/movies_4k`)

#### ⚡ %25 Gerçekçi Swarm Seeder Hesabı:
Public torrent ağlarında bir istemcinin tüm swarm'a bağlanamayacağı göz önünde bulundurularak hesaplama tracker seeder sayısının **%25'i (Aktif Seed)** üzerinden yapılır (`eff_seeders = max(1, round(seeders * 0.25))`).

#### ⏱️ Süre Bazlı Kategori & İndirilemez Koruması:
Rozetler, dosya boyutuna ve hesaplanan net dakikaya göre belirlenir:

| Rozet | 10 GB (1080p / Kompakt) | 50 GB (Full 4K Master) | Durum |
| :--- | :--- | :--- | :--- |
| ⚡ **Çok Hızlı** | **< 10 dk** | **< 30 dk** | İndirilebilir |
| 🚀 **Hızlı** | **10 - 30 dk** | **30 - 60 dk** | İndirilebilir |
| ⏳ **Normal** | **30 - 90 dk** | **60 - 120 dk** (1-2 sa) | İndirilebilir |
| ⚠️ **Yavaş** | **1.5 - 3 saat** | **2 - 6 saat** | İndirilebilir |
| ⚠️ **Çok Yavaş** | **3 - 6 saat** | **6 - 12 saat** | İndirilebilir |
| ❌ **İndirilemez** | **> 6 saat** veya 0 seed | **> 12 saat** veya 0 seed | **Kilitli / Engellendi** |

- Süre sınırı aşılan veya seeder'ı olmayan torrentlerde buton `[❌ 1080p (İndirilemez)]` olarak kilitlenir; ölü veya saatler sürecek indirmelerin sunucuyu tıkaması engellenir.
- **Kalite Değişimi & Çakışma Önleme:** İstenen film zaten kütüphanede varsa veya farklı bir kalitede mevcutsa bot eski versiyonu diskten silip yer açtıktan sonra yeni kaliteyi indirmek için iki adımlı onay ister.

---

### 2. Canlı İndirme Takibi & İptal Mekanizması (`/durum`)

- qBittorrent verileriyle **her 4 saniyede bir** mesaj canlı güncellenir (İlerleme çubuğu `%`, hız `MB/s`, kalan süre ve tohumlayıcı sayısı).
- **Telegram 429 (Flood Control) Koruması:** İlk durum mesajı anında basılır, ara mesaj gecikmesi olmadan güvenli hız limitiyle yenilenir.
- **Tek Tıkla İptal (`[🛑 İndirmeyi İptal Et]`):** İnen her film için bağımsız iptal butonu yer alır. Tıklandığında qBittorrent torrenti, Radarr kuyruğu, Radarr veritabanı kaydı ve diskteki yarım indirme parçaları tek hamlede temizlenir.

---

### 3. Depolama & Kota Korumalı Favori Sistemi (`/depo`)

- **Şişmesiz Gerçek Boyut Hesabı:** İnmekte olan filmlerin sanal toplam boyutu yerine yalnızca o ana kadar inen fiziksel baytları hesaba katılır (`dl_bytes = max(0, tot - left)`). Depo doluluk çubuğu asla erken şişmez; indirme bitince beklenen toplam alan ayrıca bildirilir.
- **İndirme İptali:** İnmekte olan filme tıklandığında `[🛑 İndirmeyi İptal Et ve Sil]` seçeneği sunulur.
- **⭐ Dokunulmaz Favori Sistemi:**
  - Her kullanıcının **4 Puanlık** favori kotası bulunur:
    - 👑 **1 Full 4K** (4 Puan)
    - ⚡ **2 Kompakt 4K** (2 x 2 Puan)
    - 🎬 **4 1080p Full HD** (4 x 1 Puan)
  - **Silinmezlik Kuralı:** Favoriye alınan bir film **ASLA** sistem veya diğer kullanıcılar tarafından silinemez. Yalnızca favoriye alan kullanıcı veya sistem yöneticisi (admin) silebilir.
- **Otomatik Kütüphane & Disk Temizliği:** Film silindiğinde diskteki klasör, Radarr kaydı kaldırılır ve Plex kütüphanesi tetiklenerek anında güncellenir.

---

### 4. Zaman Paylaşımı (Time-Sharing Scheduler)

60 Mbps upload hattının bant genişliğini adil dağıtmak amacıyla kullanıcılar iki gruba ayrılır ve Plex API üzerinden kütüphane erişimleri otomatik açılıp kapatılır:

- 💼 **Çalışanlar Grubu:** Hafta içi 18:00 - 01:00 arası ve Hafta sonu 7/24 kesintisiz erişim.
- 🛋️ **İşsizler / Gece Kuşları Grubu:** Hafta içi 01:00 - 18:00 arası erişim (Çalışanlar mesaisi başladığında erişimleri askıya alınır).

---

## 🔒 Ağ, Güvenlik & Direct Play Kuralları

1. **Sıfır Donanımsal Transcode:**
   - Plex sunucusunda video dönüşümü devre dışıdır.
   - İstemciler (TV / Mobil / PC) Video Kalitesi ayarını **Orijinal / Maksimum** seçmelidir.
   - Altyazılar metin tabanlı **.SRT** olmalıdır (PGS/Görsel altyazılar transcode tetikleyebilir).
2. **DNS Rebinding & LAN IP Senkronizasyonu:**
   - Superonline ve benzeri fiber modemlerin `*.plex.direct` alan adını engellemesine karşı `PlexManager` bot başlangıcında sunucunun LAN IP'sini (`192.168.1.x`) tespit ederek `customConnections` ayarını günceller.
   - TV istemcilerinde *"Güvensiz Bağlantılara İzin Ver: Aynı Ağda"* seçeneği önerilir.

---

## 🚀 Kurulum & Çalıştırma

### 1. Gereksinimler
- Docker & Docker Compose
- Python 3.11+
- Aktif bir Telegram Bot Token'ı ([@BotFather](https://t.me/BotFather))

### 2. Ortam Değişkenleri (`.env`)
`.env.example` dosyasını `.env` olarak kopyalayın ve bilgilerinizi girin:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ADMIN_IDS=123456789
TELEGRAM_ALLOWED_USERS=123456789,987654321

# Plex
PLEX_BASE_URL=http://localhost:32400
PLEX_TOKEN=your_plex_token_here
PLEX_USERS_WORKERS=user1@gmail.com,user2@gmail.com
PLEX_USERS_UNEMPLOYED=user3@gmail.com,user4@gmail.com

# Radarr & Prowlarr & qBittorrent
RADARR_BASE_URL=http://localhost:7878
RADARR_API_KEY=your_radarr_key
PROWLARR_BASE_URL=http://localhost:9996
PROWLARR_API_KEY=your_prowlarr_key
QBIT_BASE_URL=http://localhost:8080
```

### 3. Docker Servislerini Başlatma
```bash
docker compose up -d
```

### 4. CineBot'u Çalıştırma
Gerekli Python paketlerini yükleyin:
```bash
pip install -r bot/requirements.txt
```

Botu başlatın:
```bash
# Doğrudan konsoldan:
python bot/main.py

# Windows için arka planda sessiz başlatma:
baslat_sessiz.vbs
```

---

## 📂 Dizin Yapısı

```
CineNode/
├── bot/
│   ├── main.py              # Telegram bot çekirdeği ve komut işleyicileri
│   ├── radarr_client.py     # Radarr, Prowlarr ve qBittorrent istemcisi
│   ├── plex_client.py       # Plex API, IP senkronu ve oturum yöneticisi
│   ├── scheduler.py         # APScheduler zaman paylaşımı ve periyodik görevler
│   ├── favorites.py         # Favori puan kotası ve koruma yöneticisi
│   └── requirements.txt     # Python kütüphaneleri
├── config/
│   ├── plex/                # Plex yapılandırma ve veritabanı
│   ├── radarr/              # Radarr veritabanı
│   ├── prowlarr/            # Prowlarr veritabanı
│   ├── qbittorrent/         # qBittorrent yapılandırması
│   └── favorites.json       # Kalıcı favori film kayıtları
├── media/
│   ├── downloads/           # qBittorrent indirme klasörü
│   ├── movies_1080p/        # 1080p Full HD Plex kütüphanesi
│   └── movies_4k/           # 4K (Kompakt ve Master) Plex kütüphanesi
├── scripts/                 # Yardımcı kurulum ve manuel içe aktarma araçları
├── docker-compose.yml       # Konteyner yığını tanımları
├── baslat_bot.bat           # Hızlı bot başlatıcı
├── baslat_sessiz.vbs        # Konsol penceresiz sessiz başlatıcı
└── README.md                # Proje dokümantasyonu
```

---

## 📜 Lisans
Bu proje kişisel ev laboratuvarı ve arkadaş grubu medya paylaşımı için geliştirilmiştir. İlgili açık kaynak projelerin (Plex, Radarr, Prowlarr, qBittorrent) lisans kurallarına tabidir.
