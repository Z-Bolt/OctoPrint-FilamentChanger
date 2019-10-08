ZBolt = {
    tools: [
        {
            value: "-1",
            name: "None"
        },
        {
            value: "0",
            name: "Extrudert 1"
        },
        {
            value: "1",
            name: "Extrudert 2"
        },
        {
            value: "2",
            name: "Extrudert 3"
        },
        {
            value: "3",
            name: "Extrudert 4"
        }
    ],

    toolsFor: function(tool){
        var tools = [];
        for (t in this.tools) {
            if (this.tools[t].value != tool) {
                tools.push(this.tools[t]);
            }
        }
        return tools;
    }
}

$(function() {

    ZBolt.FilamentSensorViewModel = function(parameters) {
        var self = this;
        self.settings = parameters[0];
        self.onBeforeBinding = function() {
        //     // $("#customControls_containerTemplate_collapsable, #customControls_containerTemplate_nameless").html(function() {
        //     //     return $(this).html().replace(/"custom_section">/g, '"custom_section" data-bind="css: { plugin_control: (plugin_control) }">');
        //     // });
        //     // self.settings = self.settings.settings.plugins.zbolt;
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        ZBolt.FilamentSensorViewModel, ["settingsViewModel"]
        ["#zbolt_filament_settings"]
    ]);
    

    ZBolt.StateViewModel = function(parameters) {
        var self = this;
        
        self.printerStateViewModel = parameters[0];

        self.printerStateViewModel.stateString.subscribe(function(p){
            var s = $('#state_wrapper');

            if (p == 'Printing') {
                s.addClass('printing')
            } else {
                s.removeClass('printing')
            }
        });

        self.onAfterBinding = function() {
        }

        // Handle Plugin Messages from Server
        self.onDataUpdaterPluginMessage = function (plugin, data) {

            if (plugin !== "zbolt") {
                return;
            }

            switch (data.type) {
                case "filament-over":{
                    //console.log('octolapse.js - render-failed');
                    self.updateState(data);
                    var options = {
                        title: 'Octolapse Rendering Failed',
                        text: data.msg,
                        type: 'error',
                        hide: false,
                        addclass: "zbolt",
                        desktop: {
                            desktop: true
                        }
                    };
                    // Octolapse.displayPopup(options);
                    new PNotify(options);
                    break;
                }
            }
        }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: ZBolt.StateViewModel,
        dependencies: ["printerStateViewModel"]
    });

    ZBolt.ConnectionViewModel = function(parameters) {
        var self = this;

        self.onAfterBinding = function() {
            var connection = $("#sidebar_plugin_klipper");
            connection.collapse("hide");
         }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: ZBolt.ConnectionViewModel,
        dependencies: ["connectionViewModel"]
    });


    // if (KlipperSettingsViewModel){
    //     OCTOPRINT_VIEWMODELS.push({
    //         construct: KlipperSettingsViewModel,
    //         dependencies: ["settingsViewModel"],
    //         elements: ["#settings_plugin_zbolt"]
    //     });
    // }
});


