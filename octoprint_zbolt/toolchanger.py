import re
from octoprint_zbolt.toolchanger_sensors import ToolChangerSensors

RETRY_ATTEMPTS = 2

class ToolChanger():

    def __init__(self, printer, settings):
        self._sensors = None
        self._printer = printer
        self.Settings = settings

    def initialize(self):
        self._active_tool = -1
        self._safe_toolchanging = False
        self._skip_movement = False
        self._tool_activation_guaranteed = False
        self._axis_homed = False
        self._changing_tool_from = None
        self._changing_tool_to = None
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
                self._changing_tool_to = 0
                self.activate_tool()
            else:
                self._set_active_tool_silently(tool)

    def get_active_tool(self):
        return self._active_tool

    def change_tool(self, old, new):
        if self._skip_movement:
            self._skip_movement = False
            return

        if old == new:
            return

        self._active_tool = new

        if not self._safe_toolchanging:
            self._deactivate_activate_tool(old, new)
        else:
            self._changing_tool_from = old
            self._changing_tool_to = new
            self._tool_deactivation_attempts = 0
            self._tool_activation_attempts = 0
            self.deactivate_tool()

    def deactivate_tool(self):
        self._guarantee_axis_homed()
        self._tool_deactivation_attempts += 1

        self._printer.commands(self._deactive_tool_gcode(self._changing_tool_from))
        self._printer.commands([
            "M400", 
            "M118 zbtc:tool_deactivated"
        ])

    def activate_tool(self):
        if not self._guarantee_tool_deactivation():
            return
        
        self._guarantee_axis_homed()
        self._tool_activation_attempts += 1
    
        self._printer.commands(self._active_tool_gcode(self._changing_tool_to))
        self._printer.commands([
            "M400", 
            "M118 zbtc:tool_activated"
        ])

    def _deactivate_activate_tool(self, old, new):
        self._guarantee_axis_homed()
        gcode = self._deactive_tool_gcode(old) + self._active_tool_gcode(new) 
        self._printer.commands(gcode)

    def check_tool(self):
        if not self._guarantee_tool_activation():
            return

        self._changing_tool_from = None
        self._changing_tool_to = None

    def axis_was_homed(self):
        self._axis_homed = True

    def enable_safe_toolchanging(self):
        self._safe_toolchanging = True

    def disable_safe_toolchanging(self):
        self._safe_toolchanging = False

    def _set_active_tool_silently(self, tool):
        self._skip_movement = True
        self._printer.commands([
            "T{}".format(tool)
        ])
        self._active_tool = tool

    def _guarantee_tool_deactivation(self):
        if not self._use_sensors:
            return True

        if self._tool_deactivation_attempts > RETRY_ATTEMPTS:
            print("OMG!!!")
            self.set_active_tool_silently(self._changing_tool_from)
            # TODO Here should be some logic of emergent stop!!!
            return False

        if not self._sensors.is_no_active_tool():
            self.deactivate_tool()
            return False
        
        return True

    def _guarantee_tool_activation(self):
        if not self._use_sensors:
            return True

        if self._tool_activation_attempts > RETRY_ATTEMPTS:
            print("OMG!!!")
            # TODO Here should be some logic of emergent stop!!!
            return False

        if not self._sensors.is_tool_active(self._changing_tool_to):
            self.activate_tool()
            return False

        return True

    def _guarantee_axis_homed(self):
        if self._axis_homed:
            return

        self._printer.commands("G28")
        self._axis_homed = True

    def _reset_flags(self):
        self.flags = {
            "is_changing_tool" : False,
            "homing_first_error" : False
        }

    def _parse_command(self, line):
        r = re.compile("old:\s*(?P<old>\d)\s*new:\s*(?P<new>\d)").search(line)
        return int(r.group("old")), int(r.group("new"))

    def _active_tool_gcode(self, tool):
        o = self.offsets[tool]
        return [
            "G90",
            "G0 X{} Y0 F8000".format(self.parking_x[tool]),
            "G0 Y{} F8000".format(self.parking_safe_y),
            "G0 Y{} F1200".format(self.parking_y),
            "SET_PIN PIN=sol VALUE=1",
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
            "G0 Y{} F1200".format(self.parking_safe_y),
            "G0 Y0 F8000"
        ]



