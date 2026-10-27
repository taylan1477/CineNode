import os
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

load_dotenv()

class RadarrClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.getenv("RADARR_BASE_URL", "http://localhost:7878")).rstrip("/")
        self.api_key = api_key or os.getenv("RADARR_API_KEY", "")
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }
        self.qbit_url = f"http://{os.getenv('QBIT_HOST', 'localhost')}:{os.getenv('QBIT_PORT', '8080')}"

    def search_movie(self, title: str) -> List[Dict[str, Any]]:
        """Radarr üzerinde film arar."""
        if not self.api_key:
            return []
        url = f"{self.base_url}/api/v3/movie/lookup"
        try:
            response = requests.get(url, headers=self.headers, params={"term": title}, timeout=10)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Radarr arama hatası: {e}")
        return []

    def add_movie(self, movie_data: Dict[str, Any], root_folder: str = "/data/movies", quality_profile_id: int = 4) -> Dict[str, Any]:
        """Radarr kütüphanesine film ekler ve arama tetikler."""
        url = f"{self.base_url}/api/v3/movie"
        payload = {
            "title": movie_data.get("title"),
            "qualityProfileId": quality_profile_id,
            "titleSlug": movie_data.get("titleSlug"),
            "images": movie_data.get("images", []),
            "tmdbId": movie_data.get("tmdbId"),
            "year": movie_data.get("year"),
            "rootFolderPath": root_folder,
            "monitored": True,
            "addOptions": {
                "searchForMovie": True
            }
        }
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                return {"success": True, "movie": response.json()}
            return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_live_torrents(self) -> List[Dict[str, Any]]:
        """qBittorrent'ten anlık canlı indirme hızlarını ve ilerlemeleri döner."""
        try:
            res = requests.get(f"{self.qbit_url}/api/v2/torrents/info", timeout=5)
            if res.status_code == 200:
                torrents = res.json()
                active = []
                for t in torrents:
                    if t.get("state") in ["downloading", "stalledDL", "queuedDL", "forcedDL"]:
                        active.append({
                            "name": t.get("name"),
                            "progress": round(t.get("progress", 0) * 100, 1),
                            "dlspeed": round(t.get("dlspeed", 0) / (1024 * 1024), 2),
                            "eta": t.get("eta", 0),
                            "size": round(t.get("size", 0) / (1024 * 1024 * 1024), 2),
                            "amount_left": round(t.get("amount_left", 0) / (1024 * 1024 * 1024), 2),
                            "seeds": t.get("num_seeds", 0)
                        })
                return active
        except Exception as e:
            print(f"qBittorrent canlı veri hatası: {e}")
        return []
