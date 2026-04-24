# FILE: app_config.py
# PURPOSE: Centraliza o gerenciamento de configurações, caminhos e variáveis.

import os
import json
import platform
import threading
from utils.constants import *

class AppConfig:
    _DEFAULT_VALUES = {
        CONF_DEVICE_ID: None,
        CONF_THEME: 'System',
        CONF_LANGUAGE: 'en',
        CONF_DEVICE_COMMERCIAL_NAME: 'Unknown Device',
        CONF_START_APP: '',
        CONF_START_APP_NAME: 'None',
        CONF_DEFAULT_LAUNCHER: None,
        CONF_MOUSE_MODE: 'sdk',
        CONF_GAMEPAD_MODE: 'disabled',
        CONF_KEYBOARD_MODE: 'sdk',
        CONF_MOUSE_BIND: '++++:bhsn',
        CONF_RENDER_DRIVER: 'opengl',
        CONF_MAX_FPS: '60',
        CONF_MAX_SIZE: '0',
        CONF_DISPLAY: 'Auto',
        CONF_NEW_DISPLAY: 'Disabled',
        CONF_VIDEO_CODEC: 'Auto',
        CONF_VIDEO_ENCODER: 'Auto',
        CONF_AUDIO_CODEC: 'Auto',
        CONF_AUDIO_ENCODER: 'Auto',
        CONF_ALLOW_FRAME_DROP: 'Enabled',
        CONF_LOW_LATENCY: 'Enabled',
        CONF_PRIORITY_MODE: 'Realtime',
        CONF_BITRATE_MODE: 'VBR',
        CONF_COLOR_RANGE: 'Auto',
        CONF_IFRAME_INTERVAL: 0,
        CONF_EXTRAARGS: '',
        CONF_STAY_AWAKE: False,
        CONF_MIPMAPS: False,
        CONF_TURN_SCREEN_OFF: False,
        CONF_FULLSCREEN: False,
        CONF_USE_LUDASHI_PKG: False,
        CONF_NO_AUDIO: False,
        CONF_NO_VIDEO: False,
        CONF_VIDEO_BITRATE_SLIDER: 3000,
        CONF_AUDIO_BUFFER: 5,
        CONF_AUDIO_BITRATE_SLIDER: 128,
        CONF_VIDEO_BUFFER: 0,
        CONF_TRY_UNLOCK: False,
        ALTERNATE_LAUNCH_METHOD: False,
        CONF_WINDOWING_MODE: 'Fullscreen',
        CONF_SHOW_SYSTEM_APPS: True,
        CONF_START_WEB_SERVER_ON_LAUNCH: False,
    }
    GLOBAL_KEYS = {CONF_THEME, CONF_LANGUAGE, CONF_SHOW_SYSTEM_APPS, CONF_START_WEB_SERVER_ON_LAUNCH}
    PROFILE_TYPES = {'app': CONF_APP_METADATA, 'winlator': CONF_WINLATOR_GAME_CONFIGS}


    @classmethod
    def all_known_keys(cls):
        return list(cls._DEFAULT_VALUES.keys())

    def tr(self, section, item, **kwargs):
        """Returns the translated string for the given section and item."""
        lang = self.get(CONF_LANGUAGE, 'en')
        try:
            # Handle nested translations if 'key' is provided in kwargs
            sub_key = kwargs.pop('key', None)
            if sub_key:
                text = TRANSLATIONS[lang][section][item][sub_key]
            else:
                text = TRANSLATIONS[lang][section][item]
            
            if kwargs:
                return text.format(**kwargs)
            return text
        except (KeyError, AttributeError):
            # Fallback to English if key is missing in the current language or language is invalid
            try:
                if sub_key:
                    text = TRANSLATIONS['en'][section][item][sub_key]
                else:
                    text = TRANSLATIONS['en'][section][item]
                
                if kwargs:
                    return text.format(**kwargs)
                return text
            except KeyError:
                return f"[{section}.{item}{'.' + sub_key if sub_key else ''}]"

    def __init__(self, device_id):
        self.config_data = {}
        self.values = self._DEFAULT_VALUES.copy()
        self.CONFIG_FILE = None
        self.active_profile = 'global'
        self.connection_id = None
        self.device_app_cache = {'installed_apps': set(), 'winlator_shortcuts': set()} # New attribute
        self._config_lock = threading.Lock() # Initialize the lock

        if platform.system() == "Windows":
            self.CONFIG_DIR = os.path.join(os.getenv('APPDATA'), 'ScrcpyLauncher')
        else:
            self.CONFIG_DIR = os.path.expanduser("~/.config/yaScrcpy")

        os.makedirs(self.CONFIG_DIR, exist_ok=True)
        self.ICON_CACHE_DIR = os.path.join(self.CONFIG_DIR, 'icon_cache')
        os.makedirs(self.ICON_CACHE_DIR, exist_ok=True)

        self.GLOBAL_CONFIG_FILE = os.path.join(self.CONFIG_DIR, 'global_config.json')
        self.global_config_data = self._load_json(self.GLOBAL_CONFIG_FILE)

        for key in self.GLOBAL_KEYS:
            if key in self.global_config_data:
                self.values[key] = self.global_config_data[key]

    def get(self, key, default=None):
        return self.values.get(key, default)

    def get_connection_id(self):
        return self.connection_id or self.get(CONF_DEVICE_ID)

    def get_global_values_no_profile(self):
        """
        Returns a dictionary of the global configuration values, ignoring any active profile.
        It combines defaults, global app settings, and global device settings.
        """
        # Start with the default values
        values = self._DEFAULT_VALUES.copy()

        # Load global settings from the global config file
        values.update(self.global_config_data)

        # Load device-specific general settings if a device is connected
        if self.CONFIG_FILE:
            values.update(self.config_data.get(CONF_GENERAL_CONFIG, {}))

        return values

    def set(self, key, value):
        if key in ['device_id', 'device_commercial_name']:
            print(f"Warning: Attempted to set immutable config key: {key}.")
            return

        if self.values.get(key) != value:
            self.values[key] = value
            self.save_config()

    def _load_json(self, file_path):
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_json(self, data, file_path):
        if file_path is None:
            print("Warning: Attempted to save to a None file_path.")
            return
        with self._config_lock: # Acquire the lock
            try:
                with open(file_path, "w", encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
            except IOError as e:
                print(f"Error saving config to {file_path}: {e}")

    def save_config(self):
        if self.CONFIG_FILE is None:
            # Save global settings even if no device is connected
            global_settings = {key: self.values[key] for key in self.GLOBAL_KEYS if key in self.values}
            self._save_json(global_settings, self.GLOBAL_CONFIG_FILE)
            return

        # Separate global from device-specific settings
        global_settings = {key: self.values[key] for key in self.GLOBAL_KEYS if key in self.values}
        device_settings = {k: v for k, v in self.values.items() if k not in self.GLOBAL_KEYS}

        # Save global settings
        self._save_json(global_settings, self.GLOBAL_CONFIG_FILE)

        # Save device-specific settings to the correct profile
        if self.active_profile == 'global':
            self.config_data[CONF_GENERAL_CONFIG] = device_settings
        elif self.active_profile in self.get_app_config_keys(include_name=False):
            self.save_app_scrcpy_config(self.active_profile, device_settings)
        elif self.active_profile in self.get_winlator_config_keys(include_name=False):
            self.save_winlator_game_config(self.active_profile, device_settings)

        self._save_json(self.config_data, self.CONFIG_FILE)


    def get_app_config_keys(self, include_name=True):
        if not self.config_data: return []
        keys = []
        app_metadata = self.config_data.get(CONF_APP_METADATA, {})
        for pkg_name, data in app_metadata.items():
            if 'config' in data:
                if include_name:
                    # Try to get a friendly name
                    app_list = self.get_app_list_cache().get('user_apps', [])
                    name = next((app['name'] for app in app_list if app['key'] == pkg_name), pkg_name)
                    keys.append((pkg_name, name))
                else:
                    keys.append(pkg_name)
        return sorted(keys, key=lambda x: x[1].lower() if include_name else x.lower())

    def get_winlator_config_keys(self, include_name=True):
        if not self.config_data: return []
        keys = []
        winlator_configs = self.config_data.get(CONF_WINLATOR_GAME_CONFIGS, {})
        for path, config in winlator_configs.items():
            if config: # Ensure there's actually a config
                if include_name:
                    name = os.path.splitext(os.path.basename(path))[0]
                    keys.append((path, name))
                else:
                    keys.append(path)
        return sorted(keys, key=lambda x: x[1].lower() if include_name else x.lower())


    def load_profile(self, profile_key):
        # Start with the base global config
        base_config = self.config_data.get(CONF_GENERAL_CONFIG, {}).copy()

        # Determine profile type and load specific config
        if profile_key == 'global':
            pass # Base config is enough
        elif profile_key in self.get_app_config_keys(include_name=False):
            specific_config = self.get_app_metadata(profile_key).get('config', {})
            base_config.update(specific_config)
        elif profile_key in self.get_winlator_config_keys(include_name=False):
            specific_config = self.get_winlator_game_config(profile_key)
            base_config.update(specific_config)
        else:
            print(f"Warning: Profile key '{profile_key}' not found. Loading global config.")
            profile_key = 'global'

        # Set the loaded values, preserving global keys
        default_values = self._DEFAULT_VALUES.copy()
        for key, default_value in default_values.items():
            if key in self.GLOBAL_KEYS:
                self.values[key] = self.global_config_data.get(key, default_value)
            else:
                self.values[key] = base_config.get(key, default_value)

        self.active_profile = profile_key
        print(f"Loaded profile: {self.active_profile}")


    def _ensure_metadata_structure(self, key):
        if CONF_APP_METADATA not in self.config_data:
            self.config_data[CONF_APP_METADATA] = {}
        if key not in self.config_data[CONF_APP_METADATA]:
            self.config_data[CONF_APP_METADATA][key] = {}

    def get_app_metadata(self, key):
        return self.config_data.get(CONF_APP_METADATA, {}).get(key, {})

    def save_app_metadata(self, key, data):
        self._ensure_metadata_structure(key)
        self.config_data[CONF_APP_METADATA][key].update(data)
        self._save_json(self.config_data, self.CONFIG_FILE)

    def save_app_scrcpy_config(self, pkg_name, config_data):
        # This single method will now handle global device settings and app-specific settings.
        
        # First, handle pure-global settings which are stored in a separate file
        pure_global_settings = {k: v for k, v in config_data.items() if k in self.GLOBAL_KEYS}
        if pure_global_settings:
            self.global_config_data.update(pure_global_settings)
            self._save_json(self.global_config_data, self.GLOBAL_CONFIG_FILE)

        # Then, handle device-specific settings
        device_settings = {k: v for k, v in config_data.items() if k not in self.GLOBAL_KEYS}

        if pkg_name == '__global__':
            # Save to the CONF_GENERAL_CONFIG for the current device
            if CONF_GENERAL_CONFIG not in self.config_data:
                self.config_data[CONF_GENERAL_CONFIG] = {}
            self.config_data[CONF_GENERAL_CONFIG].update(device_settings)
        else:
            # Save to a specific app's profile
            self._ensure_metadata_structure(pkg_name)
            if 'config' not in self.config_data[CONF_APP_METADATA][pkg_name]:
                self.config_data[CONF_APP_METADATA][pkg_name]['config'] = {}
            self.config_data[CONF_APP_METADATA][pkg_name]['config'].update(device_settings)
        
        # Save the main device config file
        self._save_json(self.config_data, self.CONFIG_FILE)

    def delete_app_scrcpy_config(self, pkg_name):
        if CONF_APP_METADATA in self.config_data and pkg_name in self.config_data[CONF_APP_METADATA] and 'config' in self.config_data[CONF_APP_METADATA][pkg_name]:
            del self.config_data[CONF_APP_METADATA][pkg_name]['config']
            if not self.config_data[CONF_APP_METADATA][pkg_name]: # cleanup if empty
                 del self.config_data[CONF_APP_METADATA][pkg_name]
            if self.active_profile == pkg_name:
                self.load_profile('global')
            self._save_json(self.config_data, self.CONFIG_FILE)
            return True
        return False

    def get_app_list_cache(self):
        return self.config_data.get(CONF_APP_LIST_CACHE, {})

    def save_app_list_cache(self, apps):
        self.config_data[CONF_APP_LIST_CACHE] = apps
        self._save_json(self.config_data, self.CONFIG_FILE)

    def get_winlator_game_config(self, game_path):
        return self.config_data.get(CONF_WINLATOR_GAME_CONFIGS, {}).get(game_path, {})

    def save_winlator_game_config(self, game_path, config):
        config_to_save = {k: v for k, v in config.items() if k not in self.GLOBAL_KEYS}
        if CONF_WINLATOR_GAME_CONFIGS not in self.config_data:
            self.config_data[CONF_WINLATOR_GAME_CONFIGS] = {}
        self.config_data[CONF_WINLATOR_GAME_CONFIGS][game_path] = config_to_save
        self._save_json(self.config_data, self.CONFIG_FILE)

    def delete_winlator_game_config(self, game_path):
        if CONF_WINLATOR_GAME_CONFIGS in self.config_data and game_path in self.config_data[CONF_WINLATOR_GAME_CONFIGS]:
            del self.config_data[CONF_WINLATOR_GAME_CONFIGS][game_path]
            if self.active_profile == game_path:
                self.load_profile('global')
            self._save_json(self.config_data, self.CONFIG_FILE)
            return True
        return False

    def get_icon_cache_dir(self):
        return self.ICON_CACHE_DIR

    def get_encoder_cache(self):
        return self.config_data.get(CONF_ENCODER_CACHE, {})

    def save_encoder_cache(self, video_encoders, audio_encoders):
        self.config_data[CONF_ENCODER_CACHE] = {'video': video_encoders, 'audio': audio_encoders}
        self._save_json(self.config_data, self.CONFIG_FILE)

    def has_encoder_cache(self):
        if self.CONFIG_FILE is None: return False
        return bool(self.get_encoder_cache().get('video') or self.get_encoder_cache().get('audio'))

    def load_config_for_device(self, device_id):
        self.active_profile = 'global' # Reset on device change
        if device_id is None or device_id == "no_device":
            self.CONFIG_FILE = None
            self.config_data = {}
            self.connection_id = None
            default_values = self._DEFAULT_VALUES.copy()
            # Load global keys from file, fall back to defaults
            for key in self.GLOBAL_KEYS:
                default_values[key] = self.global_config_data.get(key, default_values.get(key))
            self.values = default_values
            self.values['device_id'] = None
            return False

        # device_id here is the configuration_id (serial number)
        self.values['device_id'] = device_id

        sanitized_id = device_id.replace(':', '_').replace('\\', '_').replace('/', '_')
        self.CONFIG_FILE = os.path.join(self.CONFIG_DIR, f'config_{sanitized_id}.json')
        self.config_data = self._load_json(self.CONFIG_FILE)
        self.config_data.setdefault(CONF_GENERAL_CONFIG, {})
        # Ensure general_config has all default keys, using defaults if not present in file
        for key, default_value in self._DEFAULT_VALUES.items():
            if key not in self.GLOBAL_KEYS and key not in self.config_data[CONF_GENERAL_CONFIG]:
                self.config_data[CONF_GENERAL_CONFIG][key] = default_value

        self.config_data.setdefault(CONF_APP_METADATA, {})
        self.config_data.setdefault(CONF_APP_LIST_CACHE, {})
        self.config_data.setdefault(CONF_WINLATOR_GAME_CONFIGS, {})
        self.config_data.setdefault(CONF_ENCODER_CACHE, {})

        # Load the global profile for the device by default
        self.load_profile('global')
