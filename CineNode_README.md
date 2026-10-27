# 🎬 Proje CineNode: Otomatize Edilmiş Medya Sunucusu ve Zaman Paylaşımlı Yayın Ağı

Bu proje, yüksek hızlı (1000/60 Mbps) ancak asimetrik ve CGNAT arkasındaki bir ev internetini kullanarak, sıfır donanımsal transcode  politikasıyla tamamen otomatize edilmiş bir 4K/1080p medya yayın ağı kurmayı amaçlamaktadır.

Kullanıcı trafiği, upload darboğazını aşmak amacıyla "Zaman Paylaşımı" mantığıyla çalışan bir Telegram Botu üzerinden yönetilir.

## 🏗️ Mimari Fazlar

### Faz 1: Proof of Concept (PoC) - Mevcut Donanım Testi

Bu fazın amacı, ekstra donanım masrafına girmeden yerel ağdaki dosyaların CGNAT aşılarak dışarıdaki 1 kullanıcıya sorunsuz (Direct Play) aktarılabildiğini kanıtlamaktır.

* **Donanım:** HP Victus Laptop + 1TB Harici HDD

* **İnternet:** Superonline Wi-Fi (60 Mbps Upload)

* **Kullanıcı:** 1 Test Kullanıcısı

* **Erişim Yöntemi:** Cloudflare Tunnel (cloudflared)

* **Başarı Kriteri:** Dışarıdaki kullanıcının Plex Dashboard üzerinde "Direct Play" ile takılmadan film izleyebilmesi.

### Faz 2: Prodüksiyon (7/24 Bağımsız Sistem)

PoC başarılı olduktan sonra HP Victus devreden çıkarılır ve sistem izole bir Mini PC'ye taşınarak tam otomasyona geçirilir.

* **Donanım:** Intel N100 Mini PC (16GB RAM) + 1TB Harici HDD (İleride 4TB/8TB'a genişletilebilir)

* **Ağ Bağlantısı:** Gigabit Ethernet Kablosu

* **Kapasite:** Toplam 4 Kullanıcı (Zaman paylaşımlı)

## ⚙️ Yazılım Katmanı (Docker Stack)

Sistem Ubuntu/Debian tabanlı bir Linux işletim sistemi üzerinde Docker container'ları ile çalışacaktır.

1. **Plex Media Server:** Oynatma, kütüphane yönetimi ve dış ağa aktarım.

2. **qBittorrent-nox:** Arka planda indirme motoru (Hız ve SSD optimizasyonları yapılmış halde).

3. **Radarr:** Film takip, arama ve indirme otomasyon beyni.

4. **Prowlarr:** Torrent indeks ve tracker yöneticisi.

5. **CineBot (Telegram):** Kullanıcı istek (request) ve zaman bazlı erişim yönetim scripti (Python).

6. **Cloudflared:** Modemde port açmadan dışarıya güvenli tünel sağlayan araç.

## 🔒 Ağ ve Erişim Kuralları

### 1. Sıfır Transcode (Zero-Transcode) Politikası

Plex Pass lisansı satın alınmayacağı ve Intel QuickSync kullanılmayacağı için **herhangi bir video dönüşümüne izin verilmez.**

* İndirilecek tüm medyalar **WEB-DL**, **WEBRip** veya **x265 Encode** formatında olacaktır.

* Ses kanalları **E-AC3, AC3 veya AAC** olmalıdır (TrueHD veya DTS-HD MA kullanılmayacaktır).

* Altyazılar kesinlikle metin tabanlı **.SRT** formatında olacaktır (PGS/Görsel altyazı yasak).

* Arkadaşların TV ve mobil cihazlarındaki Plex uygulamalarında "Video Kalitesi" ayarı kesinlikle **Original / Maximum** olarak kilitlenecektir.

### 2. CGNAT ve Dış Erişim (Cloudflare Tunnel)

Superonline altyapısındaki CGNAT (100.64.x.x) havuzu nedeniyle port yönlendirme yapılamaz.

* Cloudflare üzerinden ücretsiz bir alan adı (Domain) sisteme bağlanacak.

* Sunucuda çalışacak `cloudflared` daemon'ı, Plex'in 32400 portunu güvenli bir HTTPS tüneliyle dünyaya açacaktır.

## 🤖 Kullanıcı Yönetimi: Telegram Botu (Time-Sharing)

60 Mbps upload hızı aynı anda maksimum 4 adet 1080p veya 2 adet 4K yayını kaldırabilir. Darboğazı önlemek için 4 kişilik arkadaş grubu iki pakete ayrılır ve Plex API üzerinden yetkileri bot tarafından otomatik yönetilir.

### Kullanıcı Sınıfları

* **Çalışanlar (2 Kişi):** Yalnızca Hafta İçi akşam (18:00 - 01:00) ve Hafta Sonu tüm gün erişim.

* **İşsizler (2 Kişi):** Yalnızca Hafta İçi gündüz ve gece (01:00 - 18:00) arası erişim (Çalışanlar aktifken sistemden düşürülürler).

### Telegram Bot Komutları ve Mantığı

* `/istek [Film Adı]:` Kullanıcı film ister. Bot Radarr API'sine sinyal gönderir, Radarr filmi bulup qBittorrent'e aktarır.

* `/durum:` Bot, Plex API'ye bağlanıp filmin indirilme durumunu veya kütüphaneye eklenip eklenmediğini söyler.

* **Cronjob / Scheduler:** Bot her gün saat 17:59'da Plex API üzerinden "İşsizler" grubunun kütüphane paylaşımını (Share) askıya alır ve "Çalışanlar" grubunu aktif eder. Saat 01:01'de ise tam tersini yapar.

## 💾 Depolama Yönetimi (Retention Policy)

1TB disk kapasitesi nedeniyle sistemin şişmesini engellemek için Radarr veya harici bir Python scripti ile otomatik temizleme döngüsü (FIFO) kurulacaktır:

* İzlenme tarihi 14 günü geçen içerikler silinir.

* Disk doluluk oranı %90'a ulaştığında, kütüphanedeki en eski ve aktif olarak izlenmeyen filmler otomatik olarak silinerek yeni "siparişlere" yer açılır.