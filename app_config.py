# FILE: app_config.py
# PURPOSE: Centraliza o gerenciamento de configurações, caminhos e variáveis.

import os
import json
import platform

class AppConfig:
    _DEFAULT_VALUES = {
        'device_id': None,
        'theme': 'superhero',
        'device_commercial_name': 'Unknown Device',
        'start_app': '',
        'start_app_name': 'None',
        'mouse_mode': 'sdk',
        'gamepad_mode': 'disabled',
        'keyboard_mode': 'sdk',
        'mouse_bind': '++++:bhsn',
        'render_driver': 'opengl',
        'max_fps': '60',
        'max_size': '0',
        'display': 'Auto',
        'new_display': 'Disabled',
        'video_codec': 'Auto',
        'video_encoder': 'Auto',
        'audio_codec': 'Auto',
        'audio_encoder': 'Auto',
        'allow_frame_drop': 'enabled',
        'low_latency': 'enabled',
        'priority_mode': 'realtime',
        'bitrate_mode': 'cbr',
        'extraargs': '',
        'stay_awake': False,
        'mipmaps': False,
        'turn_screen_off': False,
        'fullscreen': False,
        'use_ludashi_pkg': False,
        'no_audio': False,
        'no_video': False,
        'video_bitrate_slider': 3000,
        'audio_buffer': 5,
        'video_buffer': 0,
    }
    GLOBAL_KEYS = {'theme', 'use_ludashi_pkg'}

    """
    Gerencia todas as configurações do aplicativo, incluindo caminhos de arquivos,
    metadados de apps e o estado da interface.
    """
    def __init__(self, device_id):
        self.config_data = {}
        self.values = self._DEFAULT_VALUES.copy() # Initialize with default values
        self.CONFIG_FILE = None # Initialize CONFIG_FILE to None

        if platform.system() == "Windows":
            self.CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'ScrcpyLauncher')
        else:
            self.CONFIG_DIR = os.path.expanduser("~/.config/yaScrcpy")

        os.makedirs(self.CONFIG_DIR, exist_ok=True)
        self.ICON_CACHE_DIR = os.path.join(self.CONFIG_DIR, 'icon_cache')
        os.makedirs(self.ICON_CACHE_DIR, exist_ok=True)

        self.GLOBAL_CONFIG_FILE = os.path.join(self.CONFIG_DIR, 'global_config.json')
        self.global_config_data = self._load_json(self.GLOBAL_CONFIG_FILE)

        # Apply global settings from loaded global_config_data
        for key in self.GLOBAL_KEYS:
            if key in self.global_config_data:
                self.values[key] = self.global_config_data[key]

    def get(self, key, default=None):
        """
        FIX: Retorna o valor da configuração para uma dada chave, com um padrão opcional.
        Agora a função se comporta como um dicionário .get(), tornando-a mais flexível.
        """
        return self.values.get(key, default)

    def set(self, key, value):
        """Define o valor de uma configuração e salva as alterações, se um arquivo de configuração estiver ativo."""
        if key in self.values:
            if self.values[key] != value:
                self.values[key] = value
                self.save_config()
        else:
            print(f"Warning: Attempted to set unknown config key: {key}")

    def get_all_values(self):
        """Retorna um dicionário com os valores atuais de todas as configurações."""
        return self.values

    def _load_json(self, file_path):
        """Carrega um arquivo JSON genérico."""
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_json(self, data, file_path):
        """Salva dados em um arquivo JSON genérico, verificando se o caminho é válido.""" 
        if file_path is None:
            print("Warning: Attempted to save to a None file_path.")
            return
        try:
            with open(file_path, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            print(f"Error saving config to {file_path}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while saving config to {file_path}: {e}")

    def save_config(self):
        """
        Salva o estado atual das variáveis, separando as configurações
        globais das configurações por dispositivo em seus respectivos arquivos.
        """
        all_values = self.get_all_values()
        global_settings = {key: all_values[key] for key in self.GLOBAL_KEYS if key in all_values}
        device_settings = {key: val for key, val in all_values.items() if key not in self.GLOBAL_KEYS}
        self.global_config_data = global_settings
        self._save_json(self.global_config_data, self.GLOBAL_CONFIG_FILE)
        
        if self.CONFIG_FILE is not None:
            self.config_data['general_config'] = device_settings
            self._save_json(self.config_data, self.CONFIG_FILE)

    def _ensure_metadata_structure(self, key):
        if 'app_metadata' not in self.config_data:
            self.config_data['app_metadata'] = {}
        if key not in self.config_data['app_metadata']:
            self.config_data['app_metadata'][key] = {}

    def get_app_metadata(self, key):
        """Retorna os metadados para uma chave específica (pkg_name, path, etc.)."""
        return self.config_data.get('app_metadata', {}).get(key, {})

    def save_app_metadata(self, key, data):
        """Salva ou atualiza os metadados para uma chave específica."""
        self._ensure_metadata_structure(key)
        self.config_data['app_metadata'][key].update(data)
        self._save_json(self.config_data, self.CONFIG_FILE)

    # ... O resto do arquivo app_config.py permanece o mesmo ...
    # Cole o conteúdo inteiro para garantir.
    def save_app_scrcpy_config(self, pkg_name, config_data):
        self._ensure_metadata_structure(pkg_name)
        self.config_data['app_metadata'][pkg_name]['config'] = config_data
        self._save_json(self.config_data, self.CONFIG_FILE)

    def delete_app_scrcpy_config(self, pkg_name):
        if 'app_metadata' in self.config_data and pkg_name in self.config_data['app_metadata'] and 'config' in self.config_data['app_metadata'][pkg_name]:
            del self.config_data['app_metadata'][pkg_name]['config']
            self._save_json(self.config_data, self.CONFIG_FILE)
            return True
        return False

    def get_app_list_cache(self):
        return self.config_data.get('app_list_cache', {})

    def save_app_list_cache(self, apps):
        self.config_data['app_list_cache'] = apps
        self._save_json(self.config_data, self.CONFIG_FILE)

    def get_winlator_game_config(self, game_path):
        return self.config_data.get('winlator_game_configs', {}).get(game_path, {})

    def save_winlator_game_config(self, game_path, config):
        # MODIFICAÇÃO: Remove 'use_ludashi_pkg' antes de salvar a configuração do jogo
        config_to_save = config.copy() # Cria uma cópia para não modificar o original
        if 'use_ludashi_pkg' in config_to_save:
            del config_to_save['use_ludashi_pkg']

        if 'winlator_game_configs' not in self.config_data:
            self.config_data['winlator_game_configs'] = {}
        self.config_data['winlator_game_configs'][game_path] = config_to_save
        self._save_json(self.config_data, self.CONFIG_FILE)

    def delete_winlator_game_config(self, game_path):
        if 'winlator_game_configs' in self.config_data and game_path in self.config_data['winlator_game_configs']:
            del self.config_data['winlator_game_configs'][game_path]
            self._save_json(self.config_data, self.CONFIG_FILE)
            return True
        return False

    def get_icon_cache_dir(self):
        return self.ICON_CACHE_DIR

    def get_encoder_cache(self):
        return self.config_data.get('encoder_cache', {})

    def save_encoder_cache(self, video_encoders, audio_encoders):
        self.config_data['encoder_cache'] = {
            'video': video_encoders,
            'audio': audio_encoders
        }
        self._save_json(self.config_data, self.CONFIG_FILE)

    def has_encoder_cache(self):
        if self.CONFIG_FILE is None:
            return False
        cache = self.get_encoder_cache()
        return bool(cache.get('video') or cache.get('audio'))

    def load_config_for_device(self, device_id):
        if device_id is None or device_id == "no_device":
            self.CONFIG_FILE = None
            self.config_data = {}
            default_values = AppConfig._DEFAULT_VALUES.copy()
            self.values = {k: v for k, v in default_values.items()}
            # Garante que as chaves globais sejam carregadas do global_config_data
            for key in self.GLOBAL_KEYS:
                self.values[key] = self.global_config_data.get(key, default_values.get(key))
            self.values['device_id'] = None
            return False

        self.CONFIG_FILE = os.path.join(self.CONFIG_DIR, f'config_{device_id}.json')
        self.config_data = self._load_json(self.CONFIG_FILE)
        self.config_data.setdefault('general_config', {})
        self.config_data.setdefault('app_metadata', {})
        self.config_data.setdefault('app_list_cache', {})
        self.config_data.setdefault('winlator_game_configs', {})
        self.config_data.setdefault('encoder_cache', {})

        general_config = self.config_data['general_config']
        default_values = AppConfig._DEFAULT_VALUES.copy()

        for key, default_value in default_values.items():
            if key in self.GLOBAL_KEYS:
                # Chaves globais são carregadas do global_config_data, não do config do dispositivo
                self.values[key] = self.global_config_data.get(key, default_value)
            else:
                self.values[key] = general_config.get(key, default_value)
        
        self.values['device_id'] = device_id

        return True