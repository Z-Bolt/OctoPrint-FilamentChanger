import time
import re

try:
    import RPi.GPIO as GPIO
except ImportError:	
    import FakeRPi.GPIO as GPIO

class FilamentChecker:

    def __init__(self, logger, printer, toolchanger, notifications, settings):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD) 

        self._logger = logger
        self._printer = printer
        self._toolchanger = toolchanger
        self._notifications = notifications
        self._pins = [ 40,38,36 ]
        self._bounce = 50
        self._paused_due_filament_over = False
        self._print_pause_position = None
        self._settings = settings

        for p in self._pins:
            GPIO.setup(p, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def enable_monitoring(self):
        if not self._settings.use_filament_sensors():
            return

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

    def on_position_received(self, line):
        if self._paused_due_filament_over:
            self._print_pause_position = Response.parse_position_line(line)

    def on_print_resumed(self):
        if self._paused_due_filament_over:
            p = self._print_pause_position
            self._paused_due_filament_over = False
            self._printer.commands([
                "G0 X{}, Y{}, Z{}".format(p["x"], p["y"], p["z"])
                ])

    def _check_gpio(self, pin):
        time.sleep(1)
        tool = self._toolchanger.get_active_tool()
        pin = self._pins[tool]
        state = GPIO.input(pin)

        self._logger.error("filament: {}, {}, {}".format(tool, pin, state))

        if not state and self._printer.is_printing():
            self._paused_due_filament_over = True
            self._printer.commands(["M114"])
            self._notifications.display("It seems like filament in current extruder is over. Please fix it and resume printing.")
            self._printer.pause_print()
            self._printer.commands(["G90", "G0 E-400 F5000", "G0 E-400 F5000", "G91"])


class Response(object):
    # This code was copied from the OctoPrint comm.pi file in order to sidestep an issue
    # where position responses with spaces after a colon (for example:  ok X:150.0 Y:150.0 Z:  0.7 E:  0.0)
    # were not being detected as a position response, and failed to file a PositionReceived event
    regex_float_pattern = "[-+]?[0-9]*\.?[0-9]+"
    regex_e_positions = re.compile("E(?P<id>\d+):(?P<value>{float})".format(float=regex_float_pattern))
    regex_position = re.compile(
        "X:\s*(?P<x>{float})\s*Y:\s*(?P<y>{float})\s*Z:\s*(?P<z>{float})\s*((E:\s*(?P<e>{float}))|(?P<es>(E\d+:{float}\s*)+))"
        .format(float=regex_float_pattern))

    @staticmethod
    def parse_position_line(line):
        """
        Parses the provided M114 response line and returns the parsed coordinates.

        Args:
            line (str): the line to parse

        Returns:
            dict or None: the parsed coordinates, or None if no coordinates could be parsed
        """

        match = Response.regex_position.search(line)
        if match is not None:
            result = dict(x=float(match.group("x")),
                          y=float(match.group("y")),
                          z=float(match.group("z")))
            if match.group("e") is not None:
                # report contains only one E
                result["e"] = float(match.group("e"))

            elif match.group("es") is not None:
                # report contains individual entries for multiple extruders ("E0:... E1:... E2:...")
                es = match.group("es")
                for m in Response.regex_e_positions.finditer(es):
                    result["e{}".format(m.group("id"))] = float(m.group("value"))

            else:
                # apparently no E at all, should never happen but let's still handle this
                return None

            return result

        return None

    @staticmethod
    def check_for_position_request(line):
        ##~~ position report processing
        if 'X:' in line and 'Y:' in line and 'Z:' in line:
            parsed = Response.parse_position_line(line)
            if parsed:
                # we don't know T or F when printing from SD since
                # there's no way to query it from the firmware and
                # no way to track it ourselves when not streaming
                # the file - this all sucks sooo much

                x = parsed.get("x")
                y = parsed.get("y")
                z = parsed.get("z")
                e = None
                if "e" in parsed:
                    e = parsed.get("e")
                return {'x': x, 'y': y, 'z': z, 'e': e, }

        return False
