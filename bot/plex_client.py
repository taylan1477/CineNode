import os
import logging
from typing import List, Dict, Any, Optional
from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount

logger = logging.getLogger(__name__)

class PlexManager:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url or os.getenv("PLEX_BASE_URL", "http://localhost:32400")
        self.token = token or os.getenv("PLEX_TOKEN", "")
        self.server: Optional[PlexServer] = None
        self.account: Optional[MyPlexAccount] = None
        self._init_connection()

    def _init_connection(self):
        if not self.token:
            logger.warning("PLEX_TOKEN tanımlanmadığı için PlexManager pasif modda.")
            return
        try:
            self.server = PlexServer(self.base_url, self.token)
            self.account = self.server.myPlexAccount()
            logger.info("Plex sunucusuna başarıyla bağlanıldı.")
        except Exception as e:
            logger.error(f"Plex bağlantı hatası: {e}")

    def set_user_access(self, user_emails: List[str], allow_access: bool) -> Dict[str, bool]:
        """
        Kullanıcıların kütüphane paylaşım izinlerini açar veya kapatır.
        Time-sharing mantığının çekirdek fonksiyonudur.
        """
        results = {}
        if not self.server or not self.account:
            return {email: False for email in user_emails}

        try:
            # Paylaşılan kütüphaneleri al
            sections = self.server.library.sections()
            section_names = [s.title for s in sections]

            for email in user_emails:
                clean_email = email.strip()
                if not clean_email:
                    continue
                try:
                    # Kullanıcıyı arkadaş listesinde bul
                    user = self.account.user(clean_email)
                    if allow_access:
                        # Kütüphaneleri paylaş
                        self.account.updateFriend(user, self.server, sections=section_names)
                        logger.info(f"Erişim AÇILDI: {clean_email}")
                    else:
                        # Kütüphane listesini boşaltarak erişimi kes
                        self.account.updateFriend(user, self.server, sections=[])
                        logger.info(f"Erişim KAPATILDI (Askıya alındı): {clean_email}")
                    results[clean_email] = True
                except Exception as user_err:
                    logger.error(f"{clean_email} yetkilendirme hatası: {user_err}")
                    results[clean_email] = False
        except Exception as e:
            logger.error(f"Plex arkadaş listesi güncellenirken genel hata: {e}")

        return results

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Şu an aktif video izleyenleri döner."""
        if not self.server:
            return []
        try:
            sessions = self.server.sessions()
            return [
                {
                    "user": s.usernames[0] if s.usernames else "Bilinmiyor",
                    "title": s.title,
                    "type": s.type,
                    "player": s.players[0].title if s.players else "Bilinmiyor",
                    "state": s.players[0].state if s.players else "Bilinmiyor"
                }
                for s in sessions
            ]
        except Exception as e:
            logger.error(f"Aktif oturumlar alınamadı: {e}")
            return []
