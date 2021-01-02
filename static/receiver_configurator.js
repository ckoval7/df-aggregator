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

// Update Map every n milliseconds
var refreshrate = 2500;
var autoRefresh = setInterval(function () { reloadRX(); }, refreshrate);

// *************************************************
// * Gets Rx data from backend
// *************************************************
function updateRx(callBack, id) {
    fetch("/rx_params")
        .then(data => { return data.json() })
        .then(res => { callBack(res, id);
        // console.log("updateRx Complete");
        // console.log(res);
      })
}

// ******************************************************
// * Makes Changes to Receiver, Saves, & Refreshes Cards
// ******************************************************
function editReceivers(rx_json, id) {
    const receivers = rx_json['receivers'];

    let isSingle = "";
    if (receivers[id].single) isSingle = "checked";

    var stationIDhtml =
        "Station ID: <a href=\"" + receivers[id].station_url + "\" target=\"_blank\">" + receivers[id].station_id + "</a>";

    // var manualInfo =
    //     "<input type=\"hidden\" id=\"manual_toggle_" + receivers[id].uid + "\"/>";

    var singleModeHtml = "&emsp;Single Receiver Mode: <input " + isSingle + " id=\"singlerx_toggle_" + id + "\" type=\"checkbox\" />";

    var locationHtml =
        "Location: " + receivers[id].latitude + "&#176;, " + receivers[id].longitude + "&#176;";

    var heading =
        "Heading: " + receivers[id].heading + "&#176;";

    var freqHtml =
        "Tuned to " + receivers[id].frequency + " MHz";

    var edit_stationIDhtml =
        "Station ID:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].station_id + "\" name=\"station_id_" + id + "\" />";

    // var edit_manualInfo =
    //     "Manually input receiver info: <input id=\"manual_toggle_" + id + "\" type=\"checkbox\" />";

    var edit_locationHtml =
        "Latitude:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].latitude + "\" name=\"station_lat_" + id + "\" />" +
        " Longitude:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].longitude + "\" name=\"station_lon_" + id + "\" />";

    var edit_heading =
        "Heading:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].heading + "\" name=\"station_heading_" + id + "\" />";

    var edit_freqHtml =
        "Frequency:<input style=\"width: 105px;\" type=\"text\" value=\"" + receivers[id].frequency + "\" name=\"frequency_" + id + "\" />";

    const mobilespan = document.getElementById(id + "-mobile");
    const singlespan = document.getElementById(id + "-single");
    // var mobile = id + "-mobile";
    var isMobileCheck;
    var isInvertedCheck;
    var isSingleCheck;
    var editButton = document.getElementById(id + "-edit");
    if (editButton.checked) {
        clearInterval(autoRefresh);
        let isMobile = "";
        if (receivers[id].mobile) isMobile = "checked";
        let isInverted = "";
        if (receivers[id].inverted) isInverted = "checked";
        document.getElementById(id + "-editicon").innerHTML = "save";
        mobilespan.innerHTML =
            "Mobile Receiver: <input " + isMobile + " id=\"mobilerx_toggle_" + id + "\" type=\"checkbox\" />";
        document.getElementById(id + "-invert").innerHTML =
            "Inverted DOA: <input " + isInverted + " id=\"invert_toggle_" + id + "\" type=\"checkbox\" />";
        isInvertedCheck = document.getElementById("invert_toggle_" + id);
        isInvertedCheck.setAttribute("title", "KerberosSDR users keep this checked.");

        isMobileCheck = document.getElementById("mobilerx_toggle_" + id);
        if (isMobileCheck.checked) {
            if (isMobileCheck.checked) {
                singlespan.innerHTML = singleModeHtml;
            }
        }
        isMobileCheck.onchange = function() {
            if (isMobileCheck.checked) {
                singlespan.innerHTML = singleModeHtml;
            } else {
                singlespan.innerHTML = "";
            }
        }
        // document.getElementById(id + "-manual").innerHTML = edit_manualInfo;
        // // document.getElementById(id + "-url").innerHTML = edit_stationUrlHtml;
        // document.getElementById("manual_toggle_" + id).onchange = function() {
        //     if (document.getElementById("manual_toggle_" + id).checked) {
        //         document.getElementById(id + "-id").innerHTML = edit_stationIDhtml;
        //         document.getElementById(id + "-location").innerHTML = edit_locationHtml;
        //         document.getElementById(id + "-heading").innerHTML = edit_heading;
        //         document.getElementById(id + "-freq").innerHTML = edit_freqHtml;
        //     } else {
        //         document.getElementById(id + "-id").innerHTML = stationIDhtml;
        //         document.getElementById(id + "-location").innerHTML = locationHtml;
        //         document.getElementById(id + "-heading").innerHTML = heading;
        //         document.getElementById(id + "-freq").innerHTML = freqHtml;
        //     }
        // }
    } else {
        autoRefresh = setInterval(function () { reloadRX(); }, refreshrate);
        isMobileCheck = document.getElementById("mobilerx_toggle_" + id);
        if (isMobileCheck.checked) {
            receivers[id].mobile = true;
        } else {
            receivers[id].mobile = false;
        }

        isInvertedCheck = document.getElementById("invert_toggle_" + id);
        if (isInvertedCheck.checked) {
            receivers[id].inverted = true;
        } else {
            receivers[id].inverted = false;
        }

        try {
          isSingleCheck = document.getElementById("singlerx_toggle_" + id);
          if (isSingleCheck.checked) {
              receivers[id].single = true;
          } else {
              receivers[id].single = false;
          }
        } catch {
            receivers[id].single = false;
        }

        const otherParams = {
            headers: {
                "content-type": "application/json"
            },
            body: JSON.stringify(receivers[id]),
            method: "PUT"
        };
        // clearOld();
        fetch("/rx_params/" + id, otherParams)
            .then(res => {
              updateRx(showReceivers, id);
              reloadRX();
            })
    }
}

