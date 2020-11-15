<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <!-- Include the CesiumJS JavaScript and CSS files -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <link href="/static/style.css" rel="stylesheet">
  <link href="/static/menu.css" rel="stylesheet">
</head>
<body>
  <div id="cesiumContainer">

  </div>
  <script>
    // Your access token can be found at: https://cesium.com/ion/tokens.
    Cesium.Ion.defaultAccessToken = '{{access_token}}';
    var viewer = new Cesium.Viewer('cesiumContainer', {
      terrainProvider: Cesium.createWorldTerrain(),
      homeButton: false,
      timeline: false
    });
    var clock = new Cesium.Clock({
       clockStep : Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER
    });

    viewer.clock.shouldAnimate = true;
    viewer.zoomTo(loadCzml());

    function updateParams(parameter) {
      var xmlHttp = new XMLHttpRequest();
      xmlHttp.open( "GET", "/update?"+parameter, true ); // false for synchronous request
      xmlHttp.send( null );
      xmlHttp.onreadystatechange = function() {
        if (this.readyState == 3) {
          clearOld();
          // loadCzml();
        } else if (this.readyState == 4 && this.status == 200) {
          // clearOld();
          loadCzml();
        };
      }
    }

    function loadCzml() {
      var dataSourcePromise = Cesium.CzmlDataSource.load('/static/output.czml');
      viewer.dataSources.add(dataSourcePromise);
      return dataSourcePromise;
    }

    function clearOld() {
      viewer.dataSources.removeAll(true);
    }

    // Add Cesium OSM Buildings, a global 3D buildings layer.
    // const buildingTileset = viewer.scene.primitives.add(Cesium.createOsmBuildings());

  </script>
  <div id="menuToggle">

    <input type="checkbox" />

    <span class="borger"></span>
    <span class="borger"></span>
    <span class="borger"></span>

    <ul id="menu">
      <h2 style="color: #eee;">Receivers</h2>
      % for x in receivers:
      <div class="receiver">
        <span>Station ID: <a href="{{x.station_url}}" target="_blank">{{x.station_id}}</a></span>
        <span>Location: {{x.latitude}}, {{x.longitude}}</span>
        <span>Heading: {{x.heading}}&#176;</span>
        <span>Tuned to {{x.frequency}} MHz</span>
      </div>
      % end
    </ul>
  </div>
  <!-- <span>Location:</span>
  <span>Mobile Receiver:
  <label class="switch">
  <input id="isMobile" name="isMobile" type="checkbox">
  <span class="switchslider round"></span>
</label></span>
</span> -->

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
      <span class="slidespan"><input name="powerValue" type="range" min="0" max="50" value="{{minpower}}" class="slider" id="powerRange"></span>
      <span class="slidevalue" id="power"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Minimum Confidence:<br>
        Minimum confidence level to record an intersection. Does not affect historical data.</span>
      <span class="slidespan"><input name="confValue" type="range" min="0" max="100" value="{{minconf}}" class="slider" id="confRange"></span>
      <span class="slidevalue" id="confidence"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Epsilon:<br>
        Maximum distance between neighboring points in a cluster. Set to 0 to disable clustering.<br>
        Disabling clustering will plot all intersections and may cause longer load times.</span>
      <span class="slidespan"><input name="epsilonValue" type="range" min="0" max="1" step="0.01" value="{{epsilon}}" class="slider" id="epsilonRange"></span>
      <span class="slidevalue" id="epsilon"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Minimum points per cluster</span>
      <span class="slidespan"><input name="minpointValue" type="range" min="0" max="300" step="5" value="{{minpoints}}" class="slider" id="minpointRange"></span>
      <span class="slidevalue" id="minpoints"></span>
    </div>
    <div style="width: 300px">
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
      updateParams("eps="+this.value);
    }
    powerslider.oninput = function() {
      poweroutput.innerHTML = this.value;
      updateParams("minpower="+this.value);
    }
    confslider.oninput = function() {
      confoutput.innerHTML = this.value;
      updateParams("minconf="+this.value);
    }
    minpointslider.oninput = function() {
      minpointoutput.innerHTML = this.value;
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
