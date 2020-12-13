<!DOCTYPE html>
<html lang="en">
<head>
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <meta name="viewport" content="width=device-width, height=device-height">
  <meta charset="utf-8">
  <!-- Include the CesiumJS JavaScript and CSS files -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.76/Build/Cesium/Cesium.js"></script>
  <script src="/static/receiver_configurator.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.76/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
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
    var cartesian;
    var cartographic
    // var center_cartesian;
    var rad_cartesian;
    var center_lat;
    var center_lon;
    var radius;

    // Pick the center point of a circle
    function pickCenter(lat_element_id, radius_element_id, outlineColor) {
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
      handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
      // Mouse over the globe to see the cartographic position
      handler.setInputAction(function (movement) {
        cartesian = viewer.camera.pickEllipsoid(
          movement.endPosition,
          scene.globe.ellipsoid
        );
        cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        if (cartesian) {
          var center_lon = Cesium.Math.toDegrees(
            cartographic.longitude
          ).toFixed(5);
          var center_lat = Cesium.Math.toDegrees(
            cartographic.latitude
          ).toFixed(5);

          lat_element_id.value = center_lat + ", " + center_lon;
          // lon_element_id.value = center_lon;
          entity.position = cartesian;
          entity.label.show = true;
          entity.label.text =
            "Lon: " +
            ("   " + center_lon).slice(-10) +
            "\nLat: " +
            ("   " + center_lat).slice(-10);
        } else {
          entity.label.show = false;
        }
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

      handler.setInputAction(function () {
        clearHover();
        pickRadius(radius_element_id, cartographic, outlineColor);
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    }

    //Stop pickng things
    function clearHover() {
      viewer.entities.removeAll();
      handler = handler && handler.destroy();
    };

    //Pick the outside edge, radius, of a circle.
    function pickRadius(radius_element_id, center_carto, outlineColor) {
      var area;
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
      handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
      handler.setInputAction(function (movement) {
        rad_cartesian = viewer.camera.pickEllipsoid(
          movement.endPosition,
          scene.globe.ellipsoid
        );
        var center_lon = Cesium.Math.toDegrees(
          center_carto.longitude
        ).toFixed(5);
        var center_lat = Cesium.Math.toDegrees(
          center_carto.latitude
        ).toFixed(5);
        cartographic = Cesium.Cartographic.fromCartesian(rad_cartesian);
        if (rad_cartesian) {
          var ellipsoidGeodesic = new Cesium.EllipsoidGeodesic(center_carto, cartographic);
          var distance = ellipsoidGeodesic.surfaceDistance.toFixed(0);

          radius_element_id.value = distance;
          entity.position = rad_cartesian;
          entity.label.show = true;
          entity.label.text = distance + " m";
          circleGeometry = new Cesium.CircleOutlineGeometry({
            center: Cesium.Cartesian3.fromDegrees(center_lon, center_lat),
            radius: distance,
            height: 0,
            // vertexFormat: Cesium.PerInstanceColorAppearance.VERTEX_FORMAT,
          });
          // Create a geometry instance using the circle geometry
          // created above. Set the color attribute to a solid blue.
          var areaSelectorInstance = new Cesium.GeometryInstance({
            geometry: circleGeometry,
            attributes: {
              color: Cesium.ColorGeometryInstanceAttribute.fromColor(
                outlineColor
              ),
            },
          });
          // Add the geometry instance to primitives.
          scene.primitives.remove(area);
          area = scene.primitives.add(
            new Cesium.Primitive({
              geometryInstances: areaSelectorInstance,
              appearance: new Cesium.PerInstanceColorAppearance({
                flat: true,
                closed: true,
                translucent: false,
                renderState: {
                  lineWidth: Math.min(3.0, scene.maximumAliasedLineWidth),
                },
              }),
            })
          );
        } else {
          entity.label.show = false;
        }
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

      handler.setInputAction(function () {
        clearHover();

      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    }

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
          <span id="new-aoi"></span>
        </div>
      </div>
      <hr>
      <div id="exclusioncards" class="menusections">
        <h2 style="color: #eee; padding-left: 5px;">Exclusion Areas</h2>
        <p> This does nothing right now. </p>
        <input id="add_exclusion" class="edit-checkbox add-icon" type="checkbox" style="width: 23px; height: 23px;"/>
        <span id="add_exclusion_icon" class="material-icons add-icon no-select">add_circle_outline</span>
        <div style="visibility: hidden; height: 0;" id="new_exclusion_div" style="padding: 0;">
          <span id="new-exclusion"></span>
        </div>
      </div>
    </ul>
  </div>
  <script src="/static/cardsmenu.js"></script>

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
