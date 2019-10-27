import time
import re
import click
from octoprint_zbolt_octoscreen.notifications import Notifications


class FilamentChecker:
    def __init__(self, logger, printer, toolchanger, settings):
        self._logger = logger
        self._printer = printer
        self._toolchanger = toolchanger
        self._settings = settings

        # Flags
        self._status = [0, 0, 0, 0]
        self._paused_due_filament_over = False
        self._print_pause_position = None
        self._activated_reservation = {}

        self.reload_settings()

    def reload_settings(self):
        self._reservation = self._settings.get_filament_reservation()

    def on_printing_started(self):
        if not self._settings.use_filament_sensors():
            return

        self._logger.info("Z-Bolt enable filament sensors")
        self._paused_due_filament_over = False
        self._activated_reservation = {}

        errors = []
        job = self._printer.get_current_job()
        # reserve = self._settings.get_filament_reservation()

        toolsGoingToUse = []
        reserveToolsForThisJob=[]

        for t in job["filament"]:
            toolNum = int(t[4])
            toolsGoingToUse.append(toolNum)

            if self._reservation[toolNum] >= 0:
                reserveToolsForThisJob.append(self._reservation[toolNum])

            if toolNum in self._reservation:
                errors.append(
                    "Tool {} was defined as reserved, so it can't be used as a main tool.".format(
                        toolNum + 1
                    )
                )

        for toolNum in list(set().union(toolsGoingToUse, reserveToolsForThisJob)):
            if not self._status[toolNum]:
                errors.append("Filament in extruder {} is over.".format(toolNum + 1))

        # for t in job["filament"]:
        #     toolNum = int(t[4])
        #     # Check that tools from gcode have filament
        #     if not self._status[toolNum]:
        #         errors.append("Filament in extruder {} is over.".format(toolNum + 1))

        #     if toolNum in reserve:
        #         errors.append(
        #             "Tool {} was defined as reserved, so it can't be used as a main tool.".format(
        #                 toolNum + 1
        #             )
        #         )
        # # Check that reserveted tools has filament
        # for r in reserve:
        #     if not self._status[toolNum]:
        #         errors.append("Filament in reserved extruder {} is over.".format(r + 1))

        # M118 zbtc:extruder:3:in:
        # M118 Klipper state: Ready

        if len(errors) > 0:
            errors.append("Please fix it and try again.")
            Notifications.send_message(
                {"title": "Cannot start printing", "text": "\n".join(errors)}
            )
            self._printer.cancel_print()

    def on_printing_stopped(self):
        self._activated_reservation = {}

    def on_print_resumed(self):
        if not self._settings.use_filament_sensors():
            return

        if self._paused_due_filament_over:
            self._paused_due_filament_over = False
            if self._print_pause_position:
                p = self._print_pause_position
                self._printer.commands(
                    [
                        "G0 X{} Y{} Z{}".format(p["x"], p["y"], p["z"]),
                        "G92 E{}".format(p["e"]),
                    ]
                )
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

    def handle_reservation_gcode(self, cmd):
        if not self._printer.is_printing():
            return cmd
            
        self._logger.info("handle_reservation_gcode")
        self._logger.info(cmd)
        for r in self._activated_reservation:
            cmd = cmd.replace(r, self._activated_reservation[r])
        self._logger.info(cmd)

        return cmd

    def on_position_received(self, line):
        if self._paused_due_filament_over and not self._print_pause_position:
            self._print_pause_position = Response.parse_position_line(line)
            self._logger.info("Saving position _paused_due_filament_over")
            self._logger.info(line)
            self._logger.info(self._print_pause_position)


    def _guarantee_filament_presence(self, tool=-1):
        if self._paused_due_filament_over or not self._printer.is_printing():
            self._logger.info(
                "Ignore _guarantee_filament_presence: {}".format(
                    self._paused_due_filament_over
                )
            )
            return

        if tool == -1:
            tool = self._toolchanger.get_active_tool()

        self._logger.info("Check current tool {}".format(tool))

        if not self._status[tool] and not self._reservation[tool]:
            self._put_on_hold(tool)
        elif not self._status[tool] and self._reservation[tool]:
            self._switch_tool(tool)

    def _put_on_hold(self, tool):
        self._logger.error("Stopping printing")
        Notifications.send_message(
            {
                "title": "Filament is over",
                "text": "It seems like filament in extruder {} is over.\nPlease fix it and resume printing.".format(tool),
            }
        )
        self._paused_due_filament_over = True
        self._printer.pause_print()

        # Service position should not be X0 Y0 due to offsets. In some cases it can lead to
        self._printer.commands(
            ["M114", "G91", "G0 Z2", "G90", "G91", "G0 E-50", "G90", "G0 X10 Y200"]
        )

    def _switch_tool(self, tool):
        self._logger.info("Switching to reserved tool.")
        reserve = self._reservation[tool]
        temperatures = self._printer.get_current_temperatures()
        target_temperature = temperatures['tool{}'.format(tool)]['target']

        self._printer.commands([
            "G0 X10 Y10",
            "M104 T{} S0".format(tool),
            "M104 T{} S{}".format(reserve, target_temperature),
            "M105",
            "M109 T{} S{}".format(reserve, target_temperature),
            "T{}".format(reserve)
        ])

        # self._activated_reservation["T{}".format(tool)] = "T{}".format(reserve)

        # M104 T1 S220
        # M105
        # M109 S220
        # M105
        # M109 T1 S220

        # {'bed': 
        # {'actual': 60.0, 'target': 60.0, 'offset': 0}, 
        # 'chamber': {'actual': None, 'target': None, 'offset': 0}, 
        # 'tool3': {'actual': 21.3, 'target': 0.0, 'offset': 0}, 
        # 'tool2': {'actual': 21.3, 'target': 0.0, 'offset': 0}, 
        # 'tool1': {'actual': 21.3, 'target': 0.0, 'offset': 0}, 
        # 'tool0': {'actual': 220.0, 'target': 220.0, 'offset': 0}
        # }
        # self._printer.pause_print()


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
