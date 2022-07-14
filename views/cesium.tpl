<!DOCTYPE html>

<!-- df-aggregator, networked radio direction finding software. =
    Copyright (C) 2020 Corey Koval

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>. -->

<html lang="en">
<head>
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <meta name="viewport" content="width=device-width, height=device-height">
  <meta charset="utf-8">
  <!-- Include the CesiumJS JavaScript and CSS files -->
  <!-- <script src="https://cesium.com/downloads/cesiumjs/releases/1.90/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.90/Build/Cesium/Widgets/widgets.css" rel="stylesheet"> -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/cesium/1.95.0/Cesium.js"
    integrity="sha512-Y95sidA9cDT2a8MMmD47EyCVxQRJYNhXEnvBgbsp+q0gK2k3VSMpMvs9DTct0dEjm+6Dru+d2wYllhgceEiFgw=="
    crossorigin="anonymous" referrerpolicy="no-referrer"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/cesium/1.95.0/Widgets/widgets.min.css"
    integrity="sha512-dWztHlhNizO37Lu3hJ+wCd8/T/VTqD8PHp4ZHRpHuGvEJJ59vTD0LPXekgZiaghVYDyZvXAqTAVhuctgyyukgw=="
    crossorigin="anonymous" referrerpolicy="no-referrer" />
  <script src="/static/receiver_configurator.js"></script>
  <script src="/static/interest_areas.js"></script>
  <!-- <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet"> -->
  <link href="/static/style.css" rel="stylesheet">
  <link href="/static/menu.css" rel="stylesheet">
