import time

try:
    import RPi.GPIO as GPIO
except ImportError:	
    import FakeRPi.GPIO as GPIO

class FilamentChecker:

    def __init__(self, logger, printer, toolchanger, settings):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) 

        self._logger = logger
        self._printer = printer
        self._toolchanger = toolchanger
        self._pins = [ 40,38,36 ]
        self._bounce = 50

        for p in self._pins:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def enable_monitoring(self):
        for p in self._pins:
            try:
                GPIO.remove_event_detect(p)
            except:
                pass

        for p in self._pins:
            GPIO.add_event_detect(p, GPIO.FALLING, callback=self._check_gpio, bouncetime=self._bounce) 


    def disable_monitoring(self):
        for p in self._pins:
            try:
                GPIO.remove_event_detect(p)
            except:
                pass


    def _check_gpio(self, pin):
        time.sleep(1)
        tool = self._toolchanger.get_active_tool()
        pin = self._pins[tool]
        state = GPIO.input(pin)

        self._logger.error("filament: {}, {}, {}".format(tool, pin, state))

        if not state and self._printer.is_printing(): #no plastic
            self._printer.pause_print()

