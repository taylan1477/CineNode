import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler
)

# Kök dizini sys.path'e ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.radarr_client import RadarrClient
from bot.plex_client import PlexManager
from bot.scheduler import setup_scheduler, activate_workers_shift, activate_unemployed_shift

# .env yükle
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("CineBot")

radarr = RadarrClient()
plex = PlexManager()

def is_user_authorized(user_id: int) -> bool:
    allowed_ids_raw = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "")
    if not allowed_ids_raw:
        return True # Boşsa herkese açık (başlangıç için)
    allowed_ids = [int(i.strip()) for i in allowed_ids_raw.split(",") if i.strip()]
    return user_id in allowed_ids

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        f"🎬 *CineNode Bot'a Hoş Geldiniz, {user.first_name}!*\n\n"
        "CineNode ortak film yayın ağımız için istek ve durum botudur.\n\n"
        "📌 *Komutlar:*\n"
        "• `/istek <Film Adı>` : Yeni bir film talep eder ve indirmeyi başlatır.\n"
        "• `/durum` : Aktif inen filmleri ve kütüphane durumunu gösterir.\n"
        "• `/vardiya` : Mevcut yayın saatini ve aktif izleyicileri gösterir.\n"
        "• `/yardim` : Altın kuralları ve Plex ayarlarını hatırlatır.\n\n"
        "⚠️ *Hatırlatma:* Plex uygulamanızda video kalitesini her zaman **Orijinal / Maksimum** yapmayı unutmayın!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🍿 *CineNode Altın Kurallar & Yayın Saatleri*\n\n"
        "🕰️ *Vardiyalar:*\n"
        "• **Çalışanlar:** Hafta içi 18:00 - 01:00 & Hafta sonu 7/24\n"
        "• **İşsizler:** Hafta içi 01:00 - 18:00\n\n"
        "⚙️ *Plex İstemci Ayarı:*\n"
        "Ayarlar > Video Kalitesi > Maksimum/Orijinal (Transcode yasaktır!)\n\n"
        "📝 *Altyazı Sorunu:* Altyazı açıldığında video donuyorsa altyazıyı kapatıp tekrar deneyin."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_user_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz bulunmuyor.")
        return

    if not context.args:
        await update.message.reply_text("Lütfen bir film adı belirtin. Örnek: `/istek Inception`", parse_mode="Markdown")
        return

    movie_name = " ".join(context.args)
    await update.message.reply_text(f"🔍 *{movie_name}* Radarr üzerinde aranıyor...", parse_mode="Markdown")

    results = radarr.search_movie(movie_name)
    if not results:
        await update.message.reply_text("❌ Aradığınız film Radarr indeksinde bulunamadı veya Radarr API bağlantısı kurulamadı.")
        return

    # İlk ve en alakalı sonucu al
    best_match = results[0]
    title = best_match.get("title")
    year = best_match.get("year", "Bilinmiyor")
    overview = best_match.get("overview", "Açıklama yok.")
    if len(overview) > 200:
        overview = overview[:200] + "..."

    # Radarr'a ekle
    res = radarr.add_movie(best_match)
    if res.get("success"):
        reply = (
            f"✅ *{title} ({year})* başarıyla indirme sırasına eklendi!\n\n"
            f"📖 {overview}\n\n"
            "İndirme tamamlandığında Plex kütüphanenizde otomatik olarak görünecektir. `/durum` ile takip edebilirsiniz."
        )
    else:
        err = res.get("error", "Bilinmeyen hata")
        if "already been added" in err.lower():
            reply = f"ℹ️ *{title} ({year})* zaten kütüphanede veya indirme kuyruğunda mevcut."
        else:
            reply = f"⚠️ Film eklenirken bir hata oluştu: {err}"

    await update.message.reply_text(reply, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queue = radarr.get_queue()
    if not queue:
        await update.message.reply_text("💤 Şu anda aktif inen bir film bulunmuyor.")
        return

    msg = "📥 *Devam Eden İndirmeler:*\n\n"
    for item in queue[:5]:
        title = item.get("title", "Bilinmiyor")
        status = item.get("status", "İniyor")
        size_left = round(item.get("sizeleft", 0) / (1024 * 1024 * 1024), 2)
        total_size = round(item.get("size", 0) / (1024 * 1024 * 1024), 2)
        msg += f"• *{title}*\n  Durum: {status} | Kalan: {size_left} GB / {total_size} GB\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def shift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday() # 0 = Pazartesi, 5 = Cts, 6 = Pzr

    if weekday >= 5:
        current_shift = "Hafta Sonu Modu (Çalışanlar 7/24 Aktif)"
    elif 18 <= hour or hour < 1:
        current_shift = "Çalışanlar Vardiyası (18:00 - 01:00)"
    else:
        current_shift = "İşsizler / Gece Kuşları Vardiyası (01:00 - 18:00)"

    sessions = plex.get_active_sessions()
    session_text = ""
    if sessions:
        session_text = "\n\n📺 *Şu Anda İzleyenler:*\n"
        for s in sessions:
            session_text += f"• {s['user']} -> {s['title']} ({s['player']} - {s['state']})\n"
    else:
        session_text = "\n\n📺 Şu an aktif izleyen kimse yok."

    await update.message.reply_text(
        f"⏰ *Mevcut Durum:*\nSaat: {now.strftime('%H:%M')}\nVardiya: *{current_shift}*{session_text}",
        parse_mode="Markdown"
    )

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN .env içinde tanımlanmamış. Bot başlatılamıyor.")
        print("\n[!] TELEGRAM_BOT_TOKEN tanımlı değil. Lütfen .env dosyasını doldurun.\n")
        return

    # Scheduler'ı başlat
    setup_scheduler(plex)

    # Telegram bot uygulamasını başlat (Timeout toleransı yüksek istek havuzu ile)
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(token).request(request).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("yardim", help_command))
    app.add_handler(CommandHandler("istek", request_command))
    app.add_handler(CommandHandler("durum", status_command))
    app.add_handler(CommandHandler("vardiya", shift_command))

    logger.info("CineBot Telegram dinleyicisi başlatılıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
