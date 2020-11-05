<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <!-- Include the CesiumJS JavaScript and CSS files -->
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.75/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
</head>
<body>
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

    const buildingTileset = viewer.scene.primitives.add(Cesium.createOsmBuildings());
    // viewer.dataSources.add(Cesium.GeoJsonDataSource.load('/static/dc_med.geojson', {
    //   clampToGround: true,
    //   //markerColor: Cesium.Color.GREEN,
    //   markerSymbol: ''
    // }));

    // Add Cesium OSM Buildings, a global 3D buildings layer.

  </script>
 </div>
 <h2>Marble Cake also the Game</h2>
</body>
</html>
