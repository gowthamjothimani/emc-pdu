import json
import threading
import time
import paho.mqtt.client as mqtt
from mqtt_config import get_mqtt_config

class PDUMQTTPublisher:
    def __init__(self, data_lock, data_provider):
        self.data_lock = data_lock
        self.data_provider = data_provider
        self.client = None
        self.connected = False
        self.running = False
        self.thread = None
        self.lock = threading.Lock()

    def connect(self):
        config = get_mqtt_config()
        broker = config["broker"]
        port = config["port"]
        username = config["broker_username"]
        password = config["broker_password"]
        print(f"[MQTT] Connecting to "f"{broker}:{port}")
        try:
            client = mqtt.Client()
            if (
                username is not None
                and password is not None
            ):
                client.username_pw_set(username,password)
            client.connect(broker,port,60)
            client.loop_start()

            with self.lock:
                self.client = client
                self.connected = True

            print(f"[MQTT] Connected to " f"{broker}:{port}")
            return True

        except Exception as exc:
            print(f"[MQTT] Connection failed: {exc}")

            with self.lock:
                self.client = None
                self.connected = False
            return False

    def disconnect(self):
        with self.lock:
            client = self.client
            self.client = None
            self.connected = False

        if client is not None:
            try:
                client.loop_stop()
                client.disconnect()
            except Exception as exc:
                print(f"[MQTT] Disconnect error: {exc}")

        print("[MQTT] Disconnected")

    def restart(self):
        print("[MQTT] Restarting MQTT connection...")
        self.disconnect()
        time.sleep(1)
        self.connect()

    def publish(self, topic, data):
        with self.lock:
            client = self.client
            connected = self.connected

        if (client is None or not connected):
            return False
        try:
            payload = json.dumps(data,default=str)
            result = client.publish(topic,payload,qos=0,retain=False)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
            print("Publish failed")
            return False
        except Exception as exc:
            print(f"[MQTT] Publish error: {exc}")
            return False

    def publisher_task(self):
        print("[MQTT] Publisher started")
        while self.running:
            try:
                config = get_mqtt_config()
                battery_topic = (config["battery_topic"])
                charger_topic = (config["charger_topic"])
                battery_data, charger_data = (self.data_provider())
                if battery_data is not None:
                    self.publish(battery_topic,battery_data)

                if charger_data is not None:
                    self.publish(charger_topic,charger_data)

            except Exception as exc:
                print(f"[MQTT] Publisher error: {exc}")
            time.sleep(1)

    def start(self):
        self.running = True
        self.connect()
        self.thread = threading.Thread(target=self.publisher_task,daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.disconnect()