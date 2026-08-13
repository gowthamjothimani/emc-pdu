# PDU API – Quick Test Notes

## 1. Start PDU Service

```bash
sudo systemctl start pdu-api.service
```

Check service:

```bash
sudo systemctl status pdu-api.service
```

Live logs:

```bash
sudo journalctl -u pdu-api.service -f
```

Check CAN:

```bash
ip -details link show can1
```

Expected:

```text
bitrate 250000
```

---

## 2. FastAPI

API base URL:

```text
http://<BBB-IP>:8000
```

Swagger:

```text
http://<BBB-IP>:8000/docs
```

---

## 3. AUTH API

### Login

```http
POST /api/v1/auth/token
```

Body:

```json
{
  "username": "admin",
  "password": "admin"
}
```

Expected:

```json
{
  "access_token": "<TOKEN>",
  "token_type": "bearer"
}
```

Copy the `access_token` for the other APIs.

---

## 4. MQTT Config

### Get current configuration

```http
GET /api/v1/mqtt/config
```

Header:

```text
Authorization: Bearer <TOKEN>
```

Expected default:

```json
{
  "broker": "192.168.1.100",
  "port": 1883,
  "broker_username": null,
  "broker_password": null,
  "status": "MQTT Broker configured",
  "battery_topic": "PDU/<hostname>/batteryData",
  "charger_topic": "PDU/<hostname>/chargerData"
}
```

### Configure new broker

```http
POST /api/v1/mqtt/config
```

Header:

```text
Authorization: Bearer <TOKEN>
```

Body:

```json
{
  "broker": "192.168.1.200",
  "port": 1883,
  "broker_username": null,
  "broker_password": null
}
```

Expected behavior:

```text
Update MQTT configuration
        ↓
Disconnect old broker
        ↓
Connect new broker
        ↓
Continue battery/charger publishing
```

---

## 5. Status API

```http
GET /api/v1/status
```

No authentication currently required.

Example response:

```json
{
  "hostname": "pdu-bbb-001",
  "mac_address": "XX:XX:XX:XX:XX:XX",
  "timestamp": "2026-08-13T18:30:00Z",
  "battery_percentage": 82,
  "battery_state": "Discharging",
  "system_voltage": 51.8,
  "load_current": 4.2,
  "battery_charging_current": -4.2,
  "battery_capacity_in_min": 120,
  "time_since_boot_in_sec": 2340
}
```

Load-current logic:

```text
Charging:
    Load = Charger Current - Battery Current

Discharging:
    Load = |Battery Current|

Ready:
    Load = Charger Current
```

Runtime:

```text
Runtime (min) =
    Remaining Battery Capacity (Ah)
    -------------------------------- × 60
          Load Current (A)
```

---

## 6. Remote Shutdown

```http
POST /api/v1/remote-shutdown
```

Header:

```text
Authorization: Bearer <TOKEN>
```

Body:

```json
{
  "username": "admin",
  "shutoff": true,
  "timestamp": null
}
```

Expected:

```json
{
  "username": "admin",
  "shutoff": true,
  "timestamp": "2026-08-13T18:30:00Z",
  "status": "Remote shutdown executed"
}
```

This calls:

```python
emc_board.turn_off_all()
```

and turns OFF all PDU outputs.

---

## 7. Quick `curl` Test

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
-H "Content-Type: application/json" \
-d '{"username":"admin","password":"admin"}'
```

### MQTT config

```bash
curl http://localhost:8000/api/v1/mqtt/config \
-H "Authorization: Bearer <TOKEN>"
```

### Status

```bash
curl http://localhost:8000/api/v1/status
```

### Remote shutdown

```bash
curl -X POST http://localhost:8000/api/v1/remote-shutdown \
-H "Authorization: Bearer <TOKEN>" \
-H "Content-Type: application/json" \
-d '{"username":"admin","shutoff":true}'
```

### Check MQTT publishing

Subscribe from another machine:

```bash
mosquitto_sub -h <MQTT-BROKER-IP> \
-t 'PDU/+/batteryData' \
-v
```

and:

```bash
mosquitto_sub -h <MQTT-BROKER-IP> \
-t 'PDU/+/chargerData' \
-v
```

