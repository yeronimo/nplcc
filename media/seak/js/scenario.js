function progressViewModel() {
  var self = this;

  self.progressHtml = ko.observable();
  self.done = ko.observable(false);
  self.error = ko.observable(false);
  self.progressBarWidth = ko.observable("0%");
  self.triggerDone = function() {
    self.done(true);
    clearInterval(app.timer);
    app.timer = null;
  };
  self.checkTimer = function() {
    var checkProgress = function () {
        var url = $('#selected_progress_url').attr('value');
        var elem = $('#scenario_progress_html'); 
        if (elem.length === 0) { 
            self.triggerDone();
            return false; 
        }
        if (!self.done()) {
            $.get(url, function(data) {
                self.progressHtml(data.html);
                if (data.error == 1) {
                    self.error(true);
                    // stop timer without declaring done
                    clearInterval(app.timer);
                    app.timer = null;
                }
                var pct = parseInt((data.complete / data.total) * 100.0, 10);
                self.progressBarWidth(pct + "%");
                if (pct >= 100) {
                    self.triggerDone();
                }
            });
        }
    };
    if (!app.timer) {
        checkProgress();
        app.timer = setInterval(checkProgress, 5000);
    } else {
        console.log("Warning: app.timer is set and checkTimer was called!");
    }
 };
  
  return self;
}

