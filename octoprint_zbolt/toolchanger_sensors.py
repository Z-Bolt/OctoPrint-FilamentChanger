# import RPi.GPIO as GPIO
# import importlib.util

try:
    import RPi.GPIO as GPIO
except ImportError:	
    import FakeRPi.GPIO as GPIO

class ToolChangerSensors:

    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) 

        self.pins = [ 37,35,33 ]

        for p in self.pins:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def get_active_tool(self):
        # return 2
        for i in range(len(self.pins)): 
            if GPIO.input(self.pins[i]) == GPIO.HIGH:
                return i

        return -1

    def is_tool_active(self, tool):
        return GPIO.input(self.pins[tool]) == GPIO.HIGH


    def is_no_active_tool(self):
        # return True
        return self.get_active_tool() == -1