function updateAoi(callBack, id) {
  fetch("/interest_areas")
    .then(function(data) { return data.json(); })
    .then(function(res) { callBack(res, id); });
}

function makeNewAoi(aoi_type, latitude, longitude, radius) {
  var otherParams = {
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ aoi_type: aoi_type, latitude: latitude, longitude: longitude, radius: radius }),
    method: "PUT"
  };
  fetch("/interest_areas/new", otherParams)
    .then(function() {
      loadAoi(function(aoi_json) {
        createAois(aoi_json);
        statusBar.updateAoiStats(aoi_json);
        if (window.mobileUI) mobileUI.updateAoiStats(aoi_json);
      });
      reloadAoi();
    });
}

function deleteAoi(uid) {
  var otherParams = {
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ uid: uid }),
    method: "PUT"
  };
  fetch("/interest_areas/del", otherParams)
    .then(function() {
      loadAoi(function(aoi_json) {
        createAois(aoi_json);
        statusBar.updateAoiStats(aoi_json);
        if (window.mobileUI) mobileUI.updateAoiStats(aoi_json);
      });
      reloadAoi();
    });
}

function purgeAoi(uid) {
  var otherParams = {
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ uid: uid }),
    method: "PUT"
  };
  fetch("/interest_areas/purge", otherParams)
    .then(function() {
      loadAoi(function(aoi_json) {
        createAois(aoi_json);
        statusBar.updateAoiStats(aoi_json);
        if (window.mobileUI) mobileUI.updateAoiStats(aoi_json);
      });
      reloadAoi();
    });
}

function runAoi() {
  fetch("/run_all_aoi_rules")
    .then(function() {
      loadAoi(function(aoi_json) {
        createAois(aoi_json);
        statusBar.updateAoiStats(aoi_json);
        if (window.mobileUI) mobileUI.updateAoiStats(aoi_json);
      });
      reloadAoi();
    });
}

function destroyAoiCards() {
  document.querySelectorAll('.aoi-card').forEach(function(e) { e.remove(); });
}

function createAois(aoi_json, id) {
  destroyAoiCards();
  var interest_areas = aoi_json.aois;
  var aoiContainer = document.getElementById("aoi-cards");
  var exContainer = document.getElementById("exclusion-cards");
  var aoiCount = 0;
  var exCount = 0;

  for (var i = 0; i < interest_areas.length; i++) {
    var aoi = interest_areas[i];
    var isExclusion = aoi.aoi_type === 'exclusion';
    var kind = isExclusion ? 'exclusion' : 'aoi';
    var dotClass = isExclusion ? 'dot-warn' : 'dot-accent';

    if (isExclusion) { exCount++; } else { aoiCount++; }

    var card = document.createElement('div');
    card.className = 'card aoi-card ' + kind;
    card.id = 'aoi-' + aoi.uid;

    var html = '<div class="aoi-head">';
    html += '<span class="dot ' + dotClass + '"></span>';
    html += '<span class="aoi-label">' + (aoi.label || kind.toUpperCase() + '-' + aoi.uid) + '</span>';
    html += '<div style="margin-left:auto; display:flex; gap:4px;">';
    if (isExclusion) {
      html += '<button class="icon-btn-sm" title="Purge intersections in this area" data-action="purge" data-uid="' + aoi.uid + '">';
      html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>';
      html += '</button>';
    }
    html += '<button class="icon-btn-sm icon-btn-danger" title="Delete" data-action="delete-aoi" data-uid="' + aoi.uid + '">';
    html += '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>';
    html += '</button>';
    html += '</div></div>';

    html += '<div class="aoi-grid">';
    html += '<div class="kv"><span class="k">LAT</span><span class="v">' + parseFloat(aoi.latitude).toFixed(5) + '°</span></div>';
    html += '<div class="kv"><span class="k">LON</span><span class="v">' + parseFloat(aoi.longitude).toFixed(5) + '°</span></div>';
    html += '<div class="kv full"><span class="k">RADIUS</span><span class="v">' + Number(aoi.radius).toLocaleString() + ' m</span></div>';
    html += '</div>';

    card.innerHTML = html;

    if (isExclusion) {
      exContainer.appendChild(card);
    } else {
      aoiContainer.appendChild(card);
    }
  }

  document.getElementById("aoi-count-pill").textContent = aoiCount;
  document.getElementById("ex-count-pill").textContent = exCount;
  wireAoiCardActions();
}

function wireAoiCardActions() {
  document.querySelectorAll('[data-action="delete-aoi"]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      deleteAoi(parseInt(btn.getAttribute('data-uid')));
    });
  });
  document.querySelectorAll('[data-action="purge"]').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var uid = parseInt(btn.getAttribute('data-uid'));
      if (confirm("Purge all intersections inside this exclusion area?\nThis cannot be undone!")) {
        purgeAoi(uid);
      }
    });
  });
}

function loadAoi(action) {
  updateAoi(action, null);
}
