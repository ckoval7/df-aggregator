<!DOCTYPE html>
<html lang="en">
<head>
  <meta name="viewport" content="width=device-width, height=device-height">
  <meta charset="utf-8">
  <!-- Include the CesiumJS JavaScript and CSS files -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
  <link href="/static/style.css" rel="stylesheet">
  <link href="/static/menu.css" rel="stylesheet">
</head>
<body onload="showReceivers()">
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
      xmlHttp.onload = function() {
        clearOld();
        loadCzml();
      }
    }

    function updateRx() {
      return new Promise(function(myResolve, myReject) {
        let request = new XMLHttpRequest();
        request.open( "GET", "/rx_params", true );
        // request.responseType = 'json';
        request.onload = function() {
          if (request.status == 200) {myResolve(request.response);}
          else {myResolve("File not Found");}
        };
        request.send( null );
      });
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

    <input id="burgerbars" type="checkbox" />

    <span class="borger"></span>
    <span class="borger"></span>
    <span class="borger"></span>

    <ul id="menu">
      <h2 style="color: #eee; padding-left: 5px;">Receivers</h2>
        <script>
          var rx_json;
          updateRx().then(JSON.parse).then(function(response) {
            rx_json = response;
          });
          function showReceivers() {
            const receivers = rx_json['receivers'];
            for (let i = 0; i < Object.keys(receivers).length; i++) {
              var stationUrlHtml = document.createElement('input');
              stationUrlHtml.type = 'hidden';
              stationUrlHtml.id = "url_" + receivers[i].uid
              var edit_stationUrlHtml =
              "Station URL:<input style=\"width: 300px;\" type=\"text\" value=\"\" name=\"station_url_" + receivers[i].uid + "\" />";

              mobileToggle = document.createElement('input');
              mobileToggle.type = 'hidden';
              mobileToggle.id = "mobilerx_toggle_" + receivers[i].uid

              var stationIDhtml = document.createElement('p');
              stationIDhtml.innerHTML = "Station ID:&nbsp";
              var stationIDhtmlLink = document.createElement('a');
              stationIDhtmlLink.href = receivers[i].station_url;
              stationIDhtmlLink.target = '_blank';
              stationIDhtmlLink.innerHTML = receivers[i].station_id;
              var edit_stationIDhtml =
              "Station ID:<input style=\"width: 105px;\" type=\"text\" value=\"\" name=\"station_id_" + receivers[i].uid + "\" />";

              var manualInfo = document.createElement('input');
              manualInfo.type = 'hidden';
              manualInfo.id = "manual_toggle_" + receivers[i].uid
              var edit_manualInfo =
              "Manually input receiver info: <input id=\"manual_toggle_" + receivers[i].uid + "\" type=\"checkbox\" />";

              var locationHtml = document.createElement('p');
              locationHtml.innerHTML = "Location: " + receivers[i].latitude + "&#176;, " + receivers[i].longitude + "&#176;";
              var edit_locationHtml =
              "Latitude:<input style=\"width: 105px;\" type=\"text\" value=\"receivers[i].latitude\" name=\"station_lat_" + receivers[i].uid + "\" />"
              + " Longitude:<input style=\"width: 105px;\" type=\"text\" value=\"receivers[i].longitude\" name=\"station_lon_" + receivers[i].uid + "\" />";

              var heading = document.createElement('p');
              heading.innerHTML = "Heading: " + receivers[i].heading + "&#176;";
              var edit_heading =
              "Heading:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[i].heading + "\" name=\"station_heading_" + receivers[i].uid + "\" />";

              var freqHtml = document.createElement('p');
              freqHtml.innerHTML = "Tuned to " + receivers[i].frequency + "MHz";
              var edit_freqHtml =
              "Frequency:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[i].frequency + "\" name=\"frequency_" + receivers[i].uid + "\" />";

              const rxcard = document.createElement('div');
              rxcard.className = "receiver";

              const urlspan = document.createElement('span');
              const mobilespan = document.createElement('span');
              const manualspan = document.createElement('span');
              const idspan = document.createElement('span');
              const locationspan =document.createElement('span');
              const headingspan = document.createElement('span');
              const freqspan = document.createElement('span');
              const editiconspan = document.createElement('span');
              editiconspan.classList.add("material-icons", "edit-icon", "no-select");
              editiconspan.innerHTML = "create";

              const editcheck = document.createElement('input');
              editcheck.classList.add("edit-checkbox", "edit-icon");
              editcheck.type = 'checkbox';

              urlspan.id = receivers[i].uid + "-url";
              mobilespan.id = receivers[i].uid + "-mobile";
              manualspan.id = receivers[i].uid + "-manual";
              idspan.id = receivers[i].uid + "-id";
              locationspan.id = receivers[i].uid + "-location";
              headingspan.id = receivers[i].uid + "-heading";
              freqspan.id = receivers[i].uid + "-freq";
              editiconspan.id = receivers[i].uid + "-editicon";

              document.getElementById("menu").appendChild(rxcard);

              rxcard.appendChild(urlspan);
              rxcard.appendChild(mobilespan);
              rxcard.appendChild(manualspan);
              rxcard.appendChild(idspan);
              rxcard.appendChild(locationspan);
              rxcard.appendChild(headingspan);
              rxcard.appendChild(freqspan);
              rxcard.appendChild(editiconspan);
              rxcard.appendChild(editcheck);

              urlspan.appendChild(stationUrlHtml);
              mobilespan.appendChild(mobileToggle);
              manualspan.appendChild(manualInfo);
              idspan.appendChild(stationIDhtml);
              idspan.appendChild(stationIDhtmlLink);
              locationspan.appendChild(locationHtml);
              headingspan.appendChild(heading);
              freqspan.appendChild(freqHtml);

            }
          }

        </script>
      <input id="add_station" class="edit-checkbox add-icon" type="checkbox" style="width: 23px; height: 23px;"/>
      <span id="add_station_icon" class="material-icons add-icon no-select">add_circle_outline</span>
      <div id="new_rx_div" style="padding: 0;" class="receiver">
        <span id="new-url"><input type="hidden" id="url_new"/></span>
      </div>
      <script>
      var stationUrlHtml_new =
      "<input type=\"hidden\" id=\"url_new\"/>";
      var edit_stationUrlHtml_new =
      "Station URL:<input style=\"width: 300px;\" type=\"text\" name=\"station_url_new\" />";
      var add_button = document.getElementById("add_station");
      add_button.onchange = function() {
        if (add_button.checked) {
          document.getElementById("new-url").innerHTML = edit_stationUrlHtml_new;
          document.getElementById("add_station_icon").innerHTML = "save";
          document.getElementById("new_rx_div").style.padding = "5px";
        } else {
          document.getElementById("new-url").innerHTML = stationUrlHtml_new;
          document.getElementById("add_station_icon").innerHTML = "add_circle_outline";
          document.getElementById("new_rx_div").style.padding = "0";
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
