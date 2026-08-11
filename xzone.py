import minimalmodbus
import datetime
import threading
from .xzone_address import XzoneRegisterAddress
import struct
from serial import Serial

# from logs import write_to_log_file


class Xzone:
    _instances = {}
    _lock = threading.Lock()
    _is_initialized = False

    def __new__(cls, gas_detector, *args, **kwargs):
        serial_number = gas_detector.gdr_serial_number
        with cls._lock:
            if serial_number not in cls._instances:
                instance = super(Xzone, cls).__new__(cls)
                cls._instances[serial_number] = instance
                instance._initialize(gas_detector)
        return cls._instances[serial_number]

    def __init__(self, gas_detector):
        if not self._is_initialized:
            self._initialize(gas_detector)
            Xzone._is_initialized = True

    def _initialize(self, gas_detector):
        self.s1 = ""
        self.s2 = ""
        self.s3 = ""
        self.s4 = ""
        self.s5 = ""

        self.v1 = -999.99
        self.v2 = -999.99
        self.v3 = -999.99
        self.v4 = -999.99
        self.v5 = -999.99

        self.u1 = ""
        self.u2 = ""
        self.u3 = ""
        self.u4 = ""
        self.u5 = ""
        self.S_number = ""
        self.isIntialized = False
        self.gas_channels = "S11,S12,S13,S14,S15"
        self.status = ""
        self.port = gas_detector.gdr_com_port
        self.slaveAddress = gas_detector.gdr_address
        self.deviceUniqueId = gas_detector.gdr_unique_id
        self.baudrate = 115200
        self.parity = "E"
        self.stopbits = 1
        self.clear_buffers_before_each_transaction = True
        self.close_port_after_each_call = True
        self.timeout = 5
        self.gas_detector = gas_detector
        self.count = 0
        self.success = False
        self.XzoneBattV = 0
        self.XamBattV = 0
        self.voltagecounter = 0
        self.XzoneErrors = []
        self.xzoneRegAddress = XzoneRegisterAddress()
        self.xzn_1101 = False
        self.xzn_1002 = False
        self.response_code = ""

    def reinitialize(self, gas_detector, force=False):
        if force:
            self._initialize(gas_detector)
            Xzone._is_initialized = True

    @classmethod
    def get_instance(cls, serial_number):
         return cls._instances.get(serial_number)

    @classmethod
    def clear_instance(cls, serial_number):
        with cls._lock:
            if serial_number in cls._instances:
                del cls._instances[serial_number]

    def initialize(self, forced):
        # write_to_log_file("==============================", self.status)
        if forced:
            print("initialize................1" +
                  self.gas_detector.gdr_name, self.count)
            self.StartDevice()  # add everything here which needs to be read
        else:
            if self.isIntialized:
                pass
            else:
                self.StartDevice()

    def StartDevice(self):
        try:
            print("###### Initializing a Xzone Device ########")
            serial = Serial()
            serial.port = self.port
            serial.baudrate = self.baudrate
            serial.parity = self.parity
            serial.stopbits = self.stopbits
            serial.timeout = self.timeout
            self.xzone = minimalmodbus.Instrument(self.port, self.slaveAddress)
            self.xzone.serial = serial
            # self.xzone.serial.baudrate = self.baudrate
            # self.xzone.serial.parity = self.parity
            # self.xzone.serial.stopbits = self.stopbits
            self.xzone.clear_buffers_before_each_transaction = (
                self.clear_buffers_before_each_transaction
            )
            self.xzone.close_port_after_each_call = self.close_port_after_each_call
            # self.xzone.serial.timeout = self.timeout
            self.xzone.serial.close()
            self.deviceType = "Xzone"
            new_success, self.status, new_serial_number, xam_detected = (
                self.readSerialNumber()
            )
            if xam_detected:
                print(
                    "oooooooooooooooo",
                    self.S_number,
                    new_serial_number,
                    new_success,
                    self.success,
                )
                if new_success & (new_success != self.success):
                    if self.S_number == "":
                        print(
                            "Intializing for the first time     Device Initiation successfull"
                        )
                        self.isIntialized = True
                        (
                            self.success,
                            self.status,
                            self.s1,
                            self.s2,
                            self.s3,
                            self.s4,
                            self.s5,
                        ) = self.xzoneGetGas()
                        (
                            self.success,
                            self.status,
                            self.u1,
                            self.u2,
                            self.u3,
                            self.u4,
                            self.u5,
                        ) = self.xzoneGetGasUnit()
                        print("GASES", self.s1, self.s2,
                              self.s3, self.s4, self.s5)
                        self.readVoltages()
                        self.success, self.status, self.XzoneErrors = self.xzoneError()
                    elif self.S_number == new_serial_number:
                        print(
                            "Intializing a old device again the first time     Device Initiation successfull"
                        )
                        self.isIntialized = True
                        (
                            self.success,
                            self.status,
                            self.s1,
                            self.s2,
                            self.s3,
                            self.s4,
                            self.s5,
                        ) = self.xzoneGetGas()
                        (
                            self.success,
                            self.status,
                            self.u1,
                            self.u2,
                            self.u3,
                            self.u4,
                            self.u5,
                        ) = self.xzoneGetGasUnit()
                        self.readVoltages()
                        self.success, self.status, self.XzoneErrors = self.xzoneError()
                    else:
                        self.S_number = new_serial_number
                        self.success = new_success
                        self.isIntialized = False
                self.S_number = new_serial_number
                self.success = new_success
            else:
                self.success = False
                self.isIntialized = False
        except Exception as e:
            print("!!!!!!!!!!!!!!!!!!", str(e))
            self.isIntialized = False
            self.success = False
            self.status = str(e)
            # self.S_number = ""

        finally:
            pass

    def readData(self):
        gdr_status = {
                "gdr_serial_id": self.gas_detector.id,
                "gdr_success": self.success,
                "gdr_status": self.status,
                "gdr_serial_number": self.S_number,
        }

        if self.isIntialized:  # self.isIntialized
            currentTime = str(
                 datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
            )
            self.success, self.status, self.v1, self.v2, self.v3, self.v4, self.v5 = (
                self.xzoneGasMeasurement()
            )
            print("current state", self.isIntialized, self.success)
            gasReadings = []
            if self.success:
                if self.s1:
                    gasReadings.append(
                        {
                            "gmt_sensor_number": "S11",
                            "gmt_gas_name": self.s1,
                            "gmt_gas_value": self.v1,
                            "gmt_gas_unit": self.u1,
                        }
                    )
                if self.s2:
                    gasReadings.append(
                        {
                            "gmt_sensor_number": "S12",
                            "gmt_gas_name": self.s2,
                            "gmt_gas_value": self.v2,
                            "gmt_gas_unit": self.u2,
                        }
                    )
                if self.s3:
                    gasReadings.append(
                        {
                            "gmt_sensor_number": "S13",
                            "gmt_gas_name": self.s3,
                            "gmt_gas_value": self.v3,
                            "gmt_gas_unit": self.u3,
                        }
                    )
                if self.s4:
                    gasReadings.append(
                        {
                            "gmt_sensor_number": "S14",
                            "gmt_gas_name": self.s4,
                            "gmt_gas_value": self.v4,
                            "gmt_gas_unit": self.u4,
                        }
                    )
                if self.s5:
                    gasReadings.append(
                        {
                            "gmt_sensor_number": "S15",
                            "gmt_gas_name": self.s5,
                            "gmt_gas_value": self.v5,
                            "gmt_gas_unit": self.u5,
                        }
                    )
                gdr_out_mqtt = {
                        "gdr_name": self.gas_detector.gdr_name,
                        "gdr_type": "1",
                        "gdr_serial_number": self.S_number,
                        "gdr_gas_sensor_params": [],
                        "gas_detector_inlet": [
                            {
                                "gdi_number": "1",
                                "gdi_status": "Reading",
                                "gdi_timestamp": currentTime,
                                "gas_detector_inlet_measurement": gasReadings,
                            }
                        ],
                        "gdr_battery_status": [
                            {
                                "gdr_battery_device": "Xzone",
                                "gdr_battery_unit": "V",
                                "gdr_battery_value": self.XzoneBattV,
                            },
                            {
                                "gdr_battery_device": "Xam",
                                "gdr_battery_unit": "V",
                                "gdr_battery_value": self.XamBattV,
                            },
                        ],
                        "gdr_response": self.XzoneErrors,
                }
            else:
                self.isIntialized = False
                gdr_out_mqtt = {
                        "gdr_name": self.gas_detector.gdr_name,
                        "gdr_type": "1",
                        "gdr_serial_number": self.S_number,
                        "gdr_gas_sensor_params": [],
                        "gas_detector_inlet": [],
                        "gdr_battery_status": [
                            {
                                "gdr_battery_device": "Xzone",
                                "gdr_battery_unit": "V",
                                "gdr_battery_value": -99.99,
                            },
                            {
                                "gdr_battery_device": "Xam",
                                "gdr_battery_unit": "V",
                                "gdr_battery_value": -99.99,
                            },
                        ],
                        "gdr_response": self.XzoneErrors,
                }

        else:

            if self.status == "No communication with X-am":
                self.XzoneErrors = [
                    {
                        "gdr_response_code": "XZN1002",
                        "gdr_response_message": "No Xam is connected",
                    }
                ]
            else:
                self.XzoneErrors = [
                    {
                        "gdr_response_code": "XZN1101",
                        "gdr_response_message": "No communication with Xzone",
                    }
                ]
            gdr_out_mqtt = {
                    "gdr_name": self.gas_detector.gdr_name,
                    "gdr_type": "1",
                    "gdr_serial_number": self.S_number,
                    "gdr_gas_sensor_params": [],
                    "gas_detector_inlet": [],
                    "gdr_battery_status": [
                        {
                            "gdr_battery_device": "Xzone",
                            "gdr_battery_unit": "V",
                            "gdr_battery_value": -99.99,
                        },
                        {
                            "gdr_battery_device": "Xam",
                            "gdr_battery_unit": "V",
                            "gdr_battery_value": -99.99,
                        },
                    ],
                    "gdr_response": self.XzoneErrors,
            }

        return gdr_status, gdr_out_mqtt

    def readVoltages(self):
        if self.isIntialized:
            self.success, self.status, self.XamBattV = self.xamBatteryV()
            self.success, self.status, self.XzoneBattV = self.xzoneBatteryV()

    def readErrors(self):
        if self.isIntialized:
            self.success, self.status, self.XzoneErrors = self.xzoneError()

    def watchDog(self, value):
        if self.isIntialized:
            self.success, self.status = self.xzoneWatchdogWrite(value)

    def acknowledgeAlarm(self):
        # if(self.isIntialized):
        self.success, self.status = self.xzoneAcknowledgeAlarm()

    def evacuateAlarm(self, alarm_val):
        print("evac alaram", self.isIntialized)
        if self.isIntialized:

            self.success, self.status = self.xzoneEvacAlarm(alarm_val)

    def turnOffWatchDog(self, turnOffWatchDogList):
        # write_to_log_file(
        #     "HHHHHHHHHHHHHHHHHHHHH", turnOffWatchDogList, self.gas_detector.id
        # )

        if str(self.gas_detector.id) in turnOffWatchDogList:
            # write_to_log_file(
            #     "Xzone was found here", self.gas_detector.id, turnOffWatchDogList
            # )
            self.success, self.status = self.xzoneWatchdogWrite(0)

    def decode_error_code(self, mask):
        decoded_errors = []
        print("This is the mask or error code", mask)
        for error in self.xzoneRegAddress.xzone_response_mapper:
            if mask & error["xzone_response_code"]:
                decoded_errors.append(
                    {
                        "gdr_response_code": error["emc_response_code"],
                        "gdr_response_message": error["xzone_response_message"],
                    }
                )
        return decoded_errors

    def readSerialNumber(self):
        serial_number = ""
        xam_detected = False
        success = False
        status = ""
        try:
            error_code = self.xzone.read_long(29, 3, False)
            if error_code & 0x2:  # this code is for communiation lost with X-am
                xam_detected = False
                serial_number = (
                    self.xzone.read_string(6, 5, 3).replace("\u0000", "") + "_"
                )  # No Xam is connected
                success = False
                status = "No communication with X-am"
            else:
                success = True
                xam_detected = True
                serial_number = (
                    self.xzone.read_string(6, 5, 3)
                    + "_"
                    + self.xzone.read_string(15, 5, 3)
                ).replace("\u0000", "")
                status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file("$$$$$$$$$$$$$$$$$$$$$$", success, e)
        return (success, status, serial_number, xam_detected)

    # --------------------------------------------------- 5 X-zone Error codes -----------------------------------------------#
    def xzoneError(self):

        v1 = 0
        try:
            success = True
            v1 = self.xzone.read_long(29, 3, False)

            # write_to_log_file("ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        error = self.decode_error_code(v1)
        return (success, status, error)

    # --------------------------------------------------- 6 X-zone Temprature -----------------------------------------------#
    def xzoneTemprature(self):

        v1 = 0
        try:
            success = True
            v1 = self.xzone.read_register(32, 0, 3, True)

            # write_to_log_file("ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        return (success, status, v1)

    # --------------------------------------------------- 7 X-zone Battery Voltage -----------------------------------------------#
    def xzoneBatteryV(self):

        v1 = 0
        try:
            success = True
            v1 = self.xzone.read_register(31, 0, 3, True) / 1000

            # write_to_log_file("ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        return (success, status, v1)

    # --------------------------------------------------- 8 X-am Battery Voltage -----------------------------------------------#
    def xamBatteryV(self):

        v1 = 0
        try:
            success = True
            v1 = self.xzone.read_register(35, 0, 3, True) / 1000
            # write_to_log_file("ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        return (success, status, v1)

    # --------------------------------------------------- 9 X-zone watchdog write -----------------------------------------------#
    def xzoneWatchdogWrite(self, val):  # we should trigger every

        v1 = 0
        try:
            success = True
            self.xzone.write_register(34, val, 0, 6)
            # write_to_log_file("ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        return (success, status)

    # --------------------------------------------------- 9 X-zone Evacuation Alarm -----------------------------------------------#
    def xzoneEvacAlarm(self, val):

        try:
            success = True
            self.xzone.write_register(28, val, 0, 16, True)
            # write_to_log_file("ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        return (success, status)

    # --------------------------------------------------- 9 X-zone Acknowledge Alarm -----------------------------------------------#
    def xzoneAcknowledgeAlarm(self):  # Write 1 to stop an alarm

        v1 = 0
        try:
            success = True
            self.xzone.write_register(33, 1, 0, 6, False)
            print(self.xzone.read_register(33, 0, 3, True))
            print("AA ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            print(e)

        return (success, status)

    # --------------------------------------------------- 9 X-zone Set Gas -----------------------------------------------#
    def xzoneGasMeasurement(self):

        v1, v2, v3, v4, v5 = 0.0, 0.0, 0.0, 0.0, 0.0
        try:
            val = self.xzone.read_registers(1200, 10, 3)
            # write_to_log_file("@@@@@@@@@@@@@@@@@@@@@@Reading 5 registers",val)
            success = True
            # write_to_log_file("ok")
            status = "Connected"
            v1 = struct.unpack("i", struct.pack(
                "I", val[0] * 65536 + val[1]))[0] / 1000
            v2 = struct.unpack("i", struct.pack(
                "I", val[2] * 65536 + val[3]))[0] / 1000
            v3 = struct.unpack("i", struct.pack(
                "I", val[4] * 65536 + val[5]))[0] / 1000
            v4 = struct.unpack("i", struct.pack(
                "I", val[6] * 65536 + val[7]))[0] / 1000
            v5 = struct.unpack("i", struct.pack(
                "I", val[8] * 65536 + val[9]))[0] / 1000
        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        return (success, status, v1, v2, v3, v4, v5)

    # --------------------------------------------------- 9 X-zone Get Gas -----------------------------------------------#
    def xzoneGetGas(self):

        v1, v2, v3, v4, v5 = "", "", "", "", ""
        try:
            success = True
            v = self.xzone.read_registers(400, 10, 3)
            v1 = (
                (
                    chr((v[0] & 0xFF00) >> 8)
                    + chr(v[0] & 0x00FF)
                    + chr((v[1] & 0xFF00) >> 8)
                    + chr(v[1] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )
            v2 = (
                (
                    chr((v[2] & 0xFF00) >> 8)
                    + chr(v[2] & 0x00FF)
                    + chr((v[3] & 0xFF00) >> 8)
                    + chr(v[3] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )
            v3 = (
                (
                    chr((v[4] & 0xFF00) >> 8)
                    + chr(v[4] & 0x00FF)
                    + chr((v[5] & 0xFF00) >> 8)
                    + chr(v[5] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )
            v4 = (
                (
                    chr((v[6] & 0xFF00) >> 8)
                    + chr(v[6] & 0x00FF)
                    + chr((v[7] & 0xFF00) >> 8)
                    + chr(v[7] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )
            v5 = (
                (
                    chr((v[8] & 0xFF00) >> 8)
                    + chr(v[8] & 0x00FF)
                    + chr((v[9] & 0xFF00) >> 8)
                    + chr(v[9] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )

            # v1 = self.xzone.read_string(400,2,3).replace('\u0000', '')
            # v2 = self.xzone.read_string(402,2,3).replace('\u0000', '')
            # v3 = self.xzone.read_string(404,2,3).replace('\u0000', '')
            # v4 = self.xzone.read_string(406,2,3).replace('\u0000', '')
            # v5 = self.xzone.read_string(408,2,3).replace('\u0000', '')

            # write_to_log_file("88888888888888888888888888888888", v1, v2, v3, v4, v5)

            # write_to_log_file("ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        return (success, status, v1, v2, v3, v4, v5)

    # --------------------------------------------------- 9 X-zone Get Unit -----------------------------------------------#
    def xzoneGetGasUnit(self):

        v1, v2, v3, v4, v5 = "XXXXXX", "XXXXXX", "XXXXXX", "XXXXXX", "XXXXXX"
        try:
            success = True
            v = self.xzone.read_registers(500, 15, 3)
            v1 = (
                (
                    chr((v[0] & 0xFF00) >> 8)
                    + chr(v[0] & 0x00FF)
                    + chr((v[1] & 0xFF00) >> 8)
                    + chr(v[1] & 0x00FF)
                    + chr((v[2] & 0xFF00) >> 8)
                    + chr(v[2] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )
            v2 = (
                (
                    chr((v[3] & 0xFF00) >> 8)
                    + chr(v[3] & 0x00FF)
                    + chr((v[4] & 0xFF00) >> 8)
                    + chr(v[4] & 0x00FF)
                    + chr((v[5] & 0xFF00) >> 8)
                    + chr(v[5] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )
            v3 = (
                (
                    chr((v[6] & 0xFF00) >> 8)
                    + chr(v[6] & 0x00FF)
                    + chr((v[7] & 0xFF00) >> 8)
                    + chr(v[7] & 0x00FF)
                    + chr((v[8] & 0xFF00) >> 8)
                    + chr(v[8] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )
            v4 = (
                (
                    chr((v[9] & 0xFF00) >> 8)
                    + chr(v[9] & 0x00FF)
                    + chr((v[10] & 0xFF00) >> 8)
                    + chr(v[10] & 0x00FF)
                    + chr((v[11] & 0xFF00) >> 8)
                    + chr(v[11] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )
            v5 = (
                (
                    chr((v[12] & 0xFF00) >> 8)
                    + chr(v[12] & 0x00FF)
                    + chr((v[13] & 0xFF00) >> 8)
                    + chr(v[13] & 0x00FF)
                    + chr((v[14] & 0xFF00) >> 8)
                    + chr(v[14] & 0x00FF)
                )
                .replace("\u0000", "")
                .replace(" ", "")
                .upper()
            )

            # write_to_log_file("ok")
            status = "Connected"

        except Exception as e:
            success = False
            status = str(e)
            # write_to_log_file(e)

        return (success, status, v1, v2, v3, v4, v5)