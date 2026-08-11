import json
from .config import MQTT_CONFIG_FILE, DEFAULT_MQTT_CONFIG


def load_mqtt_config() -> dict:
    try:
        with MQTT_CONFIG_FILE.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
            return {**DEFAULT_MQTT_CONFIG, **data}
    except FileNotFoundError:
        return DEFAULT_MQTT_CONFIG.copy()
    except json.JSONDecodeError:
        return DEFAULT_MQTT_CONFIG.copy()


def save_mqtt_config(config: dict) -> dict:
    config_to_save = {**DEFAULT_MQTT_CONFIG, **config}
    with MQTT_CONFIG_FILE.open("w", encoding="utf-8") as config_file:
        json.dump(config_to_save, config_file, indent=2)
    return config_to_save
