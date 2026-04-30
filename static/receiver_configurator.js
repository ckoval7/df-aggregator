var refreshrate = 2500;
var autoRefresh = setInterval(function() { reloadRX(); }, refreshrate);

function updateRx(callBack, id) {
  fetch("/rx_params")
    .then(function(data) { return data.json(); })
    .then(function(res) { callBack(res, id); });
}

function makeNewRx(url) {
  var otherParams = {
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ station_url: url }),
    method: "PUT"
  };
  fetch("/rx_params/new", otherParams)
    .then(function() {
      loadRx(function(rx_json) {
        createReceivers(rx_json);
        statusBar.updateReceiverStats(rx_json);
      });
      reloadRX();
    });
}

function destroyRxCards() {
  document.querySelectorAll('.rx-card').forEach(function(e) { e.remove(); });
}

function deleteReceiver(uid) {
  var otherParams = {
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ uid: uid }),
    method: "PUT"
  };
  fetch("/rx_params/del", otherParams)
    .then(function() {
      loadRx(function(rx_json) {
        createReceivers(rx_json);
        statusBar.updateReceiverStats(rx_json);
      });
      reloadRX();
    });
}

function activateReceiver(uid, state) {
  var otherParams = {
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ uid: uid, state: state }),
    method: "PUT"
  };
  fetch("/rx_params/activate", otherParams)
    .then(function() {
      loadRx(function(rx_json) {
        refreshRx(rx_json);
        statusBar.updateReceiverStats(rx_json);
      });
      reloadRX();
    });
}

function buildRxCardHtml(rx) {
  var isActive = rx.active;
  var stateClass = isActive ? 'active' : 'inactive';
  var dotClass = isActive ? 'dot-good' : 'dot-bad';
  var pillClass = isActive ? 'pill-good' : 'pill-mute';
  var pillText = isActive ? 'ONLINE' : 'OFFLINE';
  var powerTitle = isActive ? 'Disable' : 'Enable';

  var html = '<div class="rx-head">';
  html += '<span class="dot ' + dotClass + '"></span>';
  html += '<span class="rx-id">' + rx.station_id + '</span>';
  html += '<span class="status-pill ' + pillClass + '">' + pillText + '</span>';
  html += '<div class="rx-actions">';
  html += '<button class="icon-btn-sm" title="' + powerTitle + '" data-action="activate" data-uid="' + rx.uid + '">';
  html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/></svg>';
  html += '</button>';
  html += '<button class="icon-btn-sm" title="Edit" data-action="edit" data-uid="' + rx.uid + '">';
  html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 1 1 3 3L7 19l-4 1 1-4z"/></svg>';
  html += '</button>';
  html += '<button class="icon-btn-sm icon-btn-danger" title="Delete" data-action="delete" data-uid="' + rx.uid + '">';
  html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>';
  html += '</button>';
  html += '</div></div>';

  html += '<div id="rx-body-' + rx.uid + '">';
  html += '<div class="rx-grid">';
  html += '<div class="kv"><span class="k">LAT</span><span class="v">' + parseFloat(rx.latitude).toFixed(6) + '°</span></div>';
  html += '<div class="kv"><span class="k">LON</span><span class="v">' + parseFloat(rx.longitude).toFixed(6) + '°</span></div>';
  html += '<div class="kv"><span class="k">HDG</span><span class="v">' + rx.heading + '°</span></div>';
  html += '<div class="kv"><span class="k">FREQ</span><span class="v accent">' + rx.frequency + ' MHz</span></div>';
  html += '</div>';

  if (isActive) {
    var sig = rx.signal || 0;
    var conf = rx.conf || 0;
    html += '<div class="signal-bar">';
    html += '<div class="signal-label">SIG</div>';
    html += '<div class="signal-track"><div class="signal-fill" style="width:' + sig + '%"></div></div>';
    html += '<div class="signal-val">' + sig + '</div>';
    html += '<div class="signal-label">CONF</div>';
    html += '<div class="signal-track"><div class="signal-fill alt" style="width:' + Math.min(conf, 100) + '%"></div></div>';
    html += '<div class="signal-val">' + conf + '</div>';
    html += '</div>';
  }
  html += '</div>';

  return { stateClass: stateClass, html: html };
}

function createReceivers(rx_json, id) {
  destroyRxCards();
  var receivers = rx_json.receivers;
  var container = document.getElementById("rx-cards");
  var count = Object.keys(receivers).length;
  document.getElementById("rx-count-pill").textContent = count;

  for (var i = 0; i < count; i++) {
    var rx = receivers[i];
    var result = buildRxCardHtml(rx);
    var card = document.createElement('div');
    card.className = 'card rx-card ' + result.stateClass;
    card.id = 'rx-' + rx.uid;
    card.innerHTML = result.html;
    container.appendChild(card);
  }
  wireRxCardActions();
}

