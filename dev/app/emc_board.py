class EMC_Board:
    def __init__(self, hardware_provider="VISICS"):
        self.I2C_BUS = 2
        self.SLAVE_ADDR = 0x58
        self.bits = 0b10000000
        self.hardware_provider = hardware_provider
        self.hardware_available = True
        self.last_error = None

        try:
            import Adafruit_BBIO.GPIO as GPIO
            from smbus2 import SMBus
        except ImportError as exc:
            self.hardware_available = False
            self.last_error = str(exc)
            return

        self._gpio = GPIO
        self._smbus_cls = SMBus

        try:
            reset_max7320 = "P8_11"
            self._gpio.setup(reset_max7320, self._gpio.OUT)
            self._gpio.output(reset_max7320, self._gpio.HIGH)
        except Exception as exc:
            self.hardware_available = False
            self.last_error = str(exc)
            return

        self.reset()

    def reset(self):
        self.bits = 0b10000000
        return self.write_max7320_zero(self.bits)

    def turn_off_all(self):
        self.bits = 0x00
        return self.write_max7320_zero(self.bits)

    def remote_shutoff(self):
        ok = self.turn_off_all()
        return {
            "success": ok,
            "status": "shutdown_initiated" if ok else "shutdown_failed",
            "detail": self.last_error or "All outputs turned off",
        }

    def write_max7320_zero(self, bits):
        if not self.hardware_available:
            self.last_error = "Hardware interface unavailable"
            return False

        try:
            with self._smbus_cls(self.I2C_BUS) as bus:
                bus.write_byte(self.SLAVE_ADDR, bits)
            self.last_error = None
            print(f"Successfully wrote {bits}")
            return True
        except OSError as e:
            self.last_error = str(e)
            print(f"IC Error: {e}")
            return False
        except Exception as e:
            self.last_error = str(e)
            print(f"Unexpected Error: {e}")
            return False

    def _turn_on_bit(self, bit_position):
        if 0 <= bit_position <= 7:
            self.bits |= (1 << bit_position)
            return self.write_max7320_zero(self.bits)
        raise ValueError("Bit position must be between 0 and 7.")

    def _turn_off_bit(self, bit_position):
        if 0 <= bit_position <= 7:
            self.bits &= ~(1 << bit_position)
            return self.write_max7320_zero(self.bits)
        raise ValueError("Bit position must be between 0 and 7.")


if __name__ == "__main__":
    controller = EMC_Board()
    controller.turn_off_all()
    print("All outputs OFF")