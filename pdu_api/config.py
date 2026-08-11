import socket
from pathlib import Path

API_USERNAME = "admin"
API_PASSWORD = "admin"
SECRET_KEY = "visics"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
MQTT_CONFIG_FILE = Path(__file__).resolve().parent / "mqtt_config.json"
DEFAULT_MQTT_CONFIG = {
    "broker": "",
    "port": 1883,
    "broker_username": "",
    "broker_password": "",
    "battery_topic": "",
    "charger_topic": ""
}
HOSTNAME = socket.gethostname()