</head>
<body onload="loadRx(createReceivers); loadAoi(createAois);">
  <div id="loader" class="loader"></div>
  <div id="cesiumContainer">

  </div>
  <script>
    var transmittersDataSource = new Cesium.CzmlDataSource();
    var receiversDataSource = new Cesium.CzmlDataSource();
    var aoiDataSource = new Cesium.CzmlDataSource();

    % if access_token:
    // Your access token can be found at: https://cesium.com/ion/tokens.
    Cesium.Ion.defaultAccessToken = '{{access_token}}';
    % end

    // Set default map to ESRI
    const esri = new Cesium.ArcGisMapServerImageryProvider({
      url : 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer'
    });

    var viewer = new Cesium.Viewer('cesiumContainer', {
      imageryProvider: esri,
      // imageryProvider : new Cesium.TileMapServiceImageryProvider({
      //   url : Cesium.buildModuleUrl('Assets/Textures/NaturalEarthII')
      // }),
      sceneModePicker: true,
      homeButton: false,
      timeline: false,
      mapProjection : new Cesium.WebMercatorProjection(),
    });

    viewer.infoBox.frame.setAttribute("sandbox", "allow-same-origin allow-popups allow-popups-to-escape-sandbox");
    viewer.infoBox.frame.src = "about:blank";

    var clock = new Cesium.Clock({
       clockStep : Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER
    });
    viewer.clock.shouldAnimate = true;

    var hpr = new Cesium.HeadingPitchRange(0.0, -1.57, 0.0);
    // viewer.zoomTo(loadAllCzml(), hpr);
    viewer.flyTo(loadAllCzml(), {'offset':hpr});

    var scene = viewer.scene;
    if (!scene.pickPositionSupported) {
      window.alert("This browser does not support pickPosition.");
    }

    var handler;
    var cartesian;
    var cartographic
    var rad_cartesian;
    var center_lat;
    var center_lon;
    var radius;

    // ***********************************************
    // Disable/enable object selection as needed.
    //************************************************
    var noSelect = false;
    var defaultClickHandler = viewer.screenSpaceEventHandler.getInputAction(Cesium.ScreenSpaceEventType.LEFT_CLICK);
    var myClickFunction = function(event) {
      if (!noSelect) {
        defaultClickHandler(event);
      } else {
        viewer.selectedEntity = undefined;
        viewer.trackedEntity = undefined;
      }
    };
    viewer.screenSpaceEventHandler.setInputAction(myClickFunction, Cesium.ScreenSpaceEventType.LEFT_CLICK);


    // Pick the center point of a circle
    function pickCenter(lat_element_id, lon_element_id, radius_element_id, outlineColor) {
      noSelect = true;
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

          lat_element_id.value = center_lat;
          lon_element_id.value = center_lon;
          entity.position = cartesian;
          entity.label.show = true;
          entity.label.text =
            "Lat: " +
            ("   " + center_lat).slice(-10) +
            "\nLon: " +
            ("   " + center_lon).slice(-10);
        } else {
          entity.label.show = false;
        }
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

      handler.setInputAction(function () {
        clearHover();
        pickRadius(radius_element_id, cartographic, outlineColor);
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    }

    var area;
    //Stop pickng things
    function clearHover() {
      noSelect = false;
      viewer.entities.removeAll();
      handler = handler && handler.destroy();
    };

    //Pick the outside edge, radius, of a circle.
    function pickRadius(radius_element_id, center_carto, outlineColor) {
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
        clearOld();
        fetch("/update?"+parameter)
            .then(function(response) {
                loadRx(refreshRx);
                loadAllCzml();
            })
    }

    function loadTxCzml() {
      let parameter = "";

      let spinner = document.getElementById("loader");
      spinner.style.visibility = "visible";
      spinner.style.zIndex = "10";

      const epsslider = document.getElementById("epsilonRange");
      const minpointslider = document.getElementById("minpointRange");
      const intersect_en = document.getElementById("intersect_en");
      const clustering_en = document.getElementById("clustering_en");

      if(minpointslider !== null) {
        if (minpointslider.value > 0) {
          parameter += "minpts="+minpointslider.value+"&";
        } else {
          parameter += "minpts=auto&";
        }
      }
      if (clustering_en !== null) {
        if (clustering_en.checked) {
          if (epsslider.value == 0) {
            parameter += "eps=auto&";
          } else {
            parameter += "eps="+epsslider.value+"&";
          }
        } else {
          parameter += "eps=0&";
        }
      }
      // if(epsslider !== null) {
      //   parameter += "eps="+epsslider.value+"&";
      // }
      if (intersect_en !== null) {
        if (intersect_en.checked) {
          parameter += "plotpts=true"+"&";
        } else {
          parameter += "plotpts=false"+"&";
        }
      }
      console.log(parameter);
      let promise1 = transmittersDataSource.load('/output.czml?'+parameter);
      promise1.then(
        function(dataSource1) {
          spinner.style.visibility = "hidden";
          spinner.style.zIndex = "0";
      });
      viewer.dataSources.add(transmittersDataSource);
      return transmittersDataSource;
    }

    function loadRxCzml() {
      receiversDataSource.load('/receivers.czml');
      viewer.dataSources.add(receiversDataSource);
      return receiversDataSource;
    }

    function loadAoiCzml() {
      aoiDataSource.load('/aoi.czml');
      viewer.dataSources.add(aoiDataSource);
      return aoiDataSource;
    }

    function loadAllCzml() {
      loadAoiCzml();
      loadRxCzml();
      return loadTxCzml();
    }

    function clearOld() {
      viewer.dataSources.remove(receiversDataSource, true);
      viewer.dataSources.remove(aoiDataSource, true);
      viewer.dataSources.remove(transmittersDataSource, true);
      // viewer.dataSources.removeAll(true);
      // console.log("Cleared old");
    }

    function reloadRX() {
      viewer.dataSources.remove(receiversDataSource, true);
      loadRxCzml();
    }

    function reloadAoi() {
      viewer.dataSources.remove(aoiDataSource, true);
      loadAoiCzml();
    }

  </script>
  <div id="cardsmenu">
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
        <input id="add_aoi" class="edit-checkbox add-icon" type="checkbox" style="width: 23px; height: 23px;"/>
        <span id="add_aoi_icon" class="material-icons add-icon no-select">add_circle_outline</span>
        <input id="run_aoi_rules" class="edit-checkbox aoi-rule-icon" type="checkbox"
        title="Apply All AOI Rules. Do not click this before defining all off your AOIs.
        It will permanently delete intersections!" style="width: 23px; height: 23px;"/>
        <span id="run_aoi_icon" class="material-icons aoi-rule-icon no-select">rule</span>
        <div style="visibility: hidden; height: 0;" id="new_aoi_div" style="padding: 0;">
          <span id="new-aoi"></span>
        </div>
      </div>
      <hr>
      <div id="exclusioncards" class="menusections">
        <h2 style="color: #eee; padding-left: 5px;">Exclusion Areas</h2>
        <input id="add_exclusion" class="edit-checkbox add-icon" type="checkbox" style="width: 23px; height: 23px;"/>
        <span id="add_exclusion_icon" class="material-icons add-icon no-select">add_circle_outline</span>
        <div style="visibility: hidden; height: 0;" id="new_exclusion_div" style="padding: 0;">
          <span id="new-exclusion"></span>
        </div>
      </div>
    </ul>
  </div>
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
        <input name="powerValue" type="range" min="0" max="100" value="{{minpower}}" class="slider" id="powerRange">
      </span>
      <span class="slidevalue" id="power"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Minimum Confidence:<br>
        Minimum confidence level to record an intersection. Does not affect historical data.</span>
      <span class="slidespan">
        <input name="confValue" type="range" min="0" max="300" value="{{minconf}}" class="slider" id="confRange">
      </span>
      <span class="slidevalue" id="confidence"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Epsilon:<br>
        Maximum distance between neighboring points in a cluster.<br>
        </span>
      <span class="slidespan">
        <input name="epsilonValue" type="range" min="0" max="2" step="0.01" value="{{0 if epsilon == "auto" else epsilon}}" class="slider" id="epsilonRange">
      </span>
      <span class="slidevalue" id="epsilon"></span>
    </div>
    <div class="tooltip">
      <span class="tooltiptext">Minimum points per sample in a cluster.</span>
      <span class="slidespan">
        <input name="minpointValue" type="range" min="0" max="300" step="5" value="{{0 if minpoints == "auto" else minpoints}}" class="slider" id="minpointRange">
      </span>
      <span class="slidevalue" id="minpoints"></span>
    </div>
    <div style="width: 600px">
      <span class="tooltip">
        <span class="slidetitle"><h4>Clustering:</h4></span>
        <span class="slidespan" style="text-align:left; width: 100px;margin: 5px;">
        <label class="switch">
          <input id="clustering_en" name="clustering_en" {{"checked" if epsilon == "auto" else ""}} type="checkbox" onchange="updateParams()">
          <span class="switchslider round"></span>
        </label></span>
        <span class="tooltiptext">Turns clustering on or off. Clustering On will draw ellipses.
        Disabling clustering will plot all intersections and may cause longer load times.</span>
      </span>
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
    if (epsslider.value == 0) {
      epsoutput.innerHTML = "Auto";
    } else {
      epsoutput.innerHTML = epsslider.value;
    }

    var minpointslider = document.getElementById("minpointRange");
    var minpointoutput = document.getElementById("minpoints");
    if (minpointslider.value == 0) {
      minpointoutput.innerHTML = "Auto";
    } else {
      minpointoutput.innerHTML = minpointslider.value;
    }

    var rx_enable = document.getElementById("rx_en");

    var intersect_en = document.getElementById("intersect_en");
    // var clustering_en = document.getElementById("clustering_en");

    // Update the current slider value (each time you drag the slider handle)
    epsslider.oninput = function() {
      if (this.value > 0) {
        epsoutput.innerHTML = this.value;
      } else {
        epsoutput.innerHTML = "Auto";
      }
    }
    epsslider.onpointerup = function() {
      updateParams("");
    }
    powerslider.oninput = function() {
      poweroutput.innerHTML = this.value;
    }
    powerslider.onpointerup = function() {
      updateParams("minpower="+this.value);
    }
    confslider.oninput = function() {
      confoutput.innerHTML = this.value;
    }
    confslider.onpointerup = function() {
      updateParams("minconf="+this.value);
    }
    minpointslider.oninput = function() {
      if (this.value > 0) {
        minpointoutput.innerHTML = this.value;
      } else {
        minpointoutput.innerHTML = "Auto";
      }
    }
    minpointslider.onpointerup = function() {
      updateParams("");
    }

    rx_enable.onchange = function() {
      if (rx_enable.checked) {
        updateParams("rx=true");
      } else {
        updateParams("rx=false");
      }
    }

    intersect_en.onchange = function() {
      updateParams("");
    }

  </script>
</body>
</html>
