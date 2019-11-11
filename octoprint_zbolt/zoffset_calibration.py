import re

class ZOffsetCalibration:
    def __init__(self, printer, settings, logger):
        self._printer = printer
        self._logger = logger
        self._instance = None
        self.Settings = settings

    def run(self):
        self._logger.info("Starting Z Offset calibration")
        self._instance = ZOffsetCalibrationProcess(self._printer, self.Settings, self._logger)
        self._instance.run()

        # self._message = message

    def on_response_received(self, line):
        if not self._instance:
            return

        self._logger.info("on_response_received: {}".format(line))
        res = re.search('z=([-\d\.]+)', line)
        # offset = float(res[1]) # python 3
        offset = float(res.group(1)) # python 2.7

        if not self._instance.handleResult(offset):
            self._instance = None



# Send: PROBE
# [...]
# Recv: // probe at 50.000,50.000 is z=-0.302500
# Recv: // Result is z=-0.302500
# Recv: ok
# Result T0 is z=-0.327500 | -0.307500 |
# Result T1 is z=-0.245000 | -0.240000
# Result T2 
# Result T3 is z=-0.297500

class ZOffsetCalibrationProcess:
    def __init__(self, printer, settings, logger):
        self._printer = printer
        self._logger = logger
        self._tool_num = 0
        self._initial_offset = 0
        self._offsets = {}
        self.Settings = settings

    def run(self):
        self._printer.commands([
            "G28", "T0", "G0 X120 Y20 Z5 F8000", "PROBE"
        ])

    def handleResult(self, offset):
        self._offsets[self._tool_num] = offset

        if self._tool_num > 0:
            tool_offset = offset - self._offsets[0]
            self.Settings.set_z_offset(self._tool_num, tool_offset)
        
        if self._tool_num < 3:
            self._tool_num = self._tool_num + 1
            self._printer.commands([
                "G0 Z5",
                "T{}".format(self._tool_num), 
                "SET_GCODE_OFFSET Z=0",
                "G0 X120 Y20 Z5 F8000", "PROBE"
            ])

            return True
        else:
            self._printer.commands([
                "G0 Z5",
                "T0",
                "G28"
            ])

            return False

    # def mesure_for_too(self, tool_num):




        



