# FILE: utils/icon_scraper.py
# PURPOSE: Faz o download e cache de ícones de aplicativos da Google Play Store.

import os
import requests
import re
from PIL import Image

def get_icon(app_name, package_name, cache_dir, app_config, download_if_missing=True):
    """
    Obtém o ícone de um app. Se `download_if_missing` for True, tenta baixar.
    Retorna o caminho para o ícone em cache ou None.
    """
    icon_path = os.path.join(cache_dir, f"{package_name}.png")

    if os.path.exists(icon_path):
        return icon_path

    # Se não for para baixar, ou se já falhou antes, não continua.
    metadata = app_config.get_app_metadata(package_name)
    if not download_if_missing or metadata.get('icon_fetch_failed'):
        return None

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        url = f"https://play.google.com/store/apps/details?id={package_name}&hl=en&gl=US"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        # Regex mais robusta que busca pela meta tag og:image.
        match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', response.text)
        if not match:
            print(f"Icon URL pattern not found for {package_name}")
            app_config.save_app_metadata(package_name, {"icon_fetch_failed": True})
            return None

        icon_url = match.group(1).replace('=s180-rw', '=s128-rw')

        icon_response = requests.get(icon_url, stream=True)
        icon_response.raise_for_status()

        with open(icon_path, 'wb') as f:
            for chunk in icon_response.iter_content(1024):
                f.write(chunk)

        img = Image.open(icon_path)
        img.save(icon_path, "PNG")

        # Marca que o download foi bem-sucedido (ou pelo menos não falhou)
        app_config.save_app_metadata(package_name, {"icon_fetch_failed": False})
        return icon_path

    except requests.exceptions.RequestException as e:
        print(f"Failed to download icon for {package_name}: {e}")
        app_config.save_app_metadata(package_name, {"icon_fetch_failed": True})
        return None
    except Exception as e:
        print(f"An error occurred while processing icon for {package_name}: {e}")
        app_config.save_app_metadata(package_name, {"icon_fetch_failed": True})
        return None
