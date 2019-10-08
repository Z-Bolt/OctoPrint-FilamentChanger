try:
    import RPi.GPIO as GPIO
except ImportError:	
    import FakeRPi.GPIO as GPIO

class ToolChangerSensors:

    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) 
        self._pins = [37,35,33,31]

        for p in self._pins:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def get_active_tool(self):
        for i in range(len(self._pins)): 
            if GPIO.input(self._pins[i]) == GPIO.LOW:
                return i
        return -1

    def is_tool_active(self, tool):
        return GPIO.input(self._pins[tool]) == GPIO.LOW

    def is_no_active_tool(self):
        return self.get_active_tool() == -1