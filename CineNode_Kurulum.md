# 🛠️ CineNode: Kurulum, Otomasyon ve Ölçeklendirme Rehberi

Bu doküman, CineNode projesinin teorik mimarisini hayata geçirmek için gereken teknik adımları, kodlama mantığını ve sistem konfigürasyonlarını içerir.

---

## 🚀 Faz 1: HP Victus Üzerinde PoC (Proof of Concept) Kurulumu

Amaç: Mevcut Windows bilgisayarınızda Cloudflare Tunnel kurarak 1 arkadaşınıza CGNAT arkasından Plex yayını yapmak.

### Adım 1: Plex Kurulumu ve Kilit Ayarlar
1. Windows'a **Plex Media Server** kurun ve `1TB HDD`'deki filmlerinizi kütüphaneye ekleyin.
2. Plex Web'de `Ayarlar > Uzaktan Erişim (Remote Access)` sekmesine gidin ve **Devre Dışı Bırakın** (Çünkü erişimi Cloudflare üzerinden biz sağlayacağız).
3. `Ayarlar > Ağ (Network)` altındaki **Güvenli Bağlantılar (Secure Connections)** ayarını `Tercih Edilen (Preferred)` yapın.
4. `Ayarlar > Transcoder` altından **Disable video stream transcoding** (Video dönüştürmeyi kapat) seçeneğini işaretleyin.

### Adım 2: Cloudflare Tunnel Kurulumu
1. Cloudflare'da ücretsiz bir hesap açıp sahip olduğunuz bir domaini ekleyin (Cloudflare Zero Trust dashboard).
2. `Networks > Tunnels` menüsünden yeni bir tünel oluşturun.
3. Size verilen Windows kurulum komutunu (CMD veya PowerShell üzerinden) HP Victus'ta çalıştırın. `cloudflared.exe` arka planda servis olarak çalışmaya başlayacaktır.
4. Tünel ayarlarından `Public Hostname` ekleyin:
   * **Subdomain:** `plex` (örn: plex.domaininiz.com)
   * **Service:** `HTTP://localhost:32400`
5. Arkadaşınız artık tarayıcıdan `plex.domaininiz.com` adresine girerek doğrudan sunucunuza bağlanabilir.

---

## ⚙️ Faz 2: Intel N100 Mini PC Otomasyonu ve Kodlama

Amaç: Sistemi 7/24 izole bir Linux cihazına taşımak ve süreci Docker + Python Telegram Botu ile otomatize etmek.

### Adım 1: Temel İşletim Sistemi ve Docker
Mini PC'ye **Ubuntu Server 24.04** veya **Debian 12** kurun (Monitörsüz / Headless). SSH ile cihaza bağlanıp Docker ve Docker Compose kurulumlarını tamamlayın.

### Adım 2: docker-compose.yml Mimarisi
Tüm sistemi tek bir dosyayla yöneteceğiz. Mini PC'de bir klasör oluşturup içine şu `docker-compose.yml` dosyasını hazırlayın:

```yaml
version: "3.8"
services:
  plex:
    image: lscr.io/linuxserver/plex:latest
    container_name: plex
    network_mode: host
    environment:
      - PUID=1000
      - PGID=1000
      - VERSION=docker
    volumes:
      - /home/taycore/plex_config:/config
      - /mnt/1tb_hdd/media:/media
    restart: unless-stopped

  qbittorrent:
    image: lscr.io/linuxserver/qbittorrent:latest
    container_name: qbittorrent
    ports:
      - 8080:8080
      - 6881:6881
      - 6881:6881/udp
    volumes:
      - /home/taycore/qbit_config:/config
      - /mnt/1tb_hdd/downloads:/downloads

  radarr:
    image: lscr.io/linuxserver/radarr:latest
    container_name: radarr
    ports:
      - 7878:7878
    volumes:
      - /home/taycore/radarr_config:/config
      - /mnt/1tb_hdd:/data

  prowlarr:
    image: lscr.io/linuxserver/prowlarr:latest
    container_name: prowlarr
    ports:
      - 9696:9696
    volumes:
      - /home/taycore/prowlarr_config:/config
```
*Çalıştırmak için terminalde:* `docker compose up -d`

