import requests
import json

RADARR_KEY = "01de1613634642ffbe91d5049ff2967e"
PROWLARR_KEY = "f8a17479564d4a839d352a77bdac2a3c"

def configure_qbittorrent_in_radarr():
    print("[1] Radarr için qBittorrent Download Client yapılandırılıyor...")
    headers = {"X-Api-Key": RADARR_KEY, "Content-Type": "application/json"}
    
    # Mevcut download clientları kontrol et
    res = requests.get("http://localhost:7878/api/v3/downloadclient", headers=headers)
    clients = res.json()
    for c in clients:
        if c.get("name") == "qBittorrent (CineNode)":
            print("  -> qBittorrent zaten ekli.")
            return

    # Schema al
    schema_res = requests.get("http://localhost:7878/api/v3/downloadclient/schema", headers=headers)
    schemas = schema_res.json()
    qbit_schema = next((s for s in schemas if s.get("implementation") == "QBittorrent"), None)
    if not qbit_schema:
        print("  [!] QBittorrent şeması bulunamadı.")
        return

    qbit_schema["name"] = "qBittorrent (CineNode)"
    qbit_schema["enable"] = True
    
    field_map = {
        "host": "qbittorrent",
        "port": 8080,
        "username": "admin",
        "password": "R2Crjvc3n",
        "useSsl": False
    }
    
    for f in qbit_schema.get("fields", []):
        if f.get("name") in field_map:
            f["value"] = field_map[f["name"]]

    post_res = requests.post("http://localhost:7878/api/v3/downloadclient", headers=headers, json=qbit_schema)
    if post_res.status_code in [200, 201]:
        print("  -> qBittorrent başarıyla Radarr'a bağlandı!")
    else:
        print(f"  [!] qBittorrent eklenemedi: {post_res.status_code} - {post_res.text}")

def configure_radarr_in_prowlarr():
    print("[2] Prowlarr için Radarr senkronizasyonu yapılandırılıyor...")
    headers = {"X-Api-Key": PROWLARR_KEY, "Content-Type": "application/json"}

    # Mevcut uygulamaları kontrol et
    res = requests.get("http://localhost:9996/api/v1/applications", headers=headers)
    apps = res.json()
    for a in apps:
        if a.get("name") == "Radarr (CineNode)":
            print("  -> Radarr zaten Prowlarr'a ekli.")
            return

    # Schema al
    schema_res = requests.get("http://localhost:9996/api/v1/applications/schema", headers=headers)
    schemas = schema_res.json()
    radarr_schema = next((s for s in schemas if s.get("implementation") == "Radarr"), None)
    if not radarr_schema:
        print("  [!] Radarr uygulama şeması bulunamadı.")
        return

    radarr_schema["name"] = "Radarr (CineNode)"
    radarr_schema["syncLevel"] = "fullSync"
    
    field_map = {
        "prowlarrUrl": "http://prowlarr:9696",
        "baseUrl": "http://radarr:7878",
        "apiKey": RADARR_KEY
    }

    for f in radarr_schema.get("fields", []):
        if f.get("name") in field_map:
            f["value"] = field_map[f["name"]]

    post_res = requests.post("http://localhost:9996/api/v1/applications", headers=headers, json=radarr_schema)
    if post_res.status_code in [200, 201]:
        print("  -> Radarr başarıyla Prowlarr'a bağlandı (Full Sync)!")
    else:
        print(f"  [!] Radarr eklenemedi: {post_res.status_code} - {post_res.text}")

def add_public_indexers_in_prowlarr():
    print("[3] Prowlarr için popüler açık torrent trackerlar ekleniyor...")
    headers = {"X-Api-Key": PROWLARR_KEY, "Content-Type": "application/json"}
    
    # 1337x, YTS gibi açık trackerlar
    schema_res = requests.get("http://localhost:9996/api/v1/indexer/schema", headers=headers)
    schemas = schema_res.json()
    
    target_indexers = ["1337x", "YTS", "EZTV"]
    
    for target in target_indexers:
        schema = next((s for s in schemas if target.lower() in s.get("name", "").lower()), None)
        if schema:
            schema["enable"] = True
            schema["appProfileId"] = 1
            res = requests.post("http://localhost:9996/api/v1/indexer", headers=headers, json=schema)
            if res.status_code in [200, 201]:
                print(f"  -> Tracker eklendi: {target}")
            else:
                print(f"  [!] Tracker eklenemedi ({target}): {res.status_code}")

if __name__ == "__main__":
    configure_qbittorrent_in_radarr()
    configure_radarr_in_prowlarr()
    add_public_indexers_in_prowlarr()