function wireRxCardActions() {
  document.getElementById("rx-cards").querySelectorAll('[data-action]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var uid = parseInt(btn.getAttribute('data-uid'));
      var action = btn.getAttribute('data-action');
      if (action === 'delete') {
        deleteReceiver(uid);
      } else if (action === 'activate') {
        updateRx(function(rx_json) {
          var rx = rx_json.receivers[uid];
          activateReceiver(uid, !rx.active);
        }, uid);
      } else if (action === 'edit') {
        updateRx(editReceivers, uid);
      }
    });
  });
}

function editReceivers(rx_json, uid) {
  var receivers = rx_json.receivers;
  var rx = receivers[uid];
  var card = document.getElementById('rx-' + uid);
  var body = document.getElementById('rx-body-' + uid);

  if (card.classList.contains('editing')) {
    var isMobile = document.getElementById('edit-mobile-' + uid);
    var isInverted = document.getElementById('edit-invert-' + uid);
    var isSingle = document.getElementById('edit-single-' + uid);

    rx.mobile = isMobile ? isMobile.checked : rx.mobile;
    rx.inverted = isInverted ? isInverted.checked : rx.inverted;
    rx.single = isSingle ? isSingle.checked : false;

    var otherParams = {
      headers: { "content-type": "application/json" },
      body: JSON.stringify(rx),
      method: "PUT"
    };
    fetch('/rx_params/' + uid, otherParams)
      .then(function() {
        card.classList.remove('editing');
        autoRefresh = setInterval(function() { reloadRX(); }, refreshrate);
        loadRx(function(rx_json) {
          createReceivers(rx_json);
          statusBar.updateReceiverStats(rx_json);
        });
        reloadRX();
      });
    return;
  }

  clearInterval(autoRefresh);
  card.classList.add('editing');

  var isMobileChecked = rx.mobile ? 'checked' : '';
  var isInvertedChecked = rx.inverted ? 'checked' : '';
  var isSingleChecked = rx.single ? 'checked' : '';

  var editHtml = '<div class="rx-edit-grid">';
  editHtml += '<label><span>STATION ID</span>';
  editHtml += '<input type="text" id="edit-id-' + uid + '" value="' + rx.station_id + '"></label>';
  editHtml += '<label><span>LATITUDE</span>';
  editHtml += '<input type="text" id="edit-lat-' + uid + '" value="' + rx.latitude + '"></label>';
  editHtml += '<label><span>LONGITUDE</span>';
  editHtml += '<input type="text" id="edit-lon-' + uid + '" value="' + rx.longitude + '"></label>';
  editHtml += '<label><span>HEADING</span>';
  editHtml += '<input type="text" id="edit-hdg-' + uid + '" value="' + rx.heading + '"></label>';
  editHtml += '<label><span>FREQUENCY</span>';
  editHtml += '<input type="text" id="edit-freq-' + uid + '" value="' + rx.frequency + '"></label>';
  editHtml += '</div>';
  editHtml += '<div class="rx-edit-toggles">';
  editHtml += '<label><input type="checkbox" id="edit-mobile-' + uid + '" ' + isMobileChecked + '> Mobile</label>';
  editHtml += '<label><input type="checkbox" id="edit-invert-' + uid + '" ' + isInvertedChecked + '> Inverted DOA</label>';
  if (rx.mobile) {
    editHtml += '<label><input type="checkbox" id="edit-single-' + uid + '" ' + isSingleChecked + '> Single Rx</label>';
  }
  editHtml += '</div>';
  editHtml += '<div style="margin-top:8px; display:flex; gap:6px;">';
  editHtml += '<button class="btn btn-primary" style="flex:1" data-action="edit" data-uid="' + uid + '">Save</button>';
  editHtml += '<button class="btn btn-ghost" style="flex:0" onclick="autoRefresh=setInterval(function(){reloadRX()},refreshrate);loadRx(function(r){createReceivers(r);statusBar.updateReceiverStats(r)})">Cancel</button>';
  editHtml += '</div>';

  body.innerHTML = editHtml;
  wireRxCardActions();
}

function showReceivers(rx_json, uid) {
  var receivers = rx_json.receivers;
  var rx = receivers[uid];
  var card = document.getElementById('rx-' + uid);
  if (!card || card.classList.contains('editing')) return;

  var result = buildRxCardHtml(rx);
  card.className = 'card rx-card ' + result.stateClass;
  card.innerHTML = result.html;
  wireRxCardActions();
}

function refreshRx(rx_json, id) {
  var receivers = rx_json.receivers;
  for (var i = 0; i < Object.keys(receivers).length; i++) {
    showReceivers(rx_json, receivers[i].uid);
  }
  document.getElementById("rx-count-pill").textContent = Object.keys(receivers).length;
}

function loadRx(action) {
  updateRx(action, null);
}
