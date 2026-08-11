import json
import socket

CONFIG_FILE = "config/config.json"

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

USERNAME = config["username"]
PASSWORD = config["password"]

DEVICE_ID = socket.gethostname()