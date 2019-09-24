# coding=utf-8
from __future__ import absolute_import

# import logging
import octoprint.plugin
import flask
import socket

from octoprint.events import Events
from octoprint_zbolt.toolchanger import ToolChanger
from octoprint_zbolt.filament_checker import FilamentChecker
from octoprint_zbolt.notifications import Notifications
from octoprint_zbolt.settings import ZBoltSettings


class ZBoltPlugin(octoprint.plugin.SettingsPlugin,
                    octoprint.plugin.EventHandlerPlugin,
                    octoprint.plugin.TemplatePlugin,
                    octoprint.plugin.AssetPlugin,
                    octoprint.plugin.SimpleApiPlugin,
                    octoprint.plugin.StartupPlugin):

    def initialize(self):
        self._logger.info("Z-Bolt Toolchanger init")
        self.Notifications = Notifications()
        self.Settings = ZBoltSettings(self._settings)
        self.ToolChanger = ToolChanger(self._printer, self.Settings, self._logger)
        self.FilamentChecker = FilamentChecker( 
            self._logger, 
            self._printer, 
            self.ToolChanger, 
            self.Notifications,
            self.Settings
        )

    def get_assets(self):
        return dict(
            less=['less/theme.less'],
            js=['js/zbolt.js'],
            css=['css/main.css', 'css/theme.css']
        )

    def get_settings_defaults(self):
        return ZBoltSettings.default_settings()

    def get_api_commands(self):
        return dict(
            get_z_offset=["tool"],
            set_z_offset=["tool", "value"],
            get_notification=[],
            problem_occurs=[],
            problem_solved=[]
        )

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

    def on_api_command(self, command, data):
        if command == "get_z_offset":
            return flask.jsonify(offset = self.Settings.get_z_offset(data.get("tool")))
        elif command == "set_z_offset":
            self.Settings.set_z_offset(data.get("tool"), data.get("value"))
            return flask.jsonify("OK")
        elif command == "get_notification":
            return flask.jsonify(message = self.Notifications.get_message_to_display())
        elif command == "problem_occurs":
            self._printer.pause_print()
            data = {
                "type": "filament-over", "msg": "Filament eroor"
            }
            self._plugin_manager.send_plugin_message(self._identifier, data)

            return flask.jsonify("problem_occurs")
        elif command == "problem_solved":
            return flask.jsonify("problem_solved")

    def on_api_get(self, request):
        return flask.jsonify(printer_name="test2")

    def on_event(self, event, payload):
        if event is Events.HOME:
            self.ToolChanger.on_axis_homed()
        elif event is Events.TOOL_CHANGE:
            self._logger.info("event to change tool")
            if self.ToolChanger.on_tool_change(payload['old'], payload['new']):
                self._logger.info("release_job_from_hold")
                self._printer.set_job_on_hold(False)
        elif event is Events.CONNECTED:
            self._logger.info("Z-Bolt checking current tool")
            self.ToolChanger.initialize()
        elif event is Events.SETTINGS_UPDATED:
            self._logger.info("Z-Bolt reloading toolchanger")
            self.ToolChanger.initialize()
        elif event is Events.PRINT_STARTED:
            self._logger.info("Z-Bolt enable sensors")
            self.FilamentChecker.enable_monitoring()
            self.ToolChanger.on_printint_started()
        elif event in (Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED):
            self._logger.info("Z-Bolt disable sensors")
            self.FilamentChecker.disable_monitoring()
            self.ToolChanger.on_printint_stopped()
        elif event is Events.PRINT_RESUMED:
            self.FilamentChecker.on_print_resumed()

    def on_gcode_received(self, comm, line, *args, **kwargs):
        if "zbtc:tool_deactivated" in line:
            self.ToolChanger.on_tool_deactivated()
        elif "zbtc:tool_activated" in line:
            if self.ToolChanger.on_tool_activated():
                self._logger.info("release_job_from_hold")
                self._printer.set_job_on_hold(False)
        elif "M114" in line:
            self.FilamentChecker.on_position_received(line)
        return line

    def on_gcode_sending(self, comm_instance, phase, cmd, cmd_type, gcode, *args, **kwargs):
        if cmd[0] == 'T':
            self._logger.info("set_job_on_hold")
            self._printer.set_job_on_hold(True)

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
        "octoprint.comm.protocol.gcode.sending": (__plugin_implementation__.on_gcode_sending, -1),
        # "octoprint.comm.protocol.gcode.queuing": (__plugin_implementation__.on_gcode_queuing, -1),
        "octoprint.comm.protocol.gcode.received": (__plugin_implementation__.on_gcode_received, -1),
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
