# coding=utf-8
from __future__ import absolute_import

# import logging
import octoprint.plugin
from octoprint.events import Events
import flask
import socket
from .toolchanger import ToolChanger


class ZBoltPlugin(octoprint.plugin.SettingsPlugin,
                    octoprint.plugin.EventHandlerPlugin,
                    octoprint.plugin.TemplatePlugin,
                    octoprint.plugin.AssetPlugin,
                    octoprint.plugin.SimpleApiPlugin,
                    octoprint.plugin.StartupPlugin):

    def initialize(self):
        self._logger.info("Z-Bolt Toolchanger init")
        self._toolchanger = ToolChanger(self._printer, self._settings)

    def get_settings_defaults(self):
        return dict(
            t1_offset = dict(x=0, y=0, z=0),
            t2_offset = dict(x=0, y=0, z=0),
            t3_offset = dict(x=0, y=0, z=0),
            parking = dict(safe_y=0, y=0, t0_x=0, t1_x=0, t2_x=0, t3_x=0)
        )


    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self._toolchanger.load_settings()

    def get_api_commands(self):
        return dict(
            get_z_offset=["tool"],
            set_z_offset=["tool", "value"]
        )

    def on_api_command(self, command, data):
        if command == "get_z_offset":
            tool = data.get("tool")
            if tool in [1,2,3]:
                offset = self._settings.get(["t%s_offset" % data.get("tool"), "z"])
            else: 
                offset = 0.0

            return flask.jsonify(offset = float(offset))

        elif command == "set_z_offset":
            self._logger.info("Set Z Offset for T{}: {}".format(data.get("tool"), data.get("value")))
            self._settings.set(["t%s_offset" % data.get("tool"), "z"], data.get("value"))
            self._settings.save()
            return flask.jsonify("OK")

        return "test1"

    def on_api_get(self, request):
        return flask.jsonify(printer_name="test2")


    def get_assets(self):
        return dict(
            less=['less/theme.less'],
            js=['js/zbolt.js'],
            css=['css/main.css', 'css/theme.css']
        )


    def on_event(self, event, payload):
        if event is Events.HOME:
            self._toolchanger.axis_was_homed()
        elif event is Events.TOOL_CHANGE:
            self._toolchanger.changer_tool(payload['old'], payload['new'])
            # self._logger.info("Tool was changed: {}, {}".format(payload['old'], payload['new']))


    def get_template_configs(self):
        return [
            dict(type="settings", name="Z-Bolt Printer", custom_bindings=False),
        ]

    ##~~ Softwareupdate hook
    def get_update_information(self):
        return dict(
        zbolt=dict(
            displayName = "Z-Bolt Printer",
            displayVersion = self._plugin_version,

            type="github_release",
            user="Z-Bolt",
            repo="OctoPrint-Z-Bolt-Printer",
            current=self._plugin_version,

            pip="https://github.com/Z-Bolt/OctoPrint-Z-Bolt-Printer/archive/{target_version}.zip"
            )
        )

__plugin_name__ = "Z-Bolt Printer"

def __plugin_load__():
    global __plugin_implementation__    
    __plugin_implementation__ = ZBoltPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        # "octoprint.comm.protocol.gcode.sending": __plugin_implementation__.on_gcode_sent,
        # "octoprint.comm.protocol.gcode.received": __plugin_implementation__.on_gcode_received,
        "octoprint.plugin.softwareupdate.check_config":__plugin_implementation__.get_update_information
    }
