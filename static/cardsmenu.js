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
    document.getElementById("new_rx_div").style.padding = "5px";
    document.getElementById("add_station_icon").innerHTML = "save";
  } else {
    var newrxurl = stationUrlHtml_new.value
    if (newrxurl != "") {
      makeNewRx(newrxurl);
    }
    document.getElementById("new_rx_div").style.height = 0;
    document.getElementById("new_rx_div").style.visibility = "hidden";
    document.getElementById("new_rx_div").style.padding = "0";
    document.getElementById("add_station_icon").innerHTML = "add_circle_outline";
  }
}

var aoi_br = document.createElement("br");
var aoi_latlon_label = document.createTextNode("Lat, Lon:");
var aoi_lat_lon = document.createElement('input');
aoi_lat_lon.type = 'text';
aoi_lat_lon.id = 'aoi-new-latlon';
aoi_lat_lon.style.width = '300px';
var new_aoi = document.getElementById("new-aoi");
new_aoi.appendChild(aoi_latlon_label);
new_aoi.appendChild(aoi_lat_lon);
var aoi_radius_label = document.createTextNode("Radius:");
var aoi_radius = document.createElement('input');
aoi_radius.type = 'text';
aoi_radius.id = 'aoi-new-radius';
aoi_radius.style.width = '300px';
new_aoi.appendChild(aoi_br);
new_aoi.appendChild(aoi_radius_label);
new_aoi.appendChild(aoi_radius);
var add_aoi = document.getElementById("add_aoi"); //Button to add new RX
add_aoi.onchange = function() {
  if (add_aoi.checked) {
    clearHover();
    document.getElementById("add_aoi_icon").innerHTML = "save";
    pickCenter(aoi_lat_lon, aoi_radius, Cesium.Color.CORNFLOWERBLUE);
    aoi_lat_lon.value = "";
    aoi_radius.value = "";
    document.getElementById("new_aoi_div").style.height = 'auto';
    document.getElementById("new_aoi_div").style.visibility = "visible";
    document.getElementById("new_aoi_div").style.padding = "5px";
  } else {
    document.getElementById("new_aoi_div").style.height = 0;
    document.getElementById("new_aoi_div").style.visibility = "hidden";
    document.getElementById("new_aoi_div").style.padding = "0";
    document.getElementById("add_aoi_icon").innerHTML = "add_circle_outline";
    clearHover();
  }
}

var exclusion_br = document.createElement("br");
var exclusion_latlon_label = document.createTextNode("Lat, Lon:");
var exclusion_lat_lon = document.createElement('input');
exclusion_lat_lon.type = 'text';
exclusion_lat_lon.id = 'exclusion-new-latlon';
exclusion_lat_lon.style.width = '300px';
var new_exclusion = document.getElementById("new-exclusion");
new_exclusion.appendChild(exclusion_latlon_label);
new_exclusion.appendChild(exclusion_lat_lon);
var exclusion_radius_label = document.createTextNode("Radius:");
var exclusion_radius = document.createElement('input');
exclusion_radius.type = 'text';
exclusion_radius.id = 'exclusion-new-radius';
exclusion_radius.style.width = '300px';
new_exclusion.appendChild(exclusion_br);
new_exclusion.appendChild(exclusion_radius_label);
new_exclusion.appendChild(exclusion_radius);
var add_exclusion = document.getElementById("add_exclusion"); //Button to add new RX
add_exclusion.onchange = function() {
  if (add_exclusion.checked) {
    clearHover();
    document.getElementById("add_exclusion_icon").innerHTML = "save";
    pickCenter(exclusion_lat_lon, exclusion_radius, Cesium.Color.ORANGE);
    exclusion_lat_lon.value = "";
    exclusion_radius.value = "";
    document.getElementById("new_exclusion_div").style.height = 'auto';
    document.getElementById("new_exclusion_div").style.visibility = "visible";
    document.getElementById("new_exclusion_div").style.padding = "5px";
  } else {
    document.getElementById("new_exclusion_div").style.height = 0;
    document.getElementById("new_exclusion_div").style.visibility = "hidden";
    document.getElementById("new_exclusion_div").style.padding = "0";
    document.getElementById("add_exclusion_icon").innerHTML = "add_circle_outline";
    clearHover();
  }
}
