import os
import requests
from typing import List, Dict, Any, Optional

class RadarrClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or os.getenv("RADARR_BASE_URL", "http://localhost:7878")).rstrip("/")
        self.api_key = api_key or os.getenv("RADARR_API_KEY", "")
        self.headers = {
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json"
        }

    def search_movie(self, title: str) -> List[Dict[str, Any]]:
        """Radarr üzerinde film arar."""
        if not self.api_key:
            return []
        url = f"{self.base_url}/api/v3/movie/lookup"
        response = requests.get(url, headers=self.headers, params={"term": title}, timeout=10)
        if response.status_code == 200:
            return response.json()
        return []

    def add_movie(self, movie_data: Dict[str, Any], root_folder: str = "/data/movies", quality_profile_id: int = 1) -> Dict[str, Any]:
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
        response = requests.post(url, headers=self.headers, json=payload, timeout=10)
        if response.status_code in [200, 201]:
            return {"success": True, "movie": response.json()}
        return {"success": False, "error": response.text}

    def get_queue(self) -> List[Dict[str, Any]]:
        """Radarr'da aktif inen kuyruğu döner."""
        if not self.api_key:
            return []
        url = f"{self.base_url}/api/v3/queue"
        response = requests.get(url, headers=self.headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("records", [])
        return []
