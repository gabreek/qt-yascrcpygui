# FILE: app_config.py
# PURPOSE: Centraliza o gerenciamento de configurações, caminhos e variáveis.

import os
import json
import platform

class AppConfig:
    _DEFAULT_VALUES = {
        'device_id': None,
        'theme': 'System',
        'device_commercial_name': 'Unknown Device',
        'start_app': '',
        'start_app_name': 'None',
        'default_launcher': None,
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
        'allow_frame_drop': 'Enabled',
        'low_latency': 'Enabled',
        'priority_mode': 'Realtime',
        'bitrate_mode': 'VBR',
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
        'try_unlock': False,
        'alternate_launch_method': False,
        'windowing_mode': 'Fullscreen',
        'show_system_apps': True,
        'start_web_server_on_launch': False,
    }
    GLOBAL_KEYS = {'theme', 'show_system_apps', 'start_web_server_on_launch'}
    PROFILE_TYPES = {'app': 'app_metadata', 'winlator': 'winlator_game_configs'}


    def __init__(self, device_id):
        self.config_data = {}
        self.values = self._DEFAULT_VALUES.copy()
        self.CONFIG_FILE = None
        self.active_profile = 'global'
        self.connection_id = None
        self.device_app_cache = {'installed_apps': set(), 'winlator_shortcuts': set()} # New attribute

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
        return self.connection_id or self.get('device_id')

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
            values.update(self.config_data.get('general_config', {}))

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
            self.config_data['general_config'] = device_settings
        elif self.active_profile in self.get_app_config_keys(include_name=False):
            self.save_app_scrcpy_config(self.active_profile, device_settings)
        elif self.active_profile in self.get_winlator_config_keys(include_name=False):
            self.save_winlator_game_config(self.active_profile, device_settings)

        self._save_json(self.config_data, self.CONFIG_FILE)


    def get_app_config_keys(self, include_name=True):
        if not self.config_data: return []
        keys = []
        app_metadata = self.config_data.get('app_metadata', {})
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
        winlator_configs = self.config_data.get('winlator_game_configs', {})
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
        base_config = self.config_data.get('general_config', {}).copy()

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
        if 'app_metadata' not in self.config_data:
            self.config_data['app_metadata'] = {}
        if key not in self.config_data['app_metadata']:
            self.config_data['app_metadata'][key] = {}

    def get_app_metadata(self, key):
        return self.config_data.get('app_metadata', {}).get(key, {})

    def save_app_metadata(self, key, data):
        self._ensure_metadata_structure(key)
        self.config_data['app_metadata'][key].update(data)
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
            # Save to the 'general_config' for the current device
            if 'general_config' not in self.config_data:
                self.config_data['general_config'] = {}
            self.config_data['general_config'].update(device_settings)
        else:
            # Save to a specific app's profile
            self._ensure_metadata_structure(pkg_name)
            if 'config' not in self.config_data['app_metadata'][pkg_name]:
                self.config_data['app_metadata'][pkg_name]['config'] = {}
            self.config_data['app_metadata'][pkg_name]['config'].update(device_settings)
        
        # Save the main device config file
        self._save_json(self.config_data, self.CONFIG_FILE)

    def delete_app_scrcpy_config(self, pkg_name):
        if 'app_metadata' in self.config_data and pkg_name in self.config_data['app_metadata'] and 'config' in self.config_data['app_metadata'][pkg_name]:
            del self.config_data['app_metadata'][pkg_name]['config']
            if not self.config_data['app_metadata'][pkg_name]: # cleanup if empty
                 del self.config_data['app_metadata'][pkg_name]
            if self.active_profile == pkg_name:
                self.load_profile('global')
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
        config_to_save = {k: v for k, v in config.items() if k not in self.GLOBAL_KEYS}
        if 'winlator_game_configs' not in self.config_data:
            self.config_data['winlator_game_configs'] = {}
        self.config_data['winlator_game_configs'][game_path] = config_to_save
        self._save_json(self.config_data, self.CONFIG_FILE)

    def delete_winlator_game_config(self, game_path):
        if 'winlator_game_configs' in self.config_data and game_path in self.config_data['winlator_game_configs']:
            del self.config_data['winlator_game_configs'][game_path]
            if self.active_profile == game_path:
                self.load_profile('global')
            self._save_json(self.config_data, self.CONFIG_FILE)
            return True
        return False

    def get_icon_cache_dir(self):
        return self.ICON_CACHE_DIR

    def get_encoder_cache(self):
        return self.config_data.get('encoder_cache', {})

    def save_encoder_cache(self, video_encoders, audio_encoders):
        self.config_data['encoder_cache'] = {'video': video_encoders, 'audio': audio_encoders}
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
        self.config_data.setdefault('general_config', {})
        # Ensure general_config has all default keys, using defaults if not present in file
        for key, default_value in self._DEFAULT_VALUES.items():
            if key not in self.GLOBAL_KEYS and key not in self.config_data['general_config']:
                self.config_data['general_config'][key] = default_value

        self.config_data.setdefault('app_metadata', {})
        self.config_data.setdefault('app_list_cache', {})
        self.config_data.setdefault('winlator_game_configs', {})
        self.config_data.setdefault('encoder_cache', {})

        # Load the global profile for the device by default
        self.load_profile('global')