### Adım 3: Telegram Botu Kodlama Mantığı (Python)
Kullanıcı gruplarını (İşsizler/Çalışanlar) yönetecek bot için bir Python scripti yazacağız. İhtiyacımız olan ana kütüphaneler: `python-telegram-bot` (iletişim), `plexapi` (Plex kontrolü), ve `requests` (Radarr istekleri).

**Botun Çekirdek Fonksiyonları:**
1. **İstek Yönetimi:** Kullanıcı `/istek Inception` yazdığında, bot Radarr'ın API'sine (`http://localhost:7878/api/v3/movie`) JSON formatında bir POST isteği atar. Radarr filmi bulur ve qBittorrent'e yollar.
2. **Zaman Paylaşımı (Time-Sharing) Algoritması:**
   `schedule` kütüphanesi kullanarak zamanlanmış görevler (cron jobs) oluşturacağız:
   * **Saat 18:00 tetikleyicisi:** `plexapi` kütüphanesi ile "İşsizler" grubundaki e-posta adreslerinin Kütüphane Paylaşım (Library Share) izinlerini `False` (Kapalı) yapar. "Çalışanlar" grubunu `True` (Açık) yapar.
   * **Saat 01:00 tetikleyicisi:** İşsizler grubunu `True`, Çalışanlar grubunu `False` yapar.
   * *Not:* Bot arka planda bir Linux `systemd` servisi olarak 7/24 çalışacaktır.

---

## 🌍 Faz 3: İşi Büyütmek (Ölçeklendirme / Scaling)

Amaç: 4 kişilik hobi projesini, 15-20 arkadaşınızın (veya müşterinin) yıllık ödeme yaparak kullandığı profesyonel bir "Kişisel Netflix" servisine dönüştürmek.

Faz 1 ve Faz 2'deki "Sıfır Maliyet, Sıfır Transcode" kuralı 20 kişide maalesef çökecektir. Çünkü herkesin interneti, televizyonu veya cihazı 4K Direct Play'i kaldıramaz. Bu noktada sistemi profesyonelleştirmemiz gerekir.

### 1. Donanım ve Depolama Devrimi (NAS Sistemine Geçiş)
* **Depolama:** 1TB harici disk çöpe atılır (veya yedek yapılır). Yerine **TrueNAS** veya **Unraid** işletim sistemiyle çalışan, içinde 4 adet 8TB NAS diski (RAID Z1 konfigürasyonu ile toplam ~24TB kullanılabilir alan ve veri koruması) bulunan gerçek bir sunucu kasası toplanır.
* **Transcode Gücü:** **Plex Pass** satın alınır (Ömür boyu lisans). Intel N100 veya i3/i5 işlemcinin "QuickSync" özelliği aktif edilir. Böylece sistem aynı anda 10 kişinin videosunu (onlar fark etmeden) donanımsal olarak dönüştürüp takılmadan yayınlayabilir.

### 2. İnternet Darboğazını Aşma
Evdeki 60 Mbps upload hızı 20 kişiye yetmeyecektir (Max 5-6 kişi).
* **Çözüm A:** İnternet servis sağlayıcısından (eğer altyapı varsa) 1000/1000 Simetrik Fiber veya minimum 100 Mbps Upload paketine geçiş yapılır.
* **Çözüm B (Seedbox/VPS):** Eğer evdeki internet hızı artmıyorsa, aylık 15-20 Euro'ya Hetzner vb. firmalardan 1 Gigabit paylaşımsız hatlı bir Dedicated Server (Kiralık Sunucu) kiralanır ve sistem tamamen buluta taşınır.

### 3. Yazılım ve Kullanıcı Deneyimi Yükseltmesi
* **Telegram Botuna Veda, Overseerr'a Merhaba:** Kullanıcı sayısı arttığında Telegram chat'i üzerinden istek yönetmek kaos yaratır. Sisteme **Overseerr** uygulaması kurulur. Kullanıcılar `istek.domaininiz.com` adresine girer; karşılarına Netflix gibi afişlerin, fragmanların, popüler içeriklerin olduğu şık bir arayüz çıkar. Beğendiklerine "Request (İste)" butonuna basarlar, film inince otomatik e-posta/bildirim gider.
* **Ödeme Yönetimi:** Kullanıcı hesapları süre sınırlarına göre yönetilir; aboneliği biten kişinin hesabı Tautulli veya özel scriptler aracılığıyla otomatik olarak askıya alınır.