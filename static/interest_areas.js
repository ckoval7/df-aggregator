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

// *************************************************
// * Gets AOI data from backend
// *************************************************
function updateAoi(callBack, id) {
    fetch("/interest_areas")
        .then(data => { return data.json() })
        .then(res => { callBack(res, id);
      })
}

// ****************************************************
// * Sends AOI Information to backend and refreshes map
// ****************************************************
function makeNewAoi(aoi_type, latitude, longitude, radius) {
    const new_aoi = {
      "aoi_type": aoi_type,
      "latitude": latitude,
      "longitude": longitude,
      "radius": radius
    };
    // console.log(new_rx);
    const otherParams = {
        headers: {
            "content-type": "application/json"
        },
        body: JSON.stringify(new_aoi),
        method: "PUT"
    };
    // clearOld();
    fetch("/interest_areas/new", otherParams)
        .then(res => {
          updateAoi(createAois, true);
          reloadAoi();
        })
}

// *******************************************
// * Removes AOI from Backend and Reloads Map
// *******************************************
function deleteAoi(uid) {
    const del_aoi = { "uid": uid };
    // console.log(new_rx);
    const otherParams = {
        headers: {
            "content-type": "application/json"
        },
        body: JSON.stringify(del_aoi),
        method: "PUT"
    };
    // clearOld();
    fetch("/interest_areas/del", otherParams)
        .then(res => {
          // removerx(uid);
          loadAoi(createAois);
          reloadAoi();
        })
}

// *******************************************
// * Purges intersects from Backend and Reloads Map
// *******************************************
function purgeAoi(uid) {
    const del_aoi = { "uid": uid };
    // console.log(new_rx);
    const otherParams = {
        headers: {
            "content-type": "application/json"
        },
        body: JSON.stringify(del_aoi),
        method: "PUT"
    };
    // clearOld();
    fetch("/interest_areas/purge", otherParams)
        .then(res => {
          // removerx(uid);
          loadAoi(createAois);
          reloadAoi();
        })
}

// *******************************************
// * Runs all AOI rules on the backend and Reloads Map
// *******************************************
function runAoi(uid) {
    // clearOld();
    fetch("/run_all_aoi_rules")
        .then(res => {
          // removerx(uid);
          loadAoi(createAois);
          reloadAoi();
        })
}

// *****************************************
// * Removes ALL of the RX Cards
// *****************************************
function destroyAoiCards() {
  document.querySelectorAll('.aoi').forEach(e => e.remove());
}

// *******************************************
// * Fills in AOI UI cards with AOI info
// *******************************************
function showAois(aoi_json, index, uid) {
    const interest_areas = aoi_json['aois'];

    var locationHtml =
        "Location: " + interest_areas[index].latitude + "&#176;, " + interest_areas[index].longitude + "&#176;";

    var radius =
        "Radius: " + interest_areas[index].radius + " meters";

    const locationspan = document.getElementById(uid + "-aoi_location");
    const radiusspan = document.getElementById(uid + "-aoi_radius");

    locationspan.innerHTML = locationHtml;
    radiusspan.innerHTML = radius;

}

// ****************************************************
// * Creates cards on UI for AOI information.
// * Iterates through AOI objects on page load/AOI add.
// ****************************************************
function createAois(aoi_json, id) {
    destroyAoiCards();
    let interest_areas = aoi_json['aois'];
    // console.log(interest_areas);
    for (let i = 0; i < Object.keys(interest_areas).length; i++) {

        const aoicard = document.createElement('div');
        aoicard.className = "aoi";
        aoicard.id = "aoi-" + interest_areas[i].uid;

        const locationspan = document.createElement('span');
        const radiusspan = document.createElement('span');

        const deleteiconspan = document.createElement('span');
        deleteiconspan.classList.add("material-icons", "delete-icon", "no-select");
        deleteiconspan.innerHTML = "delete";

        const deletecheck = document.createElement('input');
        deletecheck.classList.add("edit-checkbox", "delete-icon");
        deletecheck.type = 'checkbox';
        deletecheck.id = interest_areas[i].uid + "-aoi_delete";
        deletecheck.setAttribute('onclick', "deleteAoi(" + interest_areas[i].uid + ")");

        locationspan.id = interest_areas[i].uid + "-aoi_location";
        radiusspan.id = interest_areas[i].uid + "-aoi_radius";

        if (interest_areas[i].aoi_type == "aoi") {
          document.getElementById("aoicards").insertBefore(aoicard, document.getElementById("add_aoi"));
        } else if (interest_areas[i].aoi_type == "exclusion") {
          document.getElementById("exclusioncards").insertBefore(aoicard, document.getElementById("add_exclusion"));
          const purgeiconspan = document.createElement('span');
          purgeiconspan.classList.add("material-icons", "edit-icon", "no-select");
          purgeiconspan.innerHTML = "rule";
          const purgecheck = document.createElement('input');
          purgecheck.classList.add("edit-checkbox", "edit-icon");
          purgecheck.type = 'checkbox';
          purgecheck.id = interest_areas[i].uid + "-aoi_purge";
          purgecheck.setAttribute('onclick', "purgeAoi(" + interest_areas[i].uid + ")");
          purgecheck.setAttribute("title", "Purge database of entries inside this area.\nThis cannot be undone!");
          aoicard.appendChild(purgeiconspan);
          aoicard.appendChild(purgecheck);
        }

        aoicard.appendChild(locationspan);
        aoicard.appendChild(radiusspan);

        aoicard.appendChild(deleteiconspan);
        aoicard.appendChild(deletecheck);

        showAois(aoi_json, i, interest_areas[i].uid);
    }
}

// ****************************************************
// * Refreshes info on Aoi UI Cards (Refresh button)
// ****************************************************
function refreshAoi(aoi_json, id) {
    const interest_areas = aoi_json['interest_areas'];
    for (let i = 0; i < Object.keys(interest_areas).length; i++) {
        showAois(aoi_json, interest_areas[i].uid);
    }
}

// ****************************************************
// * Main function - Loads all Receivers
// ****************************************************
function loadAoi(action) {
    updateAoi(action, null);
}
