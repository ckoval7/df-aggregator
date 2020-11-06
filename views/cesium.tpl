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
    const buildingTileset = viewer.scene.primitives.add(Cesium.createOsmBuildings());

  </script>
 </div>
 <div class="slidecontainer">
  <form action="/" method="post">
    <span><h4>epsilon:</h4></span>
    <span class="slidespan"><input name="epsilonValue" type="range" min="0" max="100" value="{{epsilon}}" class="slider" id="epsilonRange"></span>
  	<span><p><input value="Update" type="submit" style="height:40px;"/></p></span>
  </form>
  <p>Value: <span id="epsilon"></span></p>
</div>
<script>
var slider = document.getElementById("epsilonRange");
var output = document.getElementById("epsilon");
output.innerHTML = slider.value/100; // Display the default slider value

// Update the current slider value (each time you drag the slider handle)
slider.oninput = function() {
  output.innerHTML = this.value/100;
}
</script>
 <h4>Buttons here in the future!</h4>
</body>
</html>