// ****************************************************
// * Sends Rx station URL to backend and refreshes map
// ****************************************************
function makeNewRx(url) {
    const new_rx = { "station_url": url };
    // console.log(new_rx);
    const otherParams = {
        headers: {
            "content-type": "application/json"
        },
        body: JSON.stringify(new_rx),
        method: "PUT"
    };
    // clearOld();
    fetch("/rx_params/new", otherParams)
        .then(res => {
          updateRx(createReceivers, true);
          reloadRX();
        })
}

// *****************************************
// * Removes the Rx UI Card
// *****************************************
function removerx(uid) {
    const rxcard = document.getElementById("rx-" + uid);
    rxcard.remove();
}

// *****************************************
// * Removes ALL of the RX Cards
// *****************************************
function destroyRxCards() {
  document.querySelectorAll('.receiver').forEach(e => e.remove());
}

// *******************************************
// * Removes Rx from Backend and Reloads Map
// *******************************************
function deleteReceiver(uid) {
    const del_rx = { "uid": uid };
    // console.log(new_rx);
    const otherParams = {
        headers: {
            "content-type": "application/json"
        },
        body: JSON.stringify(del_rx),
        method: "PUT"
    };
    // clearOld();
    fetch("/rx_params/del", otherParams)
        .then(res => {
          // removerx(uid);
          loadRx(createReceivers);
          reloadRX();
        })
}

// *******************************************************
// * Updates Rx active state from Backend and Reloads Map
// *******************************************************
function activateReceiver(uid, state) {
    const activate_rx = { "uid": uid, "state": state };
    const otherParams = {
        headers: {
            "content-type": "application/json"
        },
        body: JSON.stringify(activate_rx),
        method: "PUT"
    };
    // clearOld();
    fetch("/rx_params/activate", otherParams)
        .then(res => {
          loadRx(refreshRx);
          reloadRX();
        })
}

// *******************************************
// * Fills in Rx UI cards with Rx info
// *******************************************
function showReceivers(rx_json, id) {
    const receivers = rx_json['receivers'];

    // var stationUrlHtml =
    //     "<input type=\"hidden\" id=\"url_" + id + "\"/>";

    var stationIDhtml =
        "Station ID: <a href=\"" + receivers[id].station_url + "\" target=\"_blank\">" + receivers[id].station_id + "</a>";

    // var manualInfo =
    //     "<input type=\"hidden\" id=\"manual_toggle_" + receivers[id].uid + "\"/>";

    var locationHtml =
        "Location: " + receivers[id].latitude + "&#176;, " + receivers[id].longitude + "&#176;";

    var heading =
        "Heading: " + receivers[id].heading + "&#176;";

    var freqHtml =
        "Tuned to " + receivers[id].frequency + " MHz";

    const urlspan = document.getElementById(id + "-url");
    const mobilespan = document.getElementById(id + "-mobile");
    const invertspan = document.getElementById(id + "-invert");
    const singlespan = document.getElementById(id + "-single");
    // const manualspan = document.getElementById(id + "-manual");
    const idspan = document.getElementById(id + "-id");
    const locationspan = document.getElementById(id + "-location");
    const headingspan = document.getElementById(id + "-heading");
    const freqspan = document.getElementById(id + "-freq");
    document.getElementById(id + "-activate")
      .setAttribute('onclick', "activateReceiver(" + receivers[id].uid + ", " + !receivers[id].active + ")");

    if (receivers[id].active == true) {
      document.getElementById(id + "-activate")
        .setAttribute("title", "Click to disable this receiver.");
      document.getElementById(id + "-activateicon").style.color = "black";
    } else {
      document.getElementById(id + "-activateicon").style.color = "red";
      document.getElementById(id + "-activate")
        .setAttribute("title", "Click to enable this receiver.");
    }

    // document.getElementById(id + "-mobile").innerHTML = "";
    mobilespan.innerHTML = "";
    invertspan.innerHTML = "";
    singlespan.innerHTML = "";
    document.getElementById(id + "-editicon").innerHTML = "edit";
    // document.getElementById(id + "-manual").innerHTML = manualInfo;
    // document.getElementById(id + "-url").innerHTML = stationUrlHtml;
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
    destroyRxCards();
    let receivers = rx_json['receivers'];
    // console.log(receivers);
    for (let i = 0; i < Object.keys(receivers).length; i++) {

        const rxcard = document.createElement('div');
        rxcard.className = "receiver";
        rxcard.id = "rx-" + receivers[i].uid;

        // const urlspan = document.createElement('span');
        const mobilespan = document.createElement('span');
        const invertspan = document.createElement('span');
        const singlespan = document.createElement('span');
        // const manualspan = document.createElement('span');
        const idspan = document.createElement('span');
        const locationspan = document.createElement('span');
        const headingspan = document.createElement('span');
        const freqspan = document.createElement('span');

        const editiconspan = document.createElement('span');
        editiconspan.classList.add("material-icons", "edit-icon", "no-select");
        editiconspan.innerHTML = "edit";
        editiconspan.id = receivers[i].uid + "-editicon";

        const editcheck = document.createElement('input');
        editcheck.classList.add("edit-checkbox", "edit-icon");
        editcheck.type = 'checkbox';
        editcheck.id = receivers[i].uid + "-edit";
        editcheck.setAttribute('onclick', "updateRx(editReceivers, " + receivers[i].uid + ")");

        const deleteiconspan = document.createElement('span');
        deleteiconspan.classList.add("material-icons", "delete-icon", "no-select");
        deleteiconspan.innerHTML = "delete";

        const deletecheck = document.createElement('input');
        deletecheck.classList.add("edit-checkbox", "delete-icon");
        deletecheck.type = 'checkbox';
        deletecheck.id = receivers[i].uid + "-delete";
        deletecheck.setAttribute('onclick', "deleteReceiver(" + receivers[i].uid + ")");

        const activateiconspan = document.createElement('span');
        activateiconspan.classList.add("material-icons", "activate-icon", "no-select");
        activateiconspan.innerHTML = "power_settings_new";
        activateiconspan.id = receivers[i].uid + "-activateicon";

        const activatecheck = document.createElement('input');
        activatecheck.classList.add("edit-checkbox", "activate-icon");
        activatecheck.type = 'checkbox';
        activatecheck.id = receivers[i].uid + "-activate";

        // const addnewiconspan = document.createElement('span');
        // addnewiconspan.classList.add("material-icons", "add-icon", "no-select");
        // addnewiconspan.innerHTML = "add_circle_outline"
        // addnewiconspan.id="add_station_icon"
        //
        // const addnewcheck = document.createElement('input');
        // addnewcheck.type = 'checkbox';
        // addnewcheck.id="add_station";
        // addnewcheck.classList.add("edit-checkbox", "add-icon")

        // urlspan.id = receivers[i].uid + "-url";
        mobilespan.id = receivers[i].uid + "-mobile";
        invertspan.id = receivers[i].uid + "-invert";
        singlespan.id = receivers[i].uid + "-single";
        // manualspan.id = receivers[i].uid + "-manual";
        idspan.id = receivers[i].uid + "-id";
        locationspan.id = receivers[i].uid + "-location";
        headingspan.id = receivers[i].uid + "-heading";
        freqspan.id = receivers[i].uid + "-freq";

        document.getElementById("rxcards").insertBefore(rxcard, document.getElementById("add_station"));

        // rxcard.appendChild(urlspan);
        rxcard.appendChild(mobilespan);
        rxcard.appendChild(singlespan);
        rxcard.appendChild(invertspan);
        // rxcard.appendChild(manualspan);
        rxcard.appendChild(idspan);
        rxcard.appendChild(locationspan);
        rxcard.appendChild(headingspan);
        rxcard.appendChild(freqspan);
        rxcard.appendChild(editiconspan);
        rxcard.appendChild(deleteiconspan);
        rxcard.appendChild(activateiconspan);
        rxcard.appendChild(editcheck);
        rxcard.appendChild(deletecheck);
        rxcard.appendChild(activatecheck);

        showReceivers(rx_json, i);
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
