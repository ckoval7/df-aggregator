// df-aggregator, networked radio direction finding software.
//     Copyright (C) 2020 Corey Koval
//
//     This program is free software: you can redistribute it and/or modify
//     it under the terms of the GNU General Public License as published by
//     the Free Software Foundation, either version 3 of the License, or
//     (at your option) any later version.
//
//     This program is distributed in the hope that it will be useful,
//     but WITHOUT ANY WARRANTY; without even the implied warranty of
//     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//     GNU General Public License for more details.
//
//     You should have received a copy of the GNU General Public License
//     along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
var aoi_latlabel = document.createTextNode("Lat:");
var aoi_lat = document.createElement('input');
aoi_lat.type = 'text';
aoi_lat.id = 'aoi-new-lat';
aoi_lat.style.width = '140px';
var new_aoi = document.getElementById("new-aoi");
new_aoi.appendChild(aoi_latlabel);
new_aoi.appendChild(aoi_lat);

var aoi_br = document.createElement("br");
var aoi_lonlabel = document.createTextNode(" Lon:");
var aoi_lon = document.createElement('input');
aoi_lon.type = 'text';
aoi_lon.id = 'aoi-new-lon';
aoi_lon.style.width = '140px';
var new_aoi = document.getElementById("new-aoi");
new_aoi.appendChild(aoi_lonlabel);
new_aoi.appendChild(aoi_lon);

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
    pickCenter(aoi_lat, aoi_lon, aoi_radius, Cesium.Color.CORNFLOWERBLUE);
    aoi_lat.value = "";
    aoi_lon.value = "";
    aoi_radius.value = "";
    document.getElementById("new_aoi_div").style.height = 'auto';
    document.getElementById("new_aoi_div").style.visibility = "visible";
    document.getElementById("new_aoi_div").style.padding = "5px";
  } else {
    document.getElementById("new_aoi_div").style.height = 0;
    document.getElementById("new_aoi_div").style.visibility = "hidden";
    document.getElementById("new_aoi_div").style.padding = "0";
    document.getElementById("add_aoi_icon").innerHTML = "add_circle_outline";
    makeNewAoi("aoi", aoi_lat.value, aoi_lon.value, aoi_radius.value);
    scene.primitives.remove(area);
    clearHover();
  }
}
var run_aoi_rules = document.getElementById("run_aoi_rules"); //Button to add new RX
run_aoi_rules.onchange = function() {
  if (run_aoi_rules.checked) {
    var user_conf = confirm("Did you define every AOI first?\n\
    You are about to delete every intersection outside of the currently defined AOIs.\
    This cannot be undone! When in doubt, backup your database.");
    if (user_conf) {runAoi()};
    run_aoi_rules.checked = false;
  }
}

var exclusion_br = document.createElement("br");
var exclusion_latlabel = document.createTextNode("Lat:");
var exclusion_lat = document.createElement('input');
exclusion_lat.type = 'text';
exclusion_lat.id = 'exclusion-new-lat';
exclusion_lat.style.width = '140px';
var new_exclusion = document.getElementById("new-exclusion");
new_exclusion.appendChild(exclusion_latlabel);
new_exclusion.appendChild(exclusion_lat);

var exclusion_br = document.createElement("br");
var exclusion_lonlabel = document.createTextNode(" Lon:");
var exclusion_lon = document.createElement('input');
exclusion_lon.type = 'text';
exclusion_lon.id = 'exclusion-new-lon';
exclusion_lon.style.width = '140px';
var new_exclusion = document.getElementById("new-exclusion");
new_exclusion.appendChild(exclusion_lonlabel);
new_exclusion.appendChild(exclusion_lon);

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
    pickCenter(exclusion_lat, exclusion_lon, exclusion_radius, Cesium.Color.ORANGE);
    exclusion_lat.value = "";
    exclusion_lon.value = "";
    exclusion_radius.value = "";
    document.getElementById("new_exclusion_div").style.height = 'auto';
    document.getElementById("new_exclusion_div").style.visibility = "visible";
    document.getElementById("new_exclusion_div").style.padding = "5px";
  } else {
    document.getElementById("new_exclusion_div").style.height = 0;
    document.getElementById("new_exclusion_div").style.visibility = "hidden";
    document.getElementById("new_exclusion_div").style.padding = "0";
    document.getElementById("add_exclusion_icon").innerHTML = "add_circle_outline";
    makeNewAoi("exclusion", exclusion_lat.value, exclusion_lon.value, exclusion_radius.value);
    scene.primitives.remove(area);
    clearHover();
  }
}
