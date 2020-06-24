filament_change_gcode = """M114
G91
G0 Z2
G90
G0 X10 Y10
T{RESERVE_TOOL_NUM}
M118 zbtc:complete_reserve_switch
"""

resume_printing_gcode = """G0 X{X_PRINTING_POS} Y{Y_PRINTING_POS} Z{Z_PRINTING_POS}
G92 E{E_PRINTING_POS}
"""

put_on_hold_gcode = """M114
G91
G0 Z2
G90
G91
G0 E-50
G90
G0 X10 Y180
"""

class ZBoltFCSettings(object):
    def __init__(self, settings):
        self._settings = settings

    def get_all(self):
        return {
            "filament_auto_change": float(self._settings.get(["filament_auto_change"])),
            "filament_change_gcode": float(self._settings.get(["filament_change_gcode"])),
            "resume_printing_gcode": float(self._settings.get(["resume_printing_gcode"])),
            "put_on_hold_gcode": float(self._settings.get(["put_on_hold_gcode"])),
        }

    def filament_auto_change(self):
        return bool(self._settings.get(["filament_auto_change"]))

    def filament_change_gcode(self):
        return self._settings.get(["filament_change_gcode"])

    def resume_printing_gcode(self):
        return self._settings.get(["resume_printing_gcode"])

    def put_on_hold_gcode(self):
        return self._settings.get(["put_on_hold_gcode"])

    @staticmethod
    def default_settings():
        return dict(
            filament_auto_change = 1,
            filament_change_gcode = filament_change_gcode,
            resume_printing_gcode = resume_printing_gcode,
            put_on_hold_gcode = put_on_hold_gcode
        )
