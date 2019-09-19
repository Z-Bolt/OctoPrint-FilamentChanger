import re
from octoprint_zbolt.toolchanger_sensors import ToolChangerSensors

RETRY_ATTEMPTS = 2

class ToolChanger():

    def __init__(self, printer, settings):
        self._sensors = None
        self._printer = printer
        self.Settings = settings
        # self._currentTool = 0
        # self.load_settings()

    def initialize(self):
        self._skip_movement = False
        self._tool_activation_guaranteed = False
        self._axis_homed = False
        self._changing_tool_from = None
        self._changing_tool_to = None
        self._tool_deactivation_attempts = 0
        self._tool_activation_attempts = 0        

        self.parking_x = self.Settings.get_parking_x()
        self.parking_y = self.Settings.get_parking_y()
        self.parking_safe_y = self.Settings.get_parking_safe_y()
        self.offsets = self.Settings.get_offsets()
        self._use_sensors = self.Settings.use_sensors()

        if self._use_sensors:
            self._sensors = ToolChangerSensors()
            tool = self._sensors.get_active_tool()
            if tool == -1:
                self._changing_tool_to = 0
                self.activate_tool()
            else:
                self.set_active_tool(tool)

    def set_active_tool(self, tool):
        self._skip_movement = True
        self._printer.commands([
            "T{}".format(tool)
        ])

    def change_tool(self, old, new):
        if self._skip_movement:
            self._skip_movement = False
            return

        if old == new:
            return

        self._changing_tool_from = old
        self._changing_tool_to = new
        self._tool_deactivation_attempts = 0
        self._tool_activation_attempts = 0

        self.deactivate_tool()

    def deactivate_tool(self):
        self._guarantee_axis_homed()

        self._tool_deactivation_attempts += 1
        self._printer.commands([
            "SET_GCODE_OFFSET X=0 Y=0 Z=0",
            "G91",
            "G0 Z1",
            "G90",
            "G0 X{} Y0 F8000".format(self.parking_x[self._changing_tool_from]),
            "G0 Y{} F8000".format(self.parking_safe_y),
            "G0 Y{} F1200".format(self.parking_y),
            "SET_PIN PIN=sol VALUE=0",
            "G0 Y{} F1200".format(self.parking_safe_y),
            "G0 Y0 F8000"])

        self._printer.commands([
            "M400", 
            "M118 zbtc:tool_deactivated"
            # "M118 zbtc:tool_deactivated old:{} new:{}".format(old, new)
        ])

    def activate_tool(self):
        if not self._guarantee_tool_deactivation():
            return
        
        self._guarantee_axis_homed()
        self._tool_activation_attempts += 1
        
        o = self.offsets[self._changing_tool_to]
        self._printer.commands([
            "G90",
            "G0 X{} Y0 F8000".format(self.parking_x[self._changing_tool_to]),
            "G0 Y{} F8000".format(self.parking_safe_y),
            "G0 Y{} F1200".format(self.parking_y),
            "SET_PIN PIN=sol VALUE=1",
            "G0 Y{} F1200".format(self.parking_safe_y),
            "G0 Y0 F8000",
            "G91",
            "G0 Z-1",
            "G90",
            "SET_GCODE_OFFSET X={} Y={} Z={}".format(o['x'], o['y'], o['z'])
        ])

        self._printer.commands([
            "M400", 
            "M118 zbtc:tool_activated"
        ])

    def check_tool(self):
        if not self._guarantee_tool_activation():
            return

        self._changing_tool_from = None
        self._changing_tool_to = None

    def axis_was_homed(self):
        self._axis_homed = True

    def _guarantee_tool_deactivation(self):
        if not self._use_sensors:
            return True

        if self._tool_deactivation_attempts > RETRY_ATTEMPTS:
            print("OMG!!!")
            self.set_active_tool(self._changing_tool_from)
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

