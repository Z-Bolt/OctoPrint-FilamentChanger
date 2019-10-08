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
        self._is_changing_tool = False

    def initialize(self):
        self._active_tool = 0
        # self._is_printing_now = False
        # self._tool_activation_guaranteed = False
        self._skip_movement = False
        self._axis_homed = False
        self._deactivating_tool_num = None
        self._activating_tool_num = None
        self._is_changing_tool = False
        self._changing_tool_buffer = []
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
                self._activate_tool(0)
            else:
                self._activate_tool_silently(tool)

    def get_active_tool(self):
        return self._active_tool

    def on_tool_change(self, old, new):
        if self._skip_movement:
            self._skip_movement = False
            return True

        if self._use_sensors:
            old = self._sensors.get_active_tool()
            self._active_tool = old 

        if old == new:
            return True

        if not self._printer.is_printing():
            self._deactivate_and_activate_tool(old, new)
            return True

        self._is_changing_tool = True
        self._deactivating_tool_num = old
        self._activating_tool_num = new
        self._tool_deactivation_attempts = 0
        self._tool_activation_attempts = 0
        self._deactivate_tool(self._deactivating_tool_num)

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

        return True

    def on_axis_homed(self):
        self._axis_homed = True

    def on_printing_started(self):
        if self._use_sensors:
            tool = self._sensors.get_active_tool()

            if tool == -1:
                self._activate_tool(0)
            else:
                self._activate_tool(tool)

    def on_printing_stopped(self):
        self.initialize()

    def _deactivate_tool(self, tool):
        self._guarantee_axis_homed()
        self._tool_deactivation_attempts += 1

        self._printer.commands(self._deactive_tool_gcode(tool))
        self._printer.commands([
            "M400", 
            "M118 zbtc:tool_deactivated"
        ])

    def _activate_tool(self, tool):
        if not tool in [0,1,2,3]:
            return

        self._guarantee_axis_homed()
        self._tool_activation_attempts += 1
        self._activating_tool_num = tool
    
        self._printer.commands(self._active_tool_gcode(tool))
        self._printer.commands([
            "M400", 
            "M118 zbtc:tool_activated"
        ])
        self._active_tool = tool

    def _activate_tool_silently(self, tool):
        self._skip_movement = True
        self._printer.commands([
            "T{}".format(tool)
        ])
        self._active_tool = tool

    def _deactivate_and_activate_tool(self, old, new):
        self._guarantee_axis_homed()
        self._active_tool = new 
        gcode = self._deactive_tool_gcode(old) + self._active_tool_gcode(new) 
        self._printer.commands(gcode)

    def _guarantee_tool_deactivation(self):
        if not self._use_sensors:
            return True

        if self._tool_deactivation_attempts > RETRY_ATTEMPTS:
            self._printer.set_job_on_hold(False)

            if self._printer.is_printing():
                self._printer.pause_print()

            self._printer.commands(self._emergency_deativation_gcode())

            Notifications.display("Printer cannot activate tool {}.\nPlease fix it and resume printing.".format(self._activating_tool_num+1))
            return False

        if not self._sensors.is_no_active_tool():
            self._deactivate_tool(self._deactivating_tool_num)
            return False
        
        return True

    def _guarantee_tool_activation(self):
        if not self._use_sensors:
            return True

        if self._tool_activation_attempts > RETRY_ATTEMPTS:
            self._printer.set_job_on_hold(False)

            if self._printer.is_printing():
                self._printer.pause_print()

            Notifications.display("Printer cannot activate tool {}.\nPlease fix it and resume printing.".format(self._activating_tool_num+1))
            return False

        if not self._sensors.is_tool_active(self._activating_tool_num):
            self._activate_tool(self._activating_tool_num)
            return False

        return True

    def _guarantee_axis_homed(self):
        if self._axis_homed:
            return

        self._printer.commands("G28")
        self._axis_homed = True

    def _active_tool_gcode(self, tool):
        o = self.offsets[tool]
        return [
            "G90",
            "G0 X{} Y0 F8000".format(self.parking_x[tool]),
            "G0 Y{} F8000".format(self.parking_safe_y),
            "G0 Y{} F1200".format(self.parking_y),
            "SET_PIN PIN=sol VALUE=1",
            "G4 P500",
            "G0 Y{} F1200".format(self.parking_safe_y),
            "G0 Y0 F8000",
            "G91",
            "G0 Z-1",
            "G90",
            "SET_GCODE_OFFSET X={} Y={} Z={}".format(o['x'], o['y'], o['z'])
        ]
        
    def _deactive_tool_gcode(self, tool):
        return [
            "SET_GCODE_OFFSET X=0 Y=0 Z=0",
            "G91",
            "G0 Z1",
            "G90",
            "G0 X{} Y0 F8000".format(self.parking_x[tool]),
            "G0 Y{} F8000".format(self.parking_safe_y),
            "G0 Y{} F1200".format(self.parking_y),
            "SET_PIN PIN=sol VALUE=0",
            "G4 P500",
            "G0 Y{} F1200".format(self.parking_safe_y),
            "G0 Y0 F8000"
        ]

    def _emergency_deativation_gcode(self):
        return [
            "G91",
            "G0 Y50",
            "G90",
            "SET_PIN PIN=sol VALUE=1"
        ]


