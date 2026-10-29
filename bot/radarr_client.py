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

    def get_existing_movie(self, tmdb_id: Optional[int] = None, title: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Kütüphanede bu filmin zaten var olup olmadığını döner."""
        if not self.api_key:
            return None
        url = f"{self.base_url}/api/v3/movie"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                movies = res.json()
                for m in movies:
                    if tmdb_id and m.get("tmdbId") == tmdb_id:
                        return m
                    if title and m.get("title", "").strip().lower() == title.strip().lower():
                        return m
        except Exception as e:
            print(f"Radarr film listesi sorgulama hatası: {e}")
        return None

    def get_movie_by_id(self, movie_id: int) -> Optional[Dict[str, Any]]:
        """ID'ye göre film detayını çeker."""
        url = f"{self.base_url}/api/v3/movie/{movie_id}"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            print(f"Radarr film detayı hatası: {e}")
        return None

    def delete_movie_file(self, movie_file_id: int) -> bool:
        """Radarr üzerindeki film dosyasını ve fiziksel diskteki kopyasını siler."""
        url = f"{self.base_url}/api/v3/moviefile/{movie_file_id}"
        try:
            res = requests.delete(url, headers=self.headers, timeout=10)
            return res.status_code in [200, 204]
        except Exception as e:
            print(f"Radarr dosya silme hatası: {e}")
            return False

    def upgrade_movie_quality(self, movie_id: int, new_quality_profile_id: int, target_root_folder: str, delete_existing_file: bool = True) -> Dict[str, Any]:
        """Film kalite profilini günceller, eski dosyayı siler ve yeni kalite için arama tetikler."""
        movie = self.get_movie_by_id(movie_id)
        if not movie:
            return {"success": False, "error": "Film bulunamadı."}

        # 1. Eski dosya varsa diskten sil (anında yer aç)
        if delete_existing_file:
            movie_file_id = movie.get("movieFileId") or (movie.get("movieFile") or {}).get("id")
            if movie_file_id:
                deleted = self.delete_movie_file(movie_file_id)
                if not deleted:
                    print(f"Uyarı: movie_file_id {movie_file_id} silinemedi.")

        # 2. Kalite profili ve kök klasörü güncelle
        movie["qualityProfileId"] = new_quality_profile_id
        movie["monitored"] = True
        if target_root_folder:
            movie["rootFolderPath"] = target_root_folder
            folder_name = os.path.basename(movie.get("path", "").rstrip("/\\"))
            if not folder_name:
                folder_name = f"{movie.get('title')} ({movie.get('year')})"
            movie["path"] = f"{target_root_folder.rstrip('/')}/{folder_name}"

        put_url = f"{self.base_url}/api/v3/movie/{movie_id}"
        try:
            put_res = requests.put(put_url, headers=self.headers, json=movie, timeout=10)
            if put_res.status_code not in [200, 202]:
                return {"success": False, "error": f"Güncelleme başarısız: {put_res.text}"}

            # 3. Yeni kalite için otomatik arama tetikle
            cmd_url = f"{self.base_url}/api/v3/command"
            cmd_res = requests.post(
                cmd_url,
                headers=self.headers,
                json={"name": "MoviesSearch", "movieIds": [movie_id]},
                timeout=10
            )
            return {"success": True, "movie": put_res.json(), "command": cmd_res.json() if cmd_res.status_code in [200, 201] else {}}
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
