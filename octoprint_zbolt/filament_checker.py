import time
import re
from octoprint_zbolt.notifications import Notifications

class FilamentChecker:

    def __init__(self, logger, printer, toolchanger, settings):
        self._logger = logger
        self._printer = printer
        self._toolchanger = toolchanger
        self._status = [ 0, 0, 0, 0]
        self._paused_due_filament_over = False
        self._print_pause_position = None
        self._settings = settings

    def on_printing_started(self):
        if not self._settings.use_filament_sensors():
            return

        self._logger.info("Z-Bolt enable filament sensors")
        self._paused_due_filament_over = False

        if not self._check_current_tool():
            Notifications.display("It seems like filament in current extruder is over.\nPlease fix it.")

        # Check that reservation doesn't use in Gcode
        
        job = self._printer.get_current_job()
        self._logger.info(job['filament'])


    def on_printing_stopped(self):
        if not self._settings.use_filament_sensors():
            return

        self._logger.info("Z-Bolt disable filament sensors")

    def on_position_received(self, line):
        if self._paused_due_filament_over and not self._print_pause_position:
            self._print_pause_position = Response.parse_position_line(line)
            self._logger.info("Saving position _paused_due_filament_over")
            self._logger.info(line)
            self._logger.info(self._print_pause_position)

    def on_print_resumed(self):
        if not self._settings.use_filament_sensors():
            return

        if self._paused_due_filament_over:
            self._paused_due_filament_over = False
            if self._print_pause_position:
                p = self._print_pause_position
                self._printer.commands([
                    "G0 X{} Y{} Z{}".format(p["x"], p["y"], p["z"]),
                    "G92 E{}".format(p["e"])
                    ])
                self._print_pause_position = None
        self._guarantee_filament_presence()

    def on_tool_change(self, old, new):
        if not self._settings.use_filament_sensors():
            return

        self._guarantee_filament_presence(new)

    def on_sensor_triggered(self, line):
        line_arr = line.split(":")
        tool = int(line_arr[3])

        if line_arr[4] == "in":
            self._logger.info("Filament is in")
            self._status[tool] = 1
        else:
            self._logger.info("Filament is out")
            self._status[tool] = 0

        self._guarantee_filament_presence()

    def _guarantee_filament_presence(self, tool=-1):
        if self._paused_due_filament_over or not self._printer.is_printing():
            self._logger.info("Ignore _guarantee_filament_presence: {}".format(self._paused_due_filament_over))
            return

        self._logger.info("Check current tool _guarantee_filament_presence")

        if not self._check_current_tool(tool):
            self._logger.error("Stopping printing")
            Notifications.display("It seems like filament in current extruder is over.\nPlease fix it and resume printing.")
            self._paused_due_filament_over = True
            self._printer.pause_print()

            # Service position should not be X0 Y0 due to offsets. In some cases it can lead to 
            self._printer.commands([
                "M114", 
                "G91", "G0 Z2", "G90", 
                "G91", "G0 E-20", "G90", 
                "G0 X10 Y200"])

    def _check_current_tool(self, tool=-1):
        if tool == -1:
            tool = self._toolchanger.get_active_tool()

        self._logger.info("Checking filament presence for tool {}. Status is {}.".format(tool, self._status[tool]))
        return self._status[tool]


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
