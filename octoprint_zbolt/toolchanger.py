class ToolChanger():

    def __init__(self, printer, settings):
        self._printer = printer
        self._settings = settings
        self._currentTool = 0
        self.load_settings()

    def load_settings(self):
        self.tools_x = [
            self._settings.get(["parking", "t0_x"]),
            self._settings.get(["parking", "t1_x"]),
            self._settings.get(["parking", "t2_x"]),
            self._settings.get(["parking", "t3_x"])
        ]

        self.parking_y = self._settings.get(["parking", "y"])
        self.parking_safe_y = self._settings.get(["parking", "safe_y"])

        self.offsets = [
            dict(x=0, y=0, z=0),
            dict(x=self._settings.get(["t1_offset", "x"]), y=self._settings.get(["t1_offset", "y"]), z=self._settings.get(["t1_offset", "z"])),
            dict(x=self._settings.get(["t2_offset", "x"]), y=self._settings.get(["t2_offset", "y"]), z=self._settings.get(["t2_offset", "z"])),
            dict(x=self._settings.get(["t3_offset", "x"]), y=self._settings.get(["t3_offset", "y"]), z=self._settings.get(["t3_offset", "z"]))
        ]

        self.axis_homed = False

    def changer_tool(self, old, new):
        if old == new:
            return

        self._guarantee_axis_homed()
        self._deactivate_tool(old)
        self._activate_tool(new)
    
    def axis_was_homed(self):
        self.axis_homed = True

    def _guarantee_axis_homed(self):
        if self.axis_homed:
            return

        self._printer.commands("G28")
        self.axis_homed = True

    def _deactivate_tool(self, num, homing_first=False):
        self._printer.commands([
            "SET_GCODE_OFFSET X=0 Y=0 Z=0",
            "G91",
            "G0 Z1"])

        self._printer.commands([
            "G90",
            "G0 X{} Y0 F8000".format(self.tools_x[num])])

        self._printer.commands([
            "G0 Y{} F8000".format(self.parking_safe_y),
            "G0 Y{} F1200".format(self.parking_y),
            "SET_PIN PIN=sol VALUE=0",
            "G0 Y{} F1200".format(self.parking_safe_y),
            "G0 Y0 F8000"])

    def _activate_tool(self, num):
        o = self.offsets[num]
        self._printer.commands([
            "G90",
            "G0 X{} Y0 F8000".format(self.tools_x[num]),
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

    def _reset_flags(self):
        self.flags = {
            "is_changing_tool" : False,
            "homing_first_error" : False
        }

