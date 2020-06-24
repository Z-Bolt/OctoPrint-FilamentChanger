import time
import re
import click
from octoprint_zbolt_octoscreen.notifications import Notifications


class AsyncRequest:
    def __init__(self, printer):
        self._printer = printer
        pass

    def handleCmdResponse(self, cmd, condition, callback, env):
        pass

    def handleCmdExecution(self, cmd, callback):
        pass

    def handleMessage(self, cmd, callback):
        pass

    def on_gcode_received(self):
        pass


class FilamentChecker:
    def __init__(self, logger, printer, settings):
        self._logger = logger
        self._printer = printer
        self._settings = settings
        self._active_tool = 0
        self._reserve_tool = 1

        # Flags
        self._status = [0, 0, 0, 0]
        self._paused_due_filament_over = False
        self._print_pause_position = None
        self._activated_reservation = {}

        self.reload_settings()

    def reload_settings(self):
        # self._reservation = self._settings.get_filament_reservation()
        pass

    def on_printing_started(self):
        self._logger.info("Z-Bolt enable filament sensors")
        self._paused_due_filament_over = False


        if not self._status[self._active_tool]:
            Notifications.send_message(
                {
                    "title": "Cannot start printing", 
                    "text": "Filament in extruder {} is over.".format(self._active_tool)
                }
            )
            self._printer.cancel_print()


    def on_print_resumed(self):
        # if not self._settings.use_filament_sensors():
        #     return
        if self._paused_due_filament_over:
            self._paused_due_filament_over = False
            if self._print_pause_position:
                if self._resume_printing():
                    self._print_pause_position = None

        self._guarantee_filament_presence()


    def on_complete_reserve_switch(self):
        # p = self._print_pause_position
        # self._printer.commands(
        #     [
        #         "G0 X{} Y{} Z{}".format(p["x"], p["y"], p["z"]),
        #         "G92 E{}".format(p["e"]),
        #     ]
        # )
        
        if self._resume_printing():
            self._paused_due_filament_over = False
            self._printer.set_job_on_hold(False)
            self._print_pause_position = None


    def on_tool_change(self, old, new):
        self._active_tool = new
        # 
        if new == 1:
            self._reserve_tool = 0
        else:
            self._reserve_tool = 1

        self._guarantee_filament_presence()

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

    # def handle_reservation_gcode(self, cmd):
    #     if not self._printer.is_printing():
    #         return cmd
            
    #     for r in self._activated_reservation:
    #         cmd = cmd.replace(r, self._activated_reservation[r])

    #     return cmd

    def on_position_received(self, line):
        if self._paused_due_filament_over and not self._print_pause_position:
            self._print_pause_position = Response.parse_position_line(line)
            self._logger.info("Saving position _paused_due_filament_over")
            self._logger.info(line)
            self._logger.info(self._print_pause_position)


    def _guarantee_filament_presence(self):
        if self._paused_due_filament_over or not self._printer.is_printing():
            self._logger.info(
                "Ignore _guarantee_filament_presence: {}".format(
                    self._paused_due_filament_over
                )
            )
            return

        self._logger.info("Check current tool {}".format(self._active_tool))

        if not self._status[self._active_tool]:
            if self._status[self._reserve_tool] and self._settings.filament_auto_change():
                self._switch_to_reserver_tool()
            else:
                self._put_on_hold(self._active_tool)


    def _put_on_hold(self, tool):
        self._logger.error("Stopping printing")
        Notifications.send_message(
            {
                "title": "Filament is over",
                "text": "It seems like filament in extruder {} is over.\nPlease fix it and resume printing.".format(tool+1),
            }
        )
        self._paused_due_filament_over = True
        self._printer.pause_print()

        # Service position should not be X0 Y0 due to offsets. In some cases it can lead to
        gcode = self._settings.put_on_hold_gcode()
        self._printer.commands(gcode.split("\n"))

    def _switch_to_reserver_tool(self):
        self._printer.set_job_on_hold(True)
        self._paused_due_filament_over = True
        
        self._logger.info("Switching from tool {} to reserved tool {}.".format(self._active_tool, self._reserve_tool))

        gcode = self._settings.filament_change_gcode()

        try:
            gcode = gcode.format(
                RESERVE_TOOL_NUM = self._reserve_tool,
            )
        except ValueError:
            self._put_on_hold(self._active_tool)
            Notifications.send_message(
                {
                    "title": "Filament Switching Error",
                    "text": "Unable to switch filament due to error in the code",
                }
            )
            return

        self._printer.commands(gcode.split("\n"))
        # self._printer.commands([
        #     "M114",
        #     "G91", "G0 Z2", "G90",
        #     "G0 X10 Y10",
        #     "T{}".format(self._reserve_tool),
        #     "M118 zbtc:complete_reserve_switch"
        # ])


    def _resume_printing(self):
        gcode = self._settings.resume_printing_gcode()

        try:
            p = self._print_pause_position
            gcode = gcode.format(
                X_PRINTING_POS = p["x"],
                Y_PRINTING_POS = p["y"],
                Z_PRINTING_POS = p["z"],
                E_PRINTING_POS = p["e"]
            )
        except ValueError:
            self._put_on_hold(self._active_tool)
            Notifications.send_message(
                {
                    "title": "Filament Switching Error",
                    "text": "Unable to switch filament due to error in the code",
                }
            )
            return False

        self._printer.commands(gcode.split("\n"))
        return True


class Response(object):
    # This code was copied from the OctoPrint comm.pi file in order to sidestep an issue
    # where position responses with spaces after a colon (for example:  ok X:150.0 Y:150.0 Z:  0.7 E:  0.0)
    # were not being detected as a position response, and failed to file a PositionReceived event
    regex_float_pattern = "[-+]?[0-9]*\.?[0-9]+"
    regex_e_positions = re.compile(
        "E(?P<id>\d+):(?P<value>{float})".format(float=regex_float_pattern)
    )
    regex_position = re.compile(
        "X:\s*(?P<x>{float})\s*Y:\s*(?P<y>{float})\s*Z:\s*(?P<z>{float})\s*((E:\s*(?P<e>{float}))|(?P<es>(E\d+:{float}\s*)+))".format(
            float=regex_float_pattern
        )
    )

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
            result = dict(
                x=float(match.group("x")),
                y=float(match.group("y")),
                z=float(match.group("z")),
            )
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
        if "X:" in line and "Y:" in line and "Z:" in line:
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
                return {"x": x, "y": y, "z": z, "e": e}

        return False
