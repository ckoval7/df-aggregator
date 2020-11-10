<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <!-- Include the CesiumJS JavaScript and CSS files -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <link href="/static/style.css" rel="stylesheet">
</head>
<body>
  <h2>DF Aggregator</h2>
  <div id="cesiumContainer" style="height: 800px"></div>
  <script>
    // Your access token can be found at: https://cesium.com/ion/tokens.
    Cesium.Ion.defaultAccessToken = '{{access_token}}';
    var viewer = new Cesium.Viewer('cesiumContainer', {
      terrainProvider: Cesium.createWorldTerrain()
    });

    var dataSourcePromise = Cesium.CzmlDataSource.load('/static/output.czml');
    viewer.dataSources.add(dataSourcePromise);
    viewer.zoomTo(dataSourcePromise);

    // Add Cesium OSM Buildings, a global 3D buildings layer.
    // const buildingTileset = viewer.scene.primitives.add(Cesium.createOsmBuildings());

  </script>
 </div>
 <div class="slidecontainer">
  <form action="/" method="post">
    <div><span class="slidetitle"><h4>Min Power*:</h4></span>
    <span class="slidespan"><input name="powerValue" type="range" min="0" max="100" value="{{minpower}}" class="slider" id="powerRange"></span><
    <span class="slidevalue" id="power"></span></div>
    <div><span class="slidetitle"><h4>Min Confidence*:</h4></span>
    <span class="slidespan"><input name="confValue" type="range" min="0" max="100" value="{{minconf}}" class="slider" id="confRange"></span>
    <span class="slidevalue" id="confidence"></span></div>
    <div><span class="slidetitle"><h4>epsilon:</h4></span>
    <span class="slidespan"><input name="epsilonValue" type="range" min="0" max="100" value="{{epsilon}}" class="slider" id="epsilonRange"></span>
    <span class="slidevalue" id="epsilon"></span></div>
    <div><span class="slidetitle"><h4>Min Points per Cluster:</h4></span>
    <span class="slidespan"><input name="minpointValue" type="range" min="0" max="200" value="{{minpoints}}" class="slider" id="minpointRange"></span>
    <span class="slidevalue" id="minpoints"></span></div>
    <div><span class="slidetitle"><h4>Receiver Enable:</h4></span>
    <span class="slidespan" style="text-align:left; width: 80px;">
    <!-- Rounded switch -->
    <label class="switch">
      <input name="rx_en" {{rx_state}} type="checkbox">
      <span class="switchslider round"></span>
    </label></span>
    <span class="slidetitle"><h4>Plot All intersect Points**:</h4></span>
    <span class="slidespan" style="text-align:left; width: 80px;">
    <!-- Rounded switch -->
    <label class="switch">
      <input name="intersect_en" {{intersect_state}} type="checkbox">
      <span class="switchslider round"></span>
    </label></span><span>Enabling this can cause longer load times.</span></div>
    <div style="width:15%; text-align:right;"><input value="Update" type="submit" style="height:40px;"/></div>
  </form>

<p>* Does not affect historical data.</p>
<p>** This setting does not apply if clustering is turned off (epsilon = 0).</p>
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
epsoutput.innerHTML = epsslider.value/100;

var minpointslider = document.getElementById("minpointRange");
var minpointoutput = document.getElementById("minpoints");
minpointoutput.innerHTML = minpointslider.value;

// Update the current slider value (each time you drag the slider handle)
epsslider.oninput = function() {
  epsoutput.innerHTML = this.value/100;
}
powerslider.oninput = function() {
  poweroutput.innerHTML = this.value;
}
confslider.oninput = function() {
  confoutput.innerHTML = this.value;
}
minpointslider.oninput = function() {
  minpointoutput.innerHTML = this.value;
}
</script>
</body>
</html>
