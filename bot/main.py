import os
import sys
import asyncio
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
from bot.scheduler import setup_scheduler

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("CineBot")

radarr = RadarrClient()
plex = PlexManager()

# Canlı takip görevlerini yönetmek için (chat_id -> asyncio.Task)
ACTIVE_TRACKERS = {}
# Kullanıcının aradığı bekleyen filmler (user_id -> movie_dict)
PENDING_REQUESTS = {}

def is_user_authorized(user_id: int) -> bool:
    allowed_ids_raw = os.getenv("ALLOWED_TELEGRAM_USER_IDS", "")
    if not allowed_ids_raw:
        return True
    allowed_ids = [int(i.strip()) for i in allowed_ids_raw.split(",") if i.strip()]
    return user_id in allowed_ids

def render_progress_bar(percentage: float, length: int = 10) -> str:
    """Yüzdeye göre görsel ilerleme çubuğu üretir: [████░░░░░░]"""
    filled = int(round(length * (percentage / 100)))
    filled = min(length, max(0, filled))
    empty = length - filled
    return "█" * filled + "░" * empty

def format_eta(seconds: int) -> str:
    if seconds <= 0 or seconds > 86400:
        return "Bilinmiyor"
    mins = seconds // 60
    secs = seconds % 60
    if mins > 60:
        hrs = mins // 60
        mins = mins % 60
        return f"{hrs} sa {mins} dk"
    return f"{mins} dk {secs} sn"

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = (
        f"🎬 *CineNode Bot'a Hoş Geldiniz, {user.first_name}!*\n\n"
        "CineNode film yayın ağımız için istek ve canlı takip botudur.\n\n"
        "📌 *Komutlar:*\n"
        "• `/istek <Film Adı>` : Film arar, size **1080p mi 2160p (4K) mı** istediğinizi sorar ve indirmeyi başlatır.\n"
        "• `/durum` : Aktif indirmeleri **gerçek zamanlı (canlı)** olarak takip eder.\n"
        "• `/vardiya` : Yayın saatini ve aktif izleyicileri listeler.\n"
        "• `/yardim` : Altın kuralları hatırlatır."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🍿 *CineNode Altın Kurallar & Kullanım*\n\n"
        "1. **/istek <Film Adı>** yazarak aratın, gelen butonlardan **1080p** veya **2160p (4K)** seçin.\n"
        "2. **/durum** yazdığınızda mesaj saniyeler içinde kendini canlı günceller.\n"
        "3. **Transcode Yasaktır:** TV/Cihaz Plex uygulamasında Video Kalitesi mutlaka **Maksimum/Orijinal** olmalıdır."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def request_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_authorized(user_id):
        await update.message.reply_text("⛔ Bu komutu kullanma yetkiniz bulunmuyor.")
        return

    if not context.args:
        await update.message.reply_text("Lütfen bir film adı belirtin.\nÖrnek: `/istek Interstellar`", parse_mode="Markdown")
        return

    movie_name = " ".join(context.args)
    search_msg = await update.message.reply_text(f"🔍 *{movie_name}* aranıyor...", parse_mode="Markdown")

    results = radarr.search_movie(movie_name)
    if not results:
        await search_msg.edit_text("❌ Aradığınız film Radarr indeksinde bulunamadı. Lütfen adı kontrol edin.")
        return

    best_match = results[0]
    title = best_match.get("title")
    year = best_match.get("year", "Bilinmiyor")
    overview = best_match.get("overview", "Açıklama bulunmuyor.")
    if len(overview) > 250:
        overview = overview[:250] + "..."

    # Kullanıcı için bekleyen isteği kaydet
    PENDING_REQUESTS[user_id] = best_match

    # Kalite butonları (1080p, Kompakt 2160p, Full 2160p)
    keyboard = [
        [
            InlineKeyboardButton("🎬 1080p (Full HD)", callback_data=f"qual_4_{user_id}")
        ],
        [
            InlineKeyboardButton("⚡ Kompakt 2160p (4K ~7GB)", callback_data=f"qual_7_{user_id}"),
            InlineKeyboardButton("👑 Full 2160p (4K Master ~20GB)", callback_data=f"qual_5_{user_id}")
        ],
        [
            InlineKeyboardButton("❌ İptal", callback_data=f"qual_cancel_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"🎬 *{title} ({year})* bulundu!\n\n"
        f"📖 _{overview}_\n\n"
        "📥 *Hangi kalitede indirmek istersiniz?*\n"
        "• `1080p` : Standart Full HD (Hızlı ve hafif)\n"
        "• `Kompakt 2160p` : 4K çözünürlük (~7 GB, disk ve upload dostu)\n"
        "• `Full 2160p` : Gerçek Stüdyo 4K (~20 GB, kayıpsız Atmos/HDR)"
    )
    await search_msg.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def quality_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = update.effective_user.id

    if data.startswith("qual_cancel_"):
        PENDING_REQUESTS.pop(user_id, None)
        await query.edit_message_text("❌ Film isteği iptal edildi.")
        return

    if data.startswith("qual_"):
        parts = data.split("_")
        quality_id = int(parts[1])
        req_user_id = int(parts[2])

        if user_id != req_user_id:
            await query.answer("Bu seçimi yalnızca isteği yapan kişi kullanabilir.", show_alert=True)
            return

        movie_data = PENDING_REQUESTS.pop(user_id, None)
        if not movie_data:
            await query.edit_message_text("⚠️ İstek zaman aşımına uğradı, lütfen `/istek` ile tekrar aratın.")
            return

        title = movie_data.get("title")
        year = movie_data.get("year")
        
        if quality_id == 4:
            quality_name = "1080p Full HD"
        elif quality_id == 7:
            quality_name = "Kompakt 2160p (4K Hafif)"
        elif quality_id == 5:
            quality_name = "Full 2160p (4K Master)"
        else:
            quality_name = "Otomatik Kalite"

        await query.edit_message_text(f"⏳ *{title} ({year})* [{quality_name}] indirme sırasına ekleniyor...", parse_mode="Markdown")

        res = radarr.add_movie(movie_data, quality_profile_id=quality_id)
        if res.get("success"):
            reply = (
                f"✅ *{title} ({year})* [{quality_name}] başarıyla indirme sırasına eklendi!\n\n"
                "qBittorrent indirmeye başladı. İlerlemeyi canlı izlemek için `/durum` yazabilirsiniz."
            )
        else:
            err = res.get("error", "Bilinmeyen hata")
            if "already been added" in err.lower():
                reply = f"ℹ️ *{title} ({year})* zaten kütüphanede veya indirme kuyruğunda mevcut."
            else:
                reply = f"⚠️ Hata oluştu: {err}"

        await query.edit_message_text(reply, parse_mode="Markdown")

async def live_tracker_task(chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Her 2.5 saniyede bir aynı mesajı güncelleyerek canlı ilerleme gösterir."""
    logger.info(f"Canlı takipçi başlatıldı: Chat {chat_id}")
    last_text = ""
    unchanged_count = 0

    try:
        while True:
            torrents = radarr.get_live_torrents()

            if not torrents:
                # İnen torrent yoksa veya bittiyse
                finish_text = (
                    "🎉 *Tüm İndirmeler Tamamlandı!*\n\n"
                    "Dosyalar organize edilip Plex kütüphanesine aktarılıyor. İyi seyirler! 🍿"
                )
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=finish_text,
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
                break

            msg = "📡 *CineNode Canlı İndirme Takibi:*\n\n"
            for t in torrents[:4]:
                name = t["name"]
                if len(name) > 35:
                    name = name[:35] + "..."
                prog = t["progress"]
                bar = render_progress_bar(prog, 12)
                speed = t["dlspeed"]
                left = t["amount_left"]
                size = t["size"]
                eta_str = format_eta(t["eta"])

                msg += (
                    f"🎬 *{name}*\n"
                    f"`[{bar}]` *%{prog}*\n"
                    f"⚡ Hız: `{speed} MB/s` | 💾 Kalan: `{left} GB` / `{size} GB`\n"
                    f"⏳ Kalan Süre: `{eta_str}` | 🌱 Seed: `{t['seeds']}`\n\n"
                )

            now_str = datetime.now().strftime("%H:%M:%S")
            msg += f"_(Son güncelleme: {now_str} • Her ~2.5 sn canlı güncellenir)_"

            keyboard = [[InlineKeyboardButton("🛑 Canlı Takibi Durdur", callback_data=f"stop_track_{chat_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if msg != last_text:
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=msg,
                        reply_markup=reply_markup,
                        parse_mode="Markdown"
                    )
                    last_text = msg
                    unchanged_count = 0
                except Exception as e:
                    logger.debug(f"Canlı mesaj güncelleme atlandı: {e}")
            else:
                unchanged_count += 1
                if unchanged_count > 60: # 2.5 dakika boyunca hiç değişmediyse durdur
                    break

            await asyncio.sleep(2.5)

    except asyncio.CancelledError:
        logger.info(f"Canlı takip kullanıcı tarafından durduruldu: {chat_id}")
    finally:
        ACTIVE_TRACKERS.pop(chat_id, None)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Eğer önceden çalışan bir canlı takip varsa iptal et
    if chat_id in ACTIVE_TRACKERS:
        ACTIVE_TRACKERS[chat_id].cancel()

    torrents = radarr.get_live_torrents()
    if not torrents:
        await update.message.reply_text("💤 Şu anda aktif inen bir film bulunmuyor.")
        return

    # İlk mesajı at
    init_msg = await update.message.reply_text("🔄 Canlı indirme takibi başlatılıyor...", parse_mode="Markdown")

    # Arka plan canlı güncelleme task'ını başlat
    task = asyncio.create_task(live_tracker_task(chat_id, init_msg.message_id, context))
    ACTIVE_TRACKERS[chat_id] = task

async def stop_track_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Canlı takip durduruldu.")
    chat_id = update.effective_chat.id

    if chat_id in ACTIVE_TRACKERS:
        ACTIVE_TRACKERS[chat_id].cancel()
        ACTIVE_TRACKERS.pop(chat_id, None)

    try:
        await query.edit_message_text("⏹️ Canlı takip durduruldu. Tekrar başlatmak için `/durum` yazabilirsiniz.")
    except Exception:
        pass

async def shift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()

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
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN bulunamadı.")
        return

    # Scheduler
    setup_scheduler(plex)

    # Telegram Bot
    request = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = ApplicationBuilder().token(token).request(request).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("yardim", help_command))
    app.add_handler(CommandHandler("istek", request_command))
    app.add_handler(CommandHandler("durum", status_command))
    app.add_handler(CommandHandler("vardiya", shift_command))
    app.add_handler(CallbackQueryHandler(quality_callback_handler, pattern=r"^qual_"))
    app.add_handler(CallbackQueryHandler(stop_track_callback, pattern=r"^stop_track_"))

    logger.info("CineBot hazır ve dinliyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
