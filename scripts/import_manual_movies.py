import requests
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('RADARR_BASE_URL', 'http://localhost:7878').rstrip('/')
key = os.getenv('RADARR_API_KEY')
headers = {'X-Api-Key': key}

movies_to_add = [
    {
        'title': 'Dune',
        'year': 2021,
        'tmdbId': 438631,
        'qualityProfileId': 5,
        'rootFolderPath': '/media/movies_4k',
        'folderName': 'Dune - Part One (2021)'
    },
    {
        'title': 'Dune: Part Two',
        'year': 2024,
        'tmdbId': 693134,
        'qualityProfileId': 7,
        'rootFolderPath': '/media/movies_4k',
        'folderName': 'Dune - Part Two (2024)'
    },
    {
        'title': 'Evil Dead II',
        'year': 1987,
        'tmdbId': 765,
        'qualityProfileId': 4,
        'rootFolderPath': '/media/movies_1080p',
        'folderName': 'Evil Dead II (1987)'
    },
    {
        'title': 'Matango',
        'year': 1963,
        'tmdbId': 52302,
        'qualityProfileId': 4,
        'rootFolderPath': '/media/movies_1080p',
        'folderName': 'Matango (1963)'
    }
]

for m in movies_to_add:
    lookup = requests.get(f'{url}/api/v3/movie/lookup/tmdb', headers=headers, params={'tmdbId': m['tmdbId']}).json()
    folder_path = f"{m['rootFolderPath']}/{m['folderName']}"
    payload = {
        'title': lookup.get('title'),
        'qualityProfileId': m['qualityProfileId'],
        'titleSlug': lookup.get('titleSlug'),
        'images': lookup.get('images', []),
        'tmdbId': m['tmdbId'],
        'year': lookup.get('year'),
        'rootFolderPath': m['rootFolderPath'],
        'path': folder_path,
        'monitored': True,
        'addOptions': {
            'searchForMovie': False,
            'monitor': 'movieOnly'
        }
    }
    res = requests.post(f'{url}/api/v3/movie', headers=headers, json=payload)
    print(m['title'], 'status:', res.status_code)
    if res.status_code in [200, 201]:
        new_m = res.json()
        print('  Added ID:', new_m['id'])
        cmd_res = requests.post(f'{url}/api/v3/command', headers=headers, json={'name': 'RescanMovie', 'movieId': new_m['id']})
        print('  Rescan:', cmd_res.status_code)
    else:
        print('  Response:', res.text[:200])
