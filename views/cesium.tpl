<!DOCTYPE html>
<html lang="en">
<head>
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <meta name="viewport" content="width=device-width, height=device-height">
  <meta charset="utf-8">
  <!-- Include the CesiumJS JavaScript and CSS files -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Cesium.js"></script>
  <script src="/static/receiver_configurator.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
  <link href="/static/style.css" rel="stylesheet">
  <link href="/static/menu.css" rel="stylesheet">
</head>
<body onload="loadRx(createReceivers)">
  <div id="cesiumContainer">

  </div>
  <script>
    // Your access token can be found at: https://cesium.com/ion/tokens.
    Cesium.Ion.defaultAccessToken = '{{access_token}}';
    // var hpr = new Cesium.HeadingPitchRange(0, 40, 0)
    var viewer = new Cesium.Viewer('cesiumContainer', {
      // terrainProvider: Cesium.createWorldTerrain(),
      homeButton: false,
      timeline: false,
      selectionIndicator: false,
      infoBox: false,
    });
    var clock = new Cesium.Clock({
       clockStep : Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER
    });

    viewer.clock.shouldAnimate = true;
    viewer.zoomTo(loadAllCzml());

    var scene = viewer.scene;
    if (!scene.pickPositionSupported) {
      window.alert("This browser does not support pickPosition.");
    }

    var handler;

    function hovercoords() {
      var entity = viewer.entities.add({
        label: {
          show: false,
          showBackground: true,
          font: "14px monospace",
          horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(15, 0),
        },
      });

      // Mouse over the globe to see the cartographic position
      handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
      handler.setInputAction(function (movement) {
        var cartesian = viewer.camera.pickEllipsoid(
          movement.endPosition,
          scene.globe.ellipsoid
        );
        if (cartesian) {
          var cartographic = Cesium.Cartographic.fromCartesian(cartesian);
          var longitudeString = Cesium.Math.toDegrees(
            cartographic.longitude
          ).toFixed(5);
          var latitudeString = Cesium.Math.toDegrees(
            cartographic.latitude
          ).toFixed(5);

          entity.position = cartesian;
          entity.label.show = true;
          entity.label.text =
            "Lon: " +
            ("   " + longitudeString).slice(-10) +
            "\nLat: " +
            ("   " + latitudeString).slice(-10);
        } else {
          entity.label.show = false;
        }
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
    }

    function clearHover() {
      viewer.entities.removeAll();
      handler = handler && handler.destroy();
    };

    function updateParams(parameter) {
        fetch("/update?"+parameter)
            .then(function(response) {
              if (response.status == 200) {
                loadRx(refreshRx);
                clearOld();
                loadAllCzml();
                // console.log(response);
              }
            })
    }

    function loadTxCzml() {
      var transmittersDataSource = Cesium.CzmlDataSource.load('/output.czml');
      viewer.dataSources.add(transmittersDataSource);
      // console.log("Loaded CZML");
      return transmittersDataSource;
    }

    function loadRxCzml() {
      var receiversDataSource = Cesium.CzmlDataSource.load('/receivers.czml');
      viewer.dataSources.add(receiversDataSource);
      // console.log("Loaded CZML");
      return receiversDataSource;
    }

    function loadAllCzml() {
      loadTxCzml();
      let zoom = loadRxCzml();
      return zoom;
    }

    function clearOld() {
      viewer.dataSources.removeAll(true);
      // console.log("Cleared old");
    }

    // Add Cesium OSM Buildings, a global 3D buildings layer.
    // const buildingTileset = viewer.scene.primitives.add(Cesium.createOsmBuildings());

  </script>
  <div id="menuToggle">

    <input id="burgerbars" type="checkbox" />

    <span class="borger"></span>
    <span class="borger"></span>
    <span class="borger"></span>

    <ul id="menu">
      <div id="rxcards" class="menusections">
        <h2 style="color: #eee; padding-left: 5px;">Receivers</h2>

        <input id="add_station" class="edit-checkbox add-icon" type="checkbox" style="width: 23px; height: 23px;"/>
        <span id="add_station_icon" class="material-icons add-icon no-select">add_circle_outline</span>
        <div style="visibility: hidden; height: 0;" id="new_rx_div" style="padding: 0;">
          <span id="new-url">Station URL:</span>
        </div>
      </div>
      <hr>
      <div id="aoicards" class="menusections">
        <h2 style="color: #eee; padding-left: 5px;">Areas of Interest</h2>
        <p> This does nothing right now. </p>
        <input id="add_aoi" class="edit-checkbox add-icon" type="checkbox" style="width: 23px; height: 23px;"/>
        <span id="add_aoi_icon" class="material-icons add-icon no-select">add_circle_outline</span>
        <div style="visibility: hidden; height: 0;" id="new_aoi_div" style="padding: 0;">
          <span id="new-aoi">Lat/Lon/Radius:</span>
        </div>
      </div>
      <hr>
      <div id="exclusioncards" class="menusections">
        <h2 style="color: #eee; padding-left: 5px;">Exclusion Areas</h2>
        <p> This does nothing right now. </p>
        <input id="add_exclusion" class="edit-checkbox add-icon" type="checkbox" style="width: 23px; height: 23px;"/>
        <span id="add_exclusion_icon" class="material-icons add-icon no-select">add_circle_outline</span>
        <div style="visibility: hidden; height: 0;" id="new_exclusion_div" style="padding: 0;">
          <span id="new-exclusion">Lat/Lon/Radius:</span>
        </div>
      </div>
      <script>

      var stationUrlHtml_new = document.createElement('input');
      stationUrlHtml_new.type = 'text';
      stationUrlHtml_new.id = 'url-new';
      stationUrlHtml_new.style.width = '300px';
      document.getElementById("new-url").appendChild(stationUrlHtml_new);
      var add_button = document.getElementById("add_station"); //Button to add new RX
      add_button.onchange = function() {
        if (add_button.checked) {
          stationUrlHtml_new.value = "";
          document.getElementById("new_rx_div").style.height = 'auto';
          document.getElementById("new_rx_div").style.visibility = "visible";
          document.getElementById("add_station_icon").innerHTML = "save";
          document.getElementById("new_rx_div").style.padding = "5px";
        } else {
          var newrxurl = stationUrlHtml_new.value
          if (newrxurl != "") {
            makeNewRx(newrxurl);
          }
          document.getElementById("new_rx_div").style.height = 0;
          document.getElementById("new_rx_div").style.visibility = "hidden";
          document.getElementById("add_station_icon").innerHTML = "add_circle_outline";
          document.getElementById("new_rx_div").style.padding = "0";
        }
      }

      var add_aoi = document.getElementById("add_aoi"); //Button to add new RX
      add_aoi.onchange = function() {
        if (add_aoi.checked) {
          document.getElementById("add_aoi_icon").innerHTML = "save";
          hovercoords();
        } else {
          document.getElementById("add_aoi_icon").innerHTML = "add_circle_outline";
          clearHover();
        }
      }

      var add_exclusion = document.getElementById("add_exclusion"); //Button to add new RX
      add_exclusion.onchange = function() {
        if (add_exclusion.checked) {
          document.getElementById("add_exclusion_icon").innerHTML = "save";
          hovercoords();
        } else {
          document.getElementById("add_exclusion_icon").innerHTML = "add_circle_outline";
          clearHover();
        }
      }
      </script>
    </ul>
  </div>

  <div class="slidecontainer">
    <div class="tooltip">
      <span>
      <span class="slidetitle"><h4>Enable Receiver:</h4></span>
      <span class="slidespan" style="text-align:left;width: 100px;margin: 5px;">
      <label class="switch">
      <input id="rx_en" name="rx_en" {{rx_state}} type="checkbox">
      <span class="switchslider round"></span>
      </label></span>
      </span>
      <span class="tooltiptext">Enables or disables capturing intersections.</span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Minimum Power: <br>
        Minimun power level to record an intersection.Does not affect historical data.</span>
      <span class="slidespan">
        <input name="powerValue" type="range" min="0" max="50" value="{{minpower}}" class="slider" id="powerRange">
      </span>
      <span class="slidevalue" id="power"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Minimum Confidence:<br>
        Minimum confidence level to record an intersection. Does not affect historical data.</span>
      <span class="slidespan">
        <input name="confValue" type="range" min="0" max="100" value="{{minconf}}" class="slider" id="confRange">
      </span>
      <span class="slidevalue" id="confidence"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Epsilon:<br>
        Maximum distance between neighboring points in a cluster. Set to 0 to disable clustering.<br>
        Disabling clustering will plot all intersections and may cause longer load times.</span>
      <span class="slidespan">
        <input name="epsilonValue" type="range" min="0" max="1" step="0.01" value="{{epsilon}}" class="slider" id="epsilonRange">
      </span>
      <span class="slidevalue" id="epsilon"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Minimum points per cluster</span>
      <span class="slidespan">
        <input name="minpointValue" type="range" min="0" max="300" step="5" value="{{minpoints}}" class="slider" id="minpointRange">
      </span>
      <span class="slidevalue" id="minpoints"></span>
    </div>
    <div style="width: 600px">
      <span class="tooltip">
        <span class="slidetitle"><h4>Plot All Intersect Points:</h4></span>
        <span class="slidespan" style="text-align:left; width: 100px;margin: 5px;">
        <label class="switch">
          <input id="intersect_en" name="intersect_en" {{intersect_state}} type="checkbox">
          <span class="switchslider round"></span>
        </label></span>
        <span class="tooltiptext">This setting does not apply if clustering is turned off (epsilon = 0).<br>
          Enabling this can cause longer load times.</span>
      </span>
    </div>
    <div>
      <span><input id="refreshbutton" class="slider" type="button" value="Refresh" onclick="updateParams()"></span>
    </div>
  </div>
  <script>
    var powerslider = document.getElementById("powerRange");
    var poweroutput = document.getElementById("power");
    poweroutput.innerHTML = powerslider.value;

    var confslider = document.getElementById("confRange");
    var confoutput = document.getElementById("confidence");
    confoutput.innerHTML = confslider.value;

    var epsslider = document.getElementById("epsilonRange");
    var epsoutput = document.getElementById("epsilon");
    epsoutput.innerHTML = epsslider.value;

    var minpointslider = document.getElementById("minpointRange");
    var minpointoutput = document.getElementById("minpoints");
    minpointoutput.innerHTML = minpointslider.value;

    var rx_enable = document.getElementById("rx_en");

    var intersect_en = document.getElementById("intersect_en");

    // Update the current slider value (each time you drag the slider handle)
    epsslider.oninput = function() {
      epsoutput.innerHTML = this.value;
    }
    epsslider.onmouseup = function() {
      updateParams("eps="+this.value);
    }
    powerslider.oninput = function() {
      poweroutput.innerHTML = this.value;
    }
    powerslider.onmouseup = function() {
      updateParams("minpower="+this.value);
    }
    confslider.oninput = function() {
      confoutput.innerHTML = this.value;
    }
    confslider.onmouseup = function() {
      updateParams("minconf="+this.value);
    }
    minpointslider.oninput = function() {
      minpointoutput.innerHTML = this.value;
    }
    minpointslider.onmouseup = function() {
      updateParams("minpts="+this.value);
    }

    rx_enable.onchange = function() {
      if (rx_enable.checked) {
        updateParams("rx=true");
      } else {
        updateParams("rx=false");
      }
    }

    intersect_en.onchange = function() {
      if (intersect_en.checked) {
        updateParams("plotpts=true");
      } else {
        updateParams("plotpts=false");
      }
    }

  </script>
</body>
</html>
