import socket
import threading

hostname = socket.gethostname()

# Default MQTT configuration
mqtt_config = {
    "broker": "192.168.1.100",
    "port": 1883,
    "broker_username": None,
    "broker_password": None,
}

mqtt_config_lock = threading.Lock()


def get_mqtt_config():
    with mqtt_config_lock:
        return {
            "broker": mqtt_config["broker"],
            "port": mqtt_config["port"],
            "broker_username": mqtt_config["broker_username"],
            "broker_password": mqtt_config["broker_password"],
            "status": "MQTT Broker configured",
            "battery_topic":
                f"PDU/{hostname}/batteryData",
            "charger_topic":
                f"PDU/{hostname}/chargerData",
        }


def update_mqtt_config(broker,port,broker_username=None,broker_password=None):
    with mqtt_config_lock:
        mqtt_config["broker"] = broker
        mqtt_config["port"] = port
        mqtt_config["broker_username"] = (broker_username)
        mqtt_config["broker_password"] = (broker_password)
    return get_mqtt_config()