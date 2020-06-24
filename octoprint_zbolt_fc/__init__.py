# coding=utf-8
from __future__ import absolute_import

# import logging
import octoprint.plugin
import flask
import socket

from octoprint.events import Events
from octoprint_zbolt_octoscreen.notifications import Notifications
from octoprint_zbolt_fc.filament_checker import FilamentChecker
from octoprint_zbolt_fc.settings import ZBoltFCSettings

class ZBoltPlugin(octoprint.plugin.SettingsPlugin,
                    octoprint.plugin.EventHandlerPlugin,
                    octoprint.plugin.TemplatePlugin,
                    octoprint.plugin.AssetPlugin,
                    # octoprint.plugin.SimpleApiPlugin,
                    octoprint.plugin.StartupPlugin
                    ):

    def initialize(self):
        self._logger.info("Z-Bolt Toolchanger init")
        self.Settings = ZBoltFCSettings(self._settings)
        
        self.FilamentChecker = FilamentChecker( 
            self._logger, 
            self._printer, 
            self.Settings
        )

    def get_assets(self):
        return dict(
            # less=['less/theme.less'],
            js=['js/zbolt.js'],
            # css=['css/main.css', 'css/theme.css']
        )

    def get_settings_defaults(self):
        return ZBoltFCSettings.default_settings()


    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

    def on_event(self, event, payload):
        if event is Events.TOOL_CHANGE:
            self.FilamentChecker.on_tool_change(payload['old'], payload['new'])
        elif event is Events.CONNECTED:
            self._printer.commands(['FIRMWARE_RESTART'])
        elif event is Events.SETTINGS_UPDATED:
            self._logger.info("Z-Bolt FC reloading config")
            self.FilamentChecker.reload_settings()
        elif event is Events.PRINT_STARTED:
            self.FilamentChecker.on_printing_started()
        # elif event in (Events.PRINT_DONE, Events.PRINT_CANCELLED):
            # self._logger.info("Z-Bolt FC printing stopped: {}".format(event))
            # self.FilamentChecker.on_printing_stopped()
        elif event is Events.PRINT_RESUMED:
            self.FilamentChecker.on_print_resumed()

    def on_gcode_received(self, comm, line, *args, **kwargs):
        if "zbtc:extruder" in line:
            self.FilamentChecker.on_sensor_triggered(line)
        elif "zbtc:complete_reserve_switch" in line:
            self.FilamentChecker.on_complete_reserve_switch()
        elif 'X:' in line and 'Y:' in line and 'Z:' in line:
            self.FilamentChecker.on_position_received(line)

        return line


    def get_template_configs(self):
        return [
            dict(type="settings", name="Z-Bolt FilamentChanger", custom_bindings=False),
        ]

    ##~~ Softwareupdate hook
    def get_update_information(self):
        return dict(
        zbolt=dict(
            displayName = "Z-Bolt Printer",
            displayVersion = self._plugin_version,

            type="github_release",
            user="Z-Bolt",
            repo="OctoPrint-Z-Bolt-FilamentChanger",
            current=self._plugin_version,

            pip="https://github.com/Z-Bolt/OctoPrint-Z-Bolt-Printer/archive/{target_version}.zip"
            )
        )


__plugin_name__ = "Z-Bolt FilamentChanger"

def __plugin_load__():
    global __plugin_implementation__    
    __plugin_implementation__ = ZBoltPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        # "octoprint.filemanager.analysis.factory": (__plugin_implementation__.on_gcode_analyse, -1),
        # "octoprint.comm.protocol.gcode.queuing": (__plugin_implementation__.on_gcode_queuing, -1),
        "octoprint.comm.protocol.gcode.received": (__plugin_implementation__.on_gcode_received, -1),
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
