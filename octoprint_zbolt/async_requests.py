import re
import time

class HandleAsyncExecution:
    def __init__(self):
        self._pattern = "zbtc:request:{}".format(time.time())
        self._callback = None
        self._data = None

    def request(self, cmd):
        self._cmd = cmd

    def getGcode(self):
        return self._cmd + [
            "M114 "+ self._pattern
        ]

    def callback(self, callback, data):
        self._callback = callback
        self._data = data

    def check(self, cmd):
        return self._pattern in cmd

    def execute(self, cmd):
        self._callback(self._data, cmd)


class HandleAsyncResponce:
    def __init__(self):
        self._callback = None
        self._data = None

    def pattern(self, pattern):
        self._pattern = pattern

    def request(self, cmd):
        self._cmd = cmd

    def getGcode(self):
        return self._cmd

    def callback(self, callback, data):
        self._callback = callback
        self._data = data

    def check(self, cmd):
        return re.match(self._pattern, cmd)

    def execute(self, cmd):
        self._callback(self._data, cmd)


class AsyncRequestCallback:
    def __init__(self, printer):
        self._printer = printer
        self._queue = []
        pass

    def addHandler(self, handler):
        self._queue.append(handler)

    # def handleCmdResponse(self, cmd, condition, callback, env):
    #     pass

    # def handleCmdExecution(self, cmd, callback, data = {}):
    #     self._queue.append({
    #         "cmd": cmd,
    #         "pattern": cmd,
    #         "callback":callback,
    #         "data":data
    #     })

    # def handleMessages(self, cmd, callback):
    #     pass

    def on_gcode_received(self, cmd):
        for i, handler in enumerate(self._queue):
            if handler.check(cmd):
                handler.execute(cmd)
                del self._queue[i]
                break

        # handler = self._queue[0]
        # handler['callback'](handler['data'])
        # pass
