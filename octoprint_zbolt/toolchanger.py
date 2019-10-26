import re
from octoprint_zbolt.toolchanger_sensors import ToolChangerSensors
from octoprint_zbolt.notifications import Notifications

RETRY_ATTEMPTS = 2

class ToolChanger():

    def __init__(self, printer, settings, logger):
        self._sensors = None
        self._printer = printer
        self._logger = logger
        self.Settings = settings


    # this method is called when klipper sends message "Klipper state: Ready" and after SETTINGS_UPDATED
    # so current implementation works only with klipper
    def initialize(self):
        self._logger.info("Reseting toolchanger state.")
        self._active_tool = 0
        self._press_down_tool_only = False
        self._axis_homed = False
        self._deactivating_tool_num = None
        self._activating_tool_num = None
        self._is_changing_tool = False
        self._tool_deactivation_attempts = 0
        self._tool_activation_attempts = 0        

        self._use_sensors = self.Settings.use_sensors()
        self.parking_x = self.Settings.get_parking_x()
        self.parking_y = self.Settings.get_parking_y()
        self.parking_safe_y = self.Settings.get_parking_safe_y()
        self.offsets = self.Settings.get_offsets()

        if self._use_sensors:
            self._sensors = ToolChangerSensors()
            tool = self._sensors.get_active_tool()
            if tool == -1:
                self._logger.info("No one tool is active. Fixing it.")
                self._activate_tool(0)
            else:
                self._press_down_tool(tool)

    def get_active_tool(self):
        return self._active_tool

    def on_tool_change_gcode(self, new):
        # This check should be done first. Otherwise with toolchanger will ignore next toolchanging.
        if self._press_down_tool_only: 
            self._logger.info("Pressing down already activated tool: {}".format(new))
            self._press_down_tool_only = False
            self._is_changing_tool = True
            self._activating_tool_num = new
            self._tool_activation_attempts = 0
            self._active_tool = new
            return self._active_tool_gcode(self._activating_tool_num)

        if new == self._active_tool:
            self._logger.info("Tool is already active: {} and {}".format(new, self._active_tool))
            self._is_changing_tool = False
            return []

        # if self._use_sensors:
        #     sensor_current = self._sensors.get_active_tool()
        #     if sensor_current != old:
        #         self._logger.info("Sensors info about active tool differs with octo's. Fixing it.")
        #         old = sensor_current
        #         self._active_tool = old

        self._printer.set_job_on_hold(True)
        self._logger.info("set_job_on_hold")

        self._is_changing_tool = True
        self._activating_tool_num = new
        self._deactivating_tool_num = self._active_tool
        self._tool_deactivation_attempts = 0
        self._tool_activation_attempts = 0
        self._active_tool = new

        if self._printer.is_printing():
            self._logger.info("Changing tool from {} to {}".format(self._deactivating_tool_num, self._activating_tool_num))
            self._logger.info("Deactivating tool {}.".format(self._deactivating_tool_num))
            return self._deactivate_tool_gcode(self._deactivating_tool_num, True)


        self._logger.info("Changing tool from {} to {} without sensors check.".format(self._deactivating_tool_num, self._activating_tool_num))        
        return self._deactivate_tool_gcode(self._deactivating_tool_num, False) + self._active_tool_gcode(self._activating_tool_num) 
        

    def on_tool_deactivated(self):
        if not self._guarantee_tool_deactivation():
            return

        self._activate_tool(self._activating_tool_num)

    def on_tool_activated(self):
        if not self._guarantee_tool_activation():
            return False

        self._activating_tool_num = None
        self._deactivating_tool_num = None
        self._is_changing_tool = False

        self._logger.info("release_job_from_hold")
        self._printer.set_job_on_hold(False)

    def on_axis_homed(self):
        self._axis_homed = True

    def on_printing_started(self):
        return 
        # if self._use_sensors:
        #     tool = self._sensors.get_active_tool()

        #     if tool == -1:
        #         self._activate_tool(0)
        #     else:
        #         self._activate_tool(tool)

    def on_printing_stopped(self):
        self.initialize()

    def _deactivate_tool(self, tool):
        self._logger.info("Deactivating tool {}.".format(tool))
        self._tool_deactivation_attempts += 1

        self._printer.commands(
            self._deactivate_tool_gcode(tool, True) + [
        ])

    def _activate_tool(self, tool):
        if not tool in [0,1,2,3]:
            return

        self._logger.info("Activating tool {}.".format(tool))

        self._tool_activation_attempts += 1
    
        self._printer.commands(
            self._active_tool_gcode(tool)
        )

    def _press_down_tool(self, tool):
        self._logger.info("Press down tool only {}".format(tool))
        self._press_down_tool_only = True
        self._printer.commands([
            "T{}".format(tool)
        ])

    # Utils methods

    def _guarantee_tool_deactivation(self):
        if not self._use_sensors:
            return True

        if self._tool_deactivation_attempts > RETRY_ATTEMPTS:
            self._logger.info("Tool was not deactivated. Stopping!!!")

            self._printer.set_job_on_hold(False)
            if self._printer.is_printing():
                self._printer.pause_print()

            self._printer.commands(self._emergency_deativation_gcode())

            Notifications.display("Printer cannot activate tool {}.\nPlease fix it and resume printing.".format(self._activating_tool_num+1))
            return False

        if not self._sensors.is_no_active_tool():
            self._logger.info("Tool {} was not deactivated. Trying again!".format(self._deactivating_tool_num))
            self._deactivate_tool(self._deactivating_tool_num)
            return False
        
        return True

    def _guarantee_tool_activation(self):
        if not self._use_sensors:
            return True

        if self._tool_activation_attempts > RETRY_ATTEMPTS:
            self._logger.info("Tool was not activated. Stopping!!!")

            self._printer.set_job_on_hold(False)
            if self._printer.is_printing():
                self._printer.pause_print()

            Notifications.display("Printer cannot activate tool {}.\nPlease fix it and resume printing.".format(self._activating_tool_num+1))
            return False

        if self._activating_tool_num is None:
            self._logger.info("Something happened!!! _activating_tool_num is None.")
            return True

        if not self._sensors.is_tool_active(self._activating_tool_num):
            self._logger.info("Tool {} was not activated. Trying again!!!".format(self._activating_tool_num))
            self._activate_tool(self._activating_tool_num)
            return False

        return True

    def _active_tool_gcode(self, tool):
        o = self.offsets[tool]
        return self._guarantee_axis_homed_gcode() + [
            "G90",
            "G0 X{} Y0 F10000".format(self.parking_x[tool]),
            "G0 Y{} F10000".format(self.parking_safe_y),
            "G0 Y{} F2000".format(self.parking_y),
            "SET_PIN PIN=sol VALUE=1",
            "G4 P500",
            "G0 Y{} F2000".format(self.parking_safe_y),
            "G0 Y0 F10000",
            "G91",
            "G0 Z-1",
            "G90",
            "SET_GCODE_OFFSET X={} Y={} Z={}".format(o['x'], o['y'], o['z']),
            "M400", 
            "M118 zbtc:tool_activated:{}".format(tool)
        ]
        
    def _deactivate_tool_gcode(self, tool, check_activation):

        gcode =  self._guarantee_axis_homed_gcode() + [
            "SET_GCODE_OFFSET X=0 Y=0 Z=0",
            "G91",
            "G0 Z1",
            "G90",
            "G0 X{} Y0 F10000".format(self.parking_x[tool]),
            "G0 Y{} F10000".format(self.parking_safe_y),
            "G0 Y{} F2000".format(self.parking_y),
            "SET_PIN PIN=sol VALUE=0",
            "G4 P500",
            "G0 Y{} F2000".format(self.parking_safe_y),
            "G0 Y0 F10000"
        ]

        if check_activation:
            gcode = gcode + ["M400", "M118 zbtc:tool_deactivated:{}".format(tool)]

        return gcode

    def _guarantee_axis_homed_gcode(self):
        if self._axis_homed:
            return []

        self._logger.info("No info that axis were homed so going home!!!")
        self._axis_homed = True
        return ["G28"]
        # self._printer.commands("G28")

    def _emergency_deativation_gcode(self):
        return [
            "G91",
            "G0 Y50",
            "G90",
            "SET_PIN PIN=sol VALUE=1"
        ]