function scenariosViewModel() {
  var self = this;

  // this will get bound to the active scenario
  self.selectedFeature = ko.observable(false);
  // display the form panel entirely
  self.showScenarioPanels = ko.observable();
  // display initial help
  self.showScenarioHelp = ko.observable(true);
  // display form
  self.showScenarioFormPanel = ko.observable(false);
  // display list of scenarios
  self.showScenarioList = ko.observable(true);
  self.scenarioLoadError = ko.observable(false);
  self.scenarioLoadComplete = ko.observable(false);
  self.reportLoadError = ko.observable(false);
  self.reportLoadComplete = ko.observable(false);
  self.planningUnitsLoadError = ko.observable(false);
  self.planningUnitsLoadComplete = ko.observable(false);
  self.formLoadError = ko.observable(false);
  self.formLoadComplete = ko.observable(true);
  // list of all scenarios, primary viewmodel
  self.scenarioList = ko.observableArray();
  // display mode
  self.dataMode = ko.observable('manage');

  // pagination config will display x items 
  // from this zero based index
  self.listStart = ko.observable(0);
  self.listDisplayCount = 9;

  // paginated list
  self.scenarioListPaginated = ko.computed(function () {
    return self.scenarioList.slice(self.listStart(), self.listDisplayCount+self.listStart());
  });

  // this list is model for pagination controls 
  self.paginationList = ko.computed(function () {
    var list = [], listIndex = 0, displayIndex = 1;
    for (listIndex=0; listIndex < self.scenarioList().length; listIndex++) {
      if (listIndex % self.listDisplayCount === 0 && Math.abs(listIndex - self.listStart()) < 5 * self.listDisplayCount) {
        list.push({'displayIndex': 1 + (listIndex/self.listDisplayCount), 'listIndex': listIndex });
      }
    }
    if (list.length < self.scenarioList().length / self.listDisplayCount) {
      list.push({'displayIndex': '...', 'listIndex': null });
      list.push({'displayIndex': '»', 'listIndex': null });

    }
    if (self.listStart() > self.listDisplayCount) {
      list.shift({'displayIndex': '&laquo;', 'listIndex': null });      
    }
    return list;
  });

  self.setListIndex = function (button, event) {
    var listStart = self.listStart();
    if (button.displayIndex === '»') {
        self.listStart(listStart + self.listDisplayCount * 5);
    } else {
        self.listStart(button.listIndex);
    }
    //self.selectFeature(self.scenarioList()[button.listIndex || self.listStart()]);
  };


  self.showScenarioForm = function(action, uid) {
    // get the form
    var formUrl;
    if (action === "create") {
      formUrl = app.workspace["feature-classes"][0]["link-relations"]["create"]["uri-template"]; 
    } else if (action === "edit") {
      formUrl = app.workspace["feature-classes"][0]["link-relations"]["edit"][0]["uri-template"]; 
      formUrl = formUrl.replace('{uid}', uid);
    }
    // clean up and show the form
    var jqxhr = $.get(formUrl, function(data) {
      $('#scenarios-form-container').empty().append(data);
      var $form = $('#scenarios-form-container').find('form#featureform');
      $form.find('input:submit').remove();
      self.showScenarioFormPanel(true);
      /*
      $form.find('input:visible:first').focus();
      $form.bind('submit', function(event) {
        event.preventDefault();
      });
      */
    })
    .success( function() {
        selectFeatureControl.unselectAll();
        selectGeographyControl.activate();
        pu_layer.styleMap.styles.default.defaultStyle.display = true;
        //pu_layer.redraw();
        self.showScenarioList(false);
        self.selectedFeature(false);
        self.showScenarioList(false);

        // If we're in EDIT mode, set the form values 
        if ($('#id_input_targets').val() && 
            $('#id_input_penalties').val() && 
            $('#id_input_relativecosts').val() && 
            $('#id_input_geography').val()) { 
                
            // Reset to zeros 
            $.each( $('.targetvalue'), function(k, target) { $(target).val(0); });
            $.each( $('.penaltyvalue'), function(k, penalty) { $(penalty).val(0); });
            $.each( $('.costvalue'), function(k, cost) { $(cost).removeAttr('checked'); });

            // Select and apply geography
            var in_geog = JSON.parse($('#id_input_geography').val());
            $.each(in_geog, function (i, fid) {
                var f = pu_layer.getFeaturesByAttribute("fid",fid)[0];
                if (!f) {
                    console.log("warning: fid " + fid + " is not valid");
                }
                selectGeographyControl.select(f);
            });
             
            // Apply Costs
            var in_costs = JSON.parse($('#id_input_relativecosts').val());
            $.each(in_costs, function(key, val) {
                if (val > 0) {
                    $("#cost---" + key).attr('checked','checked')
                } else {
                    $("#cost---" + key).removeAttr('checked')
                }
            });

            // Apply Targets and Penalties
            var in_targets = JSON.parse($('#id_input_targets').val());
            $.each(in_targets, function(key, val) {
                $("#target---" + key).val(val);
            });
            var in_penalties = JSON.parse($('#id_input_penalties').val());
            $.each(in_penalties, function(key, val) {
                $("#penalty---" + key).val(val);
            });
            
       }; // end EDIT mode
    })
    .error( function() { self.formLoadError(true); } )
    .complete( function() { self.formLoadComplete(true); } )
  };

  self.updateScenario = function(scenario_id, isNew) {
    var updateUrl = '/features/generic-links/links/geojson/{uid}/'.replace('{uid}', scenario_id);
    $.get(updateUrl, function(data) {
      if (isNew) {
        self.scenarioList.unshift(ko.mapping.fromJS(data.features[0].properties));
        self.selectedFeature(self.scenarioList()[0]);
      } else {
        ko.mapping.fromJS(data.features[0].properties, self.selectedFeature());
        self.showScenarioFormPanel(false);
        self.showScenarioList(true);
      }
    });
  };

  self.saveScenarioForm = function(self, event) {
        var targets = {};
        var penalties = {};
        var costs = {};
        var geography_fids = [];
        var totaltargets = 0;
        var totalpenalties = 0;
        var totalfids = 0;

        // Get geography constraints
        $.each(pu_layer.selectedFeatures, function(k, v) { 
            geography_fids.push(v.data.fid); 
            totalfids += 1;
        });
        // Get targets
        $("#form-cfs input.targetvalue").each( function(index) {
            var xid = $(this).attr("id");
            var id = "#" + xid;
            xid = xid.replace(/^target---/,''); //  Remove preceding identifier
            xid = xid.replace(/---$/,''); // Remove trailing ---
            targets[xid] = parseFloat($(id).val());
            totaltargets += parseFloat($(id).val());
        });
        // Get penalties 
        $("#form-cfs input.penaltyvalue").each( function(index) {
            var xid = $(this).attr("id");
            var id = "#" + xid;
            xid = xid.replace(/^penalty---/,''); 
            xid = xid.replace(/---$/,'');
            penalties[xid] = parseFloat($(id).val());
            totalpenalties += parseFloat($(id).val());
        });
        // Initialize costs to zero
        $('#form-costs input:checkbox.costvalue').each( function(index) {
            var xid = $(this).attr("id");
            xid = xid.replace(/^cost---/,'');
            costs[xid] = 0;
        });
        // Set the *checked* costs to 1
        $('#form-costs input:checkbox.costvalue:checked').each( function(index) {
            var xid = $(this).attr("id");
            xid = xid.replace(/^cost---/,'');
            costs[xid] = 1;
        });

        // Set the form values (note that .html() doesnt change)
        var frm = $('form#featureform');
        $(frm).find('textarea#id_input_targets').val( JSON.stringify(targets) ); 
        $(frm).find('textarea#id_input_penalties').val( JSON.stringify(penalties) );
        $(frm).find('textarea#id_input_relativecosts').val( JSON.stringify(costs) );
        $(frm).find('textarea#id_input_geography').val( JSON.stringify(geography_fids) );

        if (totalpenalties == 0 || totaltargets == 0 || totalfids == 0) {
            alert("must set targets, penalties and select geography");
        } else {
            // GO
            var values = {};
            var actionUrl = $(frm).attr('action');
            $(frm).find('input,select,textarea').each(function() {
                values[$(this).attr('name')] = $(this).val();
            });

            // Submit the form
            self.formLoadComplete(false);
            self.cancelAddScenario(); // Not acutally cancel, just clear 
            var scenario_uid; 
            var jqxhr = $.ajax({
                url: actionUrl,
                type: "POST",
                data: values
            })
            .success( function(data, textStatus, jqXHR) {
                var d = JSON.parse(data);
                if (d['status'] != 200) {
                    console.log("Unknown error", d);
                }
                scenario_uid = d["X-Madrona-Select"];
            })
            .error( function(jqXHR, textStatus, errorThrown) {
                console.log("ERROR", errorThrown, textStatus);
            })
            .complete( function() { 
                self.formLoadComplete(true);
                self.loadScenarios(); // TODO since this is async, the select below is too early (callback instead)
                if (scenario_uid) {
                    var selected = self.scenarioList()[0]; // TODO loop and select by uid
                    self.selectFeature(selected);
                };
            });
        };
  };


  self.showDeleteDialog = function () {
    $("#scenario-delete-dialog").modal("show");
  };

  self.closeDialog = function () {
    $("#scenario-delete-dialog").modal("hide");
  };

  self.deleteFeature = function () {
    var url = "/features/generic-links/links/delete/{uid}/".replace("{uid}", self.selectedFeature().uid());
    $('#scenario-delete-dialog').modal('hide');
    $.ajax({
      url: url,
      type: "DELETE",
      success: function (data, textStatus, jqXHR) {
        self.scenarioList.remove(self.selectedFeature());
        self.selectedFeature(false);
        self.showScenarioList(true);
        self.selectControl.unselectAll();
      }  
    });
  };

  // start the scenario editing process
  self.editScenario = function() {
    self.formLoadError(false);
    self.formLoadComplete(false);
    self.showScenarioForm("edit", self.selectedFeature().uid());
  };

  self.addScenarioStart = function() {
    self.formLoadError(false);
    self.formLoadComplete(false);
    self.showScenarioForm('create');
  };


  self.cancelAddScenario = function () {
    selectGeographyControl.unselectAll();
    selectGeographyControl.deactivate();
    pu_layer.styleMap.styles.default.defaultStyle.display = "none";
    pu_layer.redraw();
    self.showScenarioFormPanel(false);
    self.showScenarioList(true);
  };

  self.selectControl = {
      /*
       * Controls the map and display panel 
       * when features are selected
       */
      unselectAll: function() { 
        // $('#scenario-show-container').empty();
      },
      select: function(feature) {

        var uid = feature.uid(); 
        var showUrl = app.workspace["feature-classes"][0]["link-relations"]["self"]["uri-template"]; 
        showUrl = showUrl.replace('{uid}', uid);

        self.reportLoadError(false);
        self.reportLoadComplete(false);
        var jqxhr = $.get(showUrl, function(data) {
          var elem = document.getElementById('scenario-show-container');
          ko.cleanNode(elem);
          $('#scenario-show-container').empty().append(data);
          app.scenarios.progressViewModel = null;
          clearInterval(app.timer);
          app.timer = null;
          app.scenarios.progressViewModel = new progressViewModel();

          ko.applyBindings(app.scenarios.progressViewModel, elem);
          app.scenarios.progressViewModel.checkTimer();
        })
        .error(function() { self.reportLoadError(true); })
        .complete(function() { self.reportLoadComplete(true); })
        
        selectFeatureControl.unselectAll();
        $.each(feature.selected_fids(), function (i, fid) {
            var f = pu_layer.getFeaturesByAttribute("fid",fid)[0];
            if (!f) {
                console.log("warning: fid " + fid + " is not valid");
            }
            selectFeatureControl.select(f);
        });
      }
   };

  self.selectFeature = function(feature, event) {
    self.selectControl.unselectAll();
    self.selectControl.select(feature);
    self.selectedFeature(feature); 
    bbox = feature.bbox();
    if (bbox && bbox.length === 4) {
        map.zoomToExtent(bbox);
    }
    self.showScenarioList(false);
  };

  self.selectFeatureById = function (id) {
    var pageSize = self.scenarioList().length / self.listDisplayCount;
    $.each(self.scenarioList(), function (i, feature) {
      if (feature.uid() === id) {
        // set list start to first in list page      
        self.listStart(Math.floor(i / self.listDisplayCount) * self.listDisplayCount);
        self.selectedFeature(this);
      }
    });
  };

  self.reloadScenarios = function(property) {
    console.log("reloadScenarios");
    self.scenarioList.removeAll();
    self.loadScenarios();
  };

  self.loadViewModel = function (data) {
    self.scenarioList($.map(data.features, function (feature, i) {
      return ko.mapping.fromJS(feature.properties);
    }));
    // Don't bother selecting the first feature
    //self.selectFeature(self.scenarioList()[0]);
  };

  self.loadScenarios = function() {
    var process = function(data) {
      if (data.features && data.features.length) {
        self.loadViewModel(data);
      } 
    };
    var jqhxr = $.get('/seak/scenarios.geojson', 
        process
    )
    .error(function() { self.scenarioLoadError(true); })
    .complete(function() { self.scenarioLoadComplete(true); })

  };

  self.backToScenarioList = function() {
    selectFeatureControl.unselectAll();
    self.selectedFeature(false);
    self.showScenarioList(true);
  };

  return self;
}
