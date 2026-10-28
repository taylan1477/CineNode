import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from bot.plex_client import PlexManager

logger = logging.getLogger(__name__)

def parse_user_list(env_var_name: str) -> list[str]:
    raw = os.getenv(env_var_name, "")
    return [u.strip() for u in raw.split(",") if u.strip()]

def activate_workers_shift(plex_manager: PlexManager):
    """Saat 18:00: Çalışanlar başlar, İşsizler durdurulur."""
    workers = parse_user_list("PLEX_USERS_WORKERS")
    unemployed = parse_user_list("PLEX_USERS_UNEMPLOYED")

    logger.info("=== [SHIFT DEĞİŞİMİ - 18:00] Çalışanlar Vardiyası Başlatılıyor ===")
    if unemployed:
        plex_manager.set_user_access(unemployed, allow_access=False)
    if workers:
        plex_manager.set_user_access(workers, allow_access=True)

def activate_unemployed_shift(plex_manager: PlexManager):
    """Saat 01:00: İşsizler (gece/gündüz kuşları) başlar, Çalışanlar durdurulur."""
    workers = parse_user_list("PLEX_USERS_WORKERS")
    unemployed = parse_user_list("PLEX_USERS_UNEMPLOYED")

    logger.info("=== [SHIFT DEĞİŞİMİ - 01:00] Gece/Gündüz Vardiyası Başlatılıyor ===")
    if workers:
        plex_manager.set_user_access(workers, allow_access=False)
    if unemployed:
        plex_manager.set_user_access(unemployed, allow_access=True)

def setup_scheduler(plex_manager: PlexManager) -> BackgroundScheduler:
    scheduler = BackgroundScheduler()

    # Hafta içi saat 18:00'de çalışanlar vardiyası
    scheduler.add_job(
        activate_workers_shift,
        trigger=CronTrigger(day_of_week="mon-fri", hour=18, minute=0),
        args=[plex_manager],
        id="shift_workers_1800",
        name="Vardiya Değişimi: Çalışanlar (18:00)",
        replace_existing=True
    )

    # Hafta içi saat 01:00'de işsizler vardiyası
    scheduler.add_job(
        activate_unemployed_shift,
        trigger=CronTrigger(day_of_week="mon-fri", hour=1, minute=0),
        args=[plex_manager],
        id="shift_unemployed_0100",
        name="Vardiya Değişimi: İşsizler (01:00)",
        replace_existing=True
    )

    # Hafta sonu: Her iki gruba da veya çalışanlara tam erişim kuralı
    # Hafta sonu başlangıcı (Cumartesi 00:00)
    scheduler.add_job(
        lambda: plex_manager.set_user_access(parse_user_list("PLEX_USERS_WORKERS"), allow_access=True),
        trigger=CronTrigger(day_of_week="sat,sun", hour=0, minute=0),
        id="weekend_workers_open",
        name="Hafta Sonu Çalışanlar Açık",
        replace_existing=True
    )

    # 2 dakikada bir inmiş filmleri otomatik kütüphaneye aktar ve Plex'i tara
    from bot.main import auto_import_completed_downloads
    scheduler.add_job(
        auto_import_completed_downloads,
        trigger="interval",
        minutes=2,
        id="auto_import_downloads",
        name="Otomatik Kütüphane Aktarımı ve Plex Taraması",
        replace_existing=True
    )

    # 2 dakikada bir tamamlanan torrentleri downloads klasöründen temizle (Duplicate engelleme)
    from bot.main import cleanup_completed_downloads
    scheduler.add_job(
        cleanup_completed_downloads,
        trigger="interval",
        minutes=2,
        id="auto_cleanup_downloads",
        name="Otomatik Downloads Duplicate Temizliği",
        replace_existing=True
    )

    scheduler.start()
    logger.info("Time-sharing scheduler görevleri başarıyla başlatıldı.")
    return scheduler
