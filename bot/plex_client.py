import os
import logging
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount

load_dotenv()
logger = logging.getLogger(__name__)

class PlexManager:
    def __init__(self, base_url: Optional[str] = None, token: Optional[str] = None):
        self.base_url = base_url or os.getenv("PLEX_BASE_URL", "http://localhost:32400")
        self.token = token or os.getenv("PLEX_TOKEN", "")
        self.server: Optional[PlexServer] = None
        self.account: Optional[MyPlexAccount] = None
        self._init_connection()

    def _get_lan_ip(self) -> str:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
        finally:
            s.close()

    def _sync_custom_connections(self):
        """Host makinenin yerel IP'si değiştikçe Plex customConnections ayarını günceller."""
        if not self.server:
            return
        try:
            lan_ip = self._get_lan_ip()
            if not lan_ip or lan_ip.startswith("127."):
                return
            current = self.server.settings.get("customConnections").value or ""
            if lan_ip not in current:
                expected = f"http://{lan_ip}:32400,https://{lan_ip}:32400"
                put_url = f"{self.base_url}/:/prefs?customCertificatePath=&customConnections={expected}"
                requests.put(put_url, headers={"X-Plex-Token": self.token}, timeout=5)
                logger.info(f"Plex customConnections otomatik güncellendi: {expected}")
        except Exception as e:
            logger.debug(f"Plex IP senkronizasyon hatası: {e}")

    def _init_connection(self):
        if not self.token:
            logger.warning("PLEX_TOKEN tanımlanmadığı için PlexManager pasif modda.")
            return
        try:
            self.server = PlexServer(self.base_url, self.token)
            self.account = self.server.myPlexAccount()
            logger.info("Plex sunucusuna başarıyla bağlanıldı.")
            self._sync_custom_connections()
        except Exception as e:
            logger.error(f"Plex bağlantı hatası: {e}")

    def set_user_access(self, user_emails: List[str], allow_access: bool) -> Dict[str, bool]:
        """
        Kullanıcıların kütüphane paylaşım izinlerini açar veya kapatır.
        Time-sharing mantığının çekirdek fonksiyonudur.
        """
        results = {}
        if not self.server or not self.account:
            self._init_connection()
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
            self._init_connection()
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
