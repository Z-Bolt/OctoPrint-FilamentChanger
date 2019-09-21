$(function() {

    function ZBViewModel(parameters) {
        var self = this;
        self.settings = parameters[0];


        // self.onBeforeBinding = function() {
        //     // $("#customControls_containerTemplate_collapsable, #customControls_containerTemplate_nameless").html(function() {
        //     //     return $(this).html().replace(/"custom_section">/g, '"custom_section" data-bind="css: { plugin_control: (plugin_control) }">');
        //     // });
        //     // self.settings = self.settings.settings.plugins.zbolt;
        // };
    }

    // OCTOPRINT_VIEWMODELS.push([
    //     ZBViewModel, ["settingsViewModel"]
    //     ["#settings_plugin_zbolt"]
    // ]);

    OCTOPRINT_VIEWMODELS.push({
        construct: KlipperSettingsViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_zbolt"]
    });

    function ZBConnectionViewModel(parameters) {
        var self = this;

        // var faviconUrl = document.querySelector("link[rel~='mask-icon-theme']").href
        // || link.href
        // || window.location.origin + "/favicon.ico";


        self.onAfterBinding = function() {
            var connection = $("#sidebar_plugin_klipper");
            connection.collapse("hide");
         }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: ZBConnectionViewModel,
        dependencies: ["connectionViewModel"]
    });


    function ZBStateViewModel(parameters) {
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
            console.log('!!!---!!!----!!!')
            if (plugin !== "zbolt") {
                return;
            }
            console.log('---!!!----')
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
        construct: ZBStateViewModel,
        dependencies: ["loginStateViewModel","printerStateViewModel"]
    });

});


