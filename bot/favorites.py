import os
import json
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("CineFavorites")

FAVORITES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "favorites.json")

# Kota Puanları: Full 4K (4p), Kompakt 4K (2p), 1080p (1p). Toplam limit: 4 puan.
# 1 Full 4K = 4p
# 2 Kompakt 4K = 2 * 2p = 4p
# 4 1080p = 4 * 1p = 4p
QUALITY_POINTS = {
    5: 4,  # Full 2160p Master
    7: 2,  # Kompakt 2160p
    4: 1,  # 1080p Full HD
}

class FavoritesManager:
    def __init__(self, filepath: str = FAVORITES_FILE):
        self.filepath = filepath
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump({"favorites": {}}, f, indent=2, ensure_ascii=False)

    def load(self) -> Dict[str, Any]:
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Favorites yüklenirken hata: {e}")
            return {"favorites": {}}

    def save(self, data: Dict[str, Any]):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Favorites kaydedilirken hata: {e}")

    def get_quality_points(self, quality_profile_id: int) -> int:
        return QUALITY_POINTS.get(quality_profile_id, 1)

    def is_favorite(self, movie_id: int) -> bool:
        data = self.load()
        return str(movie_id) in data.get("favorites", {})

    def get_favorite(self, movie_id: int) -> Optional[Dict[str, Any]]:
        data = self.load()
        return data.get("favorites", {}).get(str(movie_id))

    def get_user_favorites(self, user_id: int) -> list[Dict[str, Any]]:
        data = self.load()
        return [fav for fav in data.get("favorites", {}).values() if fav.get("user_id") == user_id]

    def get_user_used_points(self, user_id: int) -> int:
        user_favs = self.get_user_favorites(user_id)
        return sum(fav.get("points", 1) for fav in user_favs)

    def can_add_favorite(self, user_id: int, quality_profile_id: int) -> Tuple[bool, str]:
        cost = self.get_quality_points(quality_profile_id)
        used = self.get_user_used_points(user_id)
        total_limit = 4

        if used + cost > total_limit:
            return False, (
                f"⛔ Favori kotanız yetersiz!\n"
                f"• Kotanız: {used}/{total_limit} puan dolu.\n"
                f"• Bu film {cost} puan gerektiriyor (Toplam {used + cost}/{total_limit} olur).\n\n"
                "📌 Kota Kuralları:\n"
                "• 1 Full 4K = 4 puan\n"
                "• 2 Kompakt 4K = 2x2 = 4 puan\n"
                "• 4 1080p = 4x1 = 4 puan"
            )
        return True, ""

    def add_favorite(self, movie_id: int, title: str, user_id: int, user_name: str, quality_profile_id: int) -> Tuple[bool, str]:
        if self.is_favorite(movie_id):
            return False, "Bu film zaten favorilerde ekli."

        can_add, reason = self.can_add_favorite(user_id, quality_profile_id)
        if not can_add:
            return False, reason

        cost = self.get_quality_points(quality_profile_id)
        data = self.load()
        data.setdefault("favorites", {})[str(movie_id)] = {
            "movie_id": movie_id,
            "title": title,
            "user_id": user_id,
            "user_name": user_name,
            "quality_profile_id": quality_profile_id,
            "points": cost
        }
        self.save(data)
        used = self.get_user_used_points(user_id)
        return True, f"⭐ *{title}* favoriye eklendi! (Kullanılan kota: {used}/4 puan)"

    def remove_favorite(self, movie_id: int, user_id: int, is_admin: bool = False) -> Tuple[bool, str]:
        data = self.load()
        fav = data.get("favorites", {}).get(str(movie_id))
        if not fav:
            return False, "Bu film favorilerde bulunamadı."

        if fav.get("user_id") != user_id and not is_admin:
            return False, f"⛔ Bu film @{fav.get('user_name', 'bir kullanıcı')} tarafından favorilenmiş. Yalnızca favorileyen kişi veya admin kaldırabilir."

        del data["favorites"][str(movie_id)]
        self.save(data)
        used = self.get_user_used_points(user_id)
        return True, f"⭐ *{fav.get('title')}* favorilerden kaldırıldı. (Kalan kota kullanımınız: {used}/4 puan)"

    def can_delete_movie(self, movie_id: int, user_id: int, is_admin: bool = False) -> Tuple[bool, str]:
        fav = self.get_favorite(movie_id)
        if not fav:
            return True, ""  # Favori değilse herkes silebilir

        if fav.get("user_id") == user_id or is_admin:
            return True, ""  # Favorileyen kişi veya admin silebilir

        user_name = fav.get("user_name", "bir kullanıcı")
        return False, f"🔒 Bu film @{user_name} tarafından favoriye alınmıştır! Favorilenen filmler silinemez. Yalnızca favorileyen kişi veya sunucu admini silebilir."
