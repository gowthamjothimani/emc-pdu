import json
import logging
import sys
import threading
import time
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from .config import HOSTNAME
from .mqtt_config import load_mqtt_config

logger = logging.getLogger(__name__)


def _load_module(path: Path, module_name: str):
    if not path.exists():
        logger.error("Missing module path: %s", path)
        return None

    sys_path = str(path.parent)
    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)

    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        logger.error("Could not load module spec for %s", path)
        return None

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MQTTManager:
    def __init__(self):
        self.client: Optional[mqtt.Client] = None
        self.connected = False
        self.config: Dict[str, Any] = {}

    def connect(self, config: Dict[str, Any]) -> bool:
        self.disconnect()

        self.config = config.copy()
        broker = config.get("broker")
        port = int(config.get("port", 1883))
        username = config.get("broker_username") or ""
        password = config.get("broker_password") or ""

        if not broker:
            logger.warning("MQTT broker is not configured")
            self.connected = False
            return False

        self.client = mqtt.Client()
        if username or password:
            self.client.username_pw_set(username=username, password=password)

        try:
            self.client.connect(broker, port, 60)
            self.client.loop_start()
            self.connected = True
            logger.info("MQTT connected to %s:%s", broker, port)
            return True
        except Exception as exc:
            logger.error("MQTT connect failed: %s", exc)
            self.connected = False
            return False

    def publish(self, topic: str, payload: Dict[str, Any]) -> bool:
        if not self.connected or not topic:
            return False

        try:
            self.client.publish(topic, json.dumps(payload), qos=0, retain=True)
            return True
        except Exception as exc:
            logger.error("MQTT publish failed (%s): %s", topic, exc)
            return False

    def disconnect(self) -> None:
        if self.client is not None:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception:
                pass
        self.connected = False
        self.client = None


class BaseMonitor:
    def __init__(self, interval_sec: float = 2.0):
        self.thread: Optional[threading.Thread] = None
        self.running = False
        self.latest: Dict[str, Any] = {}
        self.interval_sec = interval_sec

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.running = False
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def _run(self) -> None:
        raise NotImplementedError()


class BatteryMonitor(BaseMonitor):
    def __init__(self, root_path: Path, mqtt_manager: MQTTManager, battery_topic: str):
        super().__init__()
        self.mqtt_manager = mqtt_manager
        self.topic = battery_topic or f"PDU/{HOSTNAME}/batteryData"
        self.instance = None
        self.root_path = root_path
        self._load_battery_driver()

    def _load_battery_driver(self) -> None:
        battery_dir = self.root_path / "PDU_DEV_extracted" / "PDU_DEV" / "Battery"
        module = _load_module(battery_dir / "qhb.py", "battery_qhb")
        self.CAN_QHB = getattr(module, "CAN_QHB", None) if module else None

    def _initialize(self) -> bool:
        if self.CAN_QHB is None:
            return False
        self.instance = self.CAN_QHB()
        try:
            return self.instance.init_device()
        except Exception as exc:
            logger.error("Battery init_device failed: %s", exc)
            return False

    def _run(self) -> None:
        if not self._initialize():
            logger.error("Battery monitor could not initialize CAN device")
            return

        while self.running:
            try:
                data = self.instance.read_data()
                if isinstance(data, dict):
                    self.latest = data
                    if self.mqtt_manager.connected:
                        self.mqtt_manager.publish(self.topic, data)
            except Exception as exc:
                logger.error("Battery monitor read loop error: %s", exc)
            time.sleep(self.interval_sec)


class ChargerMonitor(BaseMonitor):
    def __init__(self, root_path: Path, mqtt_manager: MQTTManager, charger_topic: str):
        super().__init__()
        self.mqtt_manager = mqtt_manager
        self.topic = charger_topic or f"PDU/{HOSTNAME}/chargerData"
        self.instance = None
        self.root_path = root_path
        self._load_charger_driver()

    def _load_charger_driver(self) -> None:
        charger_dir = self.root_path / "PDU_DEV_extracted" / "PDU_DEV" / "Charger"
        module = _load_module(charger_dir / "NPB.py", "charger_npb")
        self.NPB_Charger = getattr(module, "NPB_Charger", None) if module else None

    def _initialize(self) -> bool:
        if self.NPB_Charger is None:
            return False
        try:
            self.instance = self.NPB_Charger(channel="can1", address=0x03)
            return self.instance.start_device()
        except Exception as exc:
            logger.error("Charger start_device failed: %s", exc)
            return False

    def _run(self) -> None:
        if not self._initialize():
            logger.error("Charger monitor could not initialize CAN device")
            return

        while self.running:
            try:
                data = self.instance.read_data()
                if isinstance(data, dict):
                    self.latest = data
                    if self.mqtt_manager.connected:
                        self.mqtt_manager.publish(self.topic, data)
            except Exception as exc:
                logger.error("Charger monitor read loop error: %s", exc)
            time.sleep(self.interval_sec)


class HardwareService:
    def __init__(self):
        self.root_path = Path(__file__).resolve().parents[1]
        self.mqtt_manager = MQTTManager()
        config = load_mqtt_config()
        self._set_topics(config)
        self.battery = BatteryMonitor(self.root_path, self.mqtt_manager, self.battery_topic)
        self.charger = ChargerMonitor(self.root_path, self.mqtt_manager, self.charger_topic)
        self.mqtt_config = config

    def _set_topics(self, config: Dict[str, Any]) -> None:
        self.battery_topic = config.get("battery_topic") or f"PDU/{HOSTNAME}/batteryData"
        charger_topic = config.get("charger_topic")
        if charger_topic:
            self.charger_topic = charger_topic
        else:
            self.charger_topic = self.battery_topic.replace("batteryData", "chargerData")

    def start(self) -> None:
        self.mqtt_manager.connect(self.mqtt_config)
        self.battery.start()
        self.charger.start()

    def stop(self) -> None:
        self.battery.stop()
        self.charger.stop()
        self.mqtt_manager.disconnect()

    def reload_config(self, config: Dict[str, Any]) -> None:
        self.mqtt_config = config.copy()
        self._set_topics(config)
        self.battery.topic = self.battery_topic
        self.charger.topic = self.charger_topic
        self.mqtt_manager.connect(self.mqtt_config)

    def get_latest_status(self) -> Dict[str, Any]:
        return {
            "battery": self.battery.latest,
            "charger": self.charger.latest,
        }
