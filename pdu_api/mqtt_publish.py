import json
import threading
import time
import paho.mqtt.client as mqtt
from mqtt_config import get_mqtt_config

class MQTTPublisher:
    def __init__(self, data_lock, data_provider):
        self.data_lock = data_lock
        self.data_provider = data_provider
        self.client = None
        self.connected = False
        self.running = False
        self.thread = None
        self.last_config = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._publisher_task,daemon=True)
        self.thread.start()
        print("[MQTT] Publisher thread started")

    def stop(self):
        self.running = False
        self._disconnect()
        print("[MQTT] Publisher stopped")

    def _create_client(self):
        client = mqtt.Client()
        return client

    def _connect(self, config):
        try:
            print(
                "[MQTT] Connecting to "
                f"{config['broker']}:{config['port']}"
            )
            self.client = self._create_client()
            username = config.get("broker_username")
            password = config.get("broker_password")
            if username:
                self.client.username_pw_set(username, password)
            self.client.connect(config["broker"],config["port"],keepalive=60 )
            self.client.loop_start()
            self.connected = True
            self.last_config = (
                config["broker"],
                config["port"],
                config.get("broker_username"),
                config.get("broker_password")
            )

            print("[MQTT] Connected successfully")

            return True
        except Exception as exc:
            self.connected = False
            print(f"[MQTT] Connection failed: {exc}")
            self._disconnect()
            return False

    def _disconnect(self):
        if self.client is not None:
            try:
                self.client.loop_stop()
            except Exception:
                pass
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.client = None
        self.connected = False

    def _config_changed(self, config):
        current_config = (
            config["broker"],
            config["port"],
            config.get("broker_username"),
            config.get("broker_password")
        )
        return current_config != self.last_config

    def _publish_data(self):
        if not self.connected:
            return
        data = self.data_provider()
        if data is None:
            return
        battery_data = data.get("battery")
        charger_data = data.get("charger")
        config = get_mqtt_config()

        if battery_data is not None:
            try:
                payload = json.dumps(battery_data)
                self.client.publish(config["battery_topic"],payload)
            except Exception as exc:
                print(f"[MQTT] Battery publish error: {exc}")

        if charger_data is not None:
            try:
                payload = json.dumps(charger_data)
                self.client.publish(config["charger_topic"],payload)
            except Exception as exc:
                print(f"[MQTT] Charger publish error: {exc}")

    def _publisher_task(self):
        while self.running:
            try:
                config = get_mqtt_config()
                if self._config_changed(config):
                    print("[MQTT] MQTT configuration ""changed")
                    self._disconnect()
                    self._connect(config)

                elif not self.connected:
                    self._connect(config)
                if self.connected:
                    self._publish_data()

            except Exception as exc:
                print(f"[MQTT] Publisher error: {exc}")
                self.connected = False
            time.sleep(2)