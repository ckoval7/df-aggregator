// *************************************************
// * Gets Rx data from backend
// *************************************************
function updateRx(callBack, id) {
  fetch("/rx_params")
  .then(data=>{return data.json()})
  .then(res=>{callBack(res, id)})
}

// ******************************************************
// * Makes Changes to Receiver, Saves, & Refreshes Cards
// ******************************************************
function editReceivers(rx_json, id) {
  const receivers = rx_json['receivers'];
  var stationUrlHtml =
  "<input type=\"hidden\" id=\"url_" + id + "\"/>";

  var stationIDhtml =
  "Station ID: <a href=\"" + receivers[id].station_url + "\" target=\"_blank\">" + receivers[id].station_id + "</a>";

  var manualInfo =
  "<input type=\"hidden\" id=\"manual_toggle_" + receivers[id].uid + "\"/>";

  var locationHtml =
  "Location: " + receivers[id].latitude + "&#176;, " + receivers[id].longitude + "&#176;";

  var heading =
  "Heading: " + receivers[id].heading + "&#176;";

  var freqHtml =
  "Tuned to " + receivers[id].frequency + " MHz";

  var edit_stationUrlHtml =
  "Station URL:<input style=\"width: 300px;\" type=\"text\" value=\"" + receivers[id].station_url + "\" name=\"station_url_" + id + "\" />";

  var edit_stationIDhtml =
  "Station ID:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].station_id + "\" name=\"station_id_" + id + "\" />";

  var edit_manualInfo =
  "Manually input receiver info: <input id=\"manual_toggle_" + id + "\" type=\"checkbox\" />";

  var edit_locationHtml =
  "Latitude:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].latitude + "\" name=\"station_lat_" + id + "\" />"
  + " Longitude:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].longitude + "\" name=\"station_lon_" + id + "\" />";

  var edit_heading =
  "Heading:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].heading + "\" name=\"station_heading_" + id + "\" />";

  var edit_freqHtml =
  "Frequency:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].frequency + "\" name=\"frequency_" + id + "\" />";

  var mobile = id + "-mobile";
  var editButton = document.getElementById(id + "-edit");
  var isMobileCheck = document.getElementById("mobilerx_toggle_" + id);
  if (editButton.checked) {
    let isMobile = "";
    if (receivers[id].mobile) isMobile = "checked";
    document.getElementById(id + "-editicon").innerHTML = "save";
    document.getElementById(mobile).innerHTML =
    "Mobile Receiver: <input " + isMobile + " id=\"mobilerx_toggle_" + id + "\" type=\"checkbox\" />";
    document.getElementById(id + "-manual").innerHTML = edit_manualInfo;
    document.getElementById(id + "-url").innerHTML = edit_stationUrlHtml;
    document.getElementById("manual_toggle_" + id).onchange = function() {
      if (document.getElementById("manual_toggle_" + id).checked) {
        document.getElementById(id + "-id").innerHTML = edit_stationIDhtml;
        document.getElementById(id + "-location").innerHTML = edit_locationHtml;
        document.getElementById(id + "-heading").innerHTML = edit_heading;
        document.getElementById(id + "-freq").innerHTML = edit_freqHtml;
      } else {
        document.getElementById(id + "-id").innerHTML = stationIDhtml;
        document.getElementById(id + "-location").innerHTML = locationHtml;
        document.getElementById(id + "-heading").innerHTML = heading;
        document.getElementById(id + "-freq").innerHTML = freqHtml;
      }
    }
  } else {
    isMobileCheck = document.getElementById("mobilerx_toggle_" + id);
    if (isMobileCheck.checked) {
      receivers[id].mobile = true;
    } else {
      receivers[id].mobile = false;
    }
    const otherParams = {
      headers:{
        "content-type":"application/json"
      },
      body: JSON.stringify(receivers[id]),
      method: "PUT"
    };
    clearOld();
    fetch("/rx_params/" + id, otherParams)
    .then(data=>{return data.json()})
    .then(res=>{updateRx(showReceivers, id)})
    .then(res=>{loadCzml()})
    //.catch(error=>{console.log(error)})
    // updateRx(showReceivers, id);
    // loadCzml();
  }
}

// ****************************************************
// * Sends Rx station URL to backend and refreshes map
// ****************************************************
function makeNewRx(url) {
  const new_rx = {"station_url":url};
  // console.log(new_rx);
  const otherParams = {
    headers:{
      "content-type":"application/json"
    },
    body: JSON.stringify(new_rx),
    method: "PUT"
  };
  clearOld();
  fetch("/rx_params/new", otherParams)
  .then(data=>{return data.json()})
  .then(res=>{updateRx(createReceivers, true)})
  .then(res=>{loadCzml()})
  //.catch(error=>{console.log(error)})
  //.then(updateRx(createReceivers, true));
  // loadCzml();
}

// *****************************************
// * Removes the Rx UI Card
// *****************************************
function removerx(uid) {
  const rxcard = document.getElementById("rx-" + uid);
  rxcard.remove();
}

// *******************************************
// * Removes Rx from Backend and Reloads Map
// *******************************************
function deleteReceiver(uid) {
  const del_rx = {"uid":uid};
  // console.log(new_rx);
  const otherParams = {
    headers:{
      "content-type":"application/json"
    },
    body: JSON.stringify(del_rx),
    method: "PUT"
  };
  clearOld();
  fetch("/rx_params/del", otherParams)
  .then(data=>{return data.json()})
  .then(res=>{removerx(uid)})
  .then(res=>{loadCzml()})
  //.catch(error=>{console.log(error)})
  //.then(updateRx(createReceivers, true));
  // loadCzml();
}

// *******************************************
// * Fills in Rx UI cards with Rx info 
// *******************************************
function showReceivers(rx_json, id) {
  const receivers = rx_json['receivers'];

  var stationUrlHtml =
  "<input type=\"hidden\" id=\"url_" + id + "\"/>";

  var stationIDhtml =
  "Station ID: <a href=\"" + receivers[id].station_url + "\" target=\"_blank\">" + receivers[id].station_id + "</a>";

  var manualInfo =
  "<input type=\"hidden\" id=\"manual_toggle_" + receivers[id].uid + "\"/>";

  var locationHtml =
  "Location: " + receivers[id].latitude + "&#176;, " + receivers[id].longitude + "&#176;";

  var heading =
  "Heading: " + receivers[id].heading + "&#176;";

  var freqHtml =
  "Tuned to " + receivers[id].frequency + " MHz";

  const urlspan = document.getElementById(id + "-url");
  const mobilespan = document.getElementById(id + "-mobile");
  const manualspan = document.getElementById(id + "-manual");
  const idspan = document.getElementById(id + "-id");
  const locationspan =document.getElementById(id + "-location");
  const headingspan = document.getElementById(id + "-heading");
  const freqspan = document.getElementById(id + "-freq");

  document.getElementById(id + "-mobile").innerHTML = "";
  document.getElementById(id + "-editicon").innerHTML = "edit";
  document.getElementById(id + "-manual").innerHTML = manualInfo;
  document.getElementById(id + "-url").innerHTML = stationUrlHtml;
  document.getElementById(id + "-id").innerHTML = stationIDhtml;
  document.getElementById(id + "-location").innerHTML = locationHtml;
  document.getElementById(id + "-heading").innerHTML = heading;
  document.getElementById(id + "-freq").innerHTML = freqHtml;

}

// ****************************************************
// * Creates cards on UI for Receiver information.
// * Iterates through Rx objects on page load/Rx add.
// ****************************************************
function createReceivers(rx_json, id) {
  var receivers
  if (id == true) {
    receivers = [rx_json['receivers'][Object.keys(rx_json['receivers']).length - 1]];
  } else {
    receivers = rx_json['receivers'];
  }
  console.log(receivers);
  for (let i = 0; i < Object.keys(receivers).length; i++) {

    const rxcard = document.createElement('div');
    rxcard.className = "receiver";
    rxcard.id = "rx-" + receivers[i].uid;

    const urlspan = document.createElement('span');
    const mobilespan = document.createElement('span');
    const manualspan = document.createElement('span');
    const idspan = document.createElement('span');
    const locationspan =document.createElement('span');
    const headingspan = document.createElement('span');
    const freqspan = document.createElement('span');

    const editiconspan = document.createElement('span');
    editiconspan.classList.add("material-icons", "edit-icon", "no-select");
    editiconspan.innerHTML = "edit";

    const editcheck = document.createElement('input');
    editcheck.classList.add("edit-checkbox", "edit-icon");
    editcheck.type = 'checkbox';
    editcheck.id = receivers[i].uid + "-edit";
    editcheck.setAttribute('onclick',"updateRx(editReceivers, " + receivers[i].uid + ")");

    const deleteiconspan = document.createElement('span');
    deleteiconspan.classList.add("material-icons", "delete-icon", "no-select");
    deleteiconspan.innerHTML = "delete";

    const deletecheck = document.createElement('input');
    deletecheck.classList.add("edit-checkbox", "delete-icon");
    deletecheck.type = 'checkbox';
    deletecheck.id = receivers[i].uid + "-delete";
    deletecheck.setAttribute('onclick',"deleteReceiver(" + receivers[i].uid + ")");

    urlspan.id = receivers[i].uid + "-url";
    mobilespan.id = receivers[i].uid + "-mobile";
    manualspan.id = receivers[i].uid + "-manual";
    idspan.id = receivers[i].uid + "-id";
    locationspan.id = receivers[i].uid + "-location";
    headingspan.id = receivers[i].uid + "-heading";
    freqspan.id = receivers[i].uid + "-freq";
    editiconspan.id = receivers[i].uid + "-editicon";

    document.getElementById("menu").insertBefore(rxcard, document.getElementById("add_station"));

    rxcard.appendChild(urlspan);
    rxcard.appendChild(mobilespan);
    rxcard.appendChild(manualspan);
    rxcard.appendChild(idspan);
    rxcard.appendChild(locationspan);
    rxcard.appendChild(headingspan);
    rxcard.appendChild(freqspan);
    rxcard.appendChild(editiconspan);
    rxcard.appendChild(deleteiconspan);
    rxcard.appendChild(editcheck);
    rxcard.appendChild(deletecheck);

    showReceivers(rx_json, receivers[i].uid);
  }
}

// ****************************************************
// * Refreshes info on Rx UI Cards (Refresh button)
// ****************************************************
function refreshRx(rx_json, id) {
  const receivers = rx_json['receivers'];
  for (let i = 0; i < Object.keys(receivers).length; i++) {
    showReceivers(rx_json, receivers[i].uid);
  }
}

// ****************************************************
// * Main function - Loads all Receivers
// ****************************************************
function loadRx(action) {
  updateRx(action, null);
}
