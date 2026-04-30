var HIGHLIGHT_GAP_THRESHOLD_MS = 10000;
var highlightRanges = [];
var isHistoryMode = false;

function extractIntervals(dataSource) {
  var intervals = [];
  var entities = dataSource.entities.values;
  for (var i = 0; i < entities.length; i++) {
    var entity = entities[i];
    if (entity.availability) {
      for (var j = 0; j < entity.availability.length; j++) {
        var interval = entity.availability.get(j);
        var startMs = Cesium.JulianDate.toDate(interval.start).getTime();
        var stopMs = Cesium.JulianDate.toDate(interval.stop).getTime();
        intervals.push([startMs, stopMs]);
      }
    }
  }
  intervals.sort(function(a, b) { return a[0] - b[0]; });
  return intervals;
}

function mergeIntervals(intervals) {
  if (intervals.length === 0) return [];
  var merged = [[intervals[0][0], intervals[0][1]]];
  for (var i = 1; i < intervals.length; i++) {
    var last = merged[merged.length - 1];
    if (intervals[i][0] - last[1] <= HIGHLIGHT_GAP_THRESHOLD_MS) {
      last[1] = Math.max(last[1], intervals[i][1]);
    } else {
      merged.push([intervals[i][0], intervals[i][1]]);
    }
  }
  return merged;
}

function renderTimelineHighlights(dataSource) {
  clearTimelineHighlights();
  var intervals = extractIntervals(dataSource);
  var merged = mergeIntervals(intervals);

  var color = Cesium.Color.GREEN.withAlpha(0.4);
  for (var i = 0; i < merged.length; i++) {
    var range = viewer.timeline.addHighlightRange(color, 5);
    range.setRange(
      Cesium.JulianDate.fromDate(new Date(merged[i][0])),
      Cesium.JulianDate.fromDate(new Date(merged[i][1]))
    );
    highlightRanges.push(range);
  }
  viewer.timeline.updateFromClock();

  renderScrubHighlights(merged);
}

function clearTimelineHighlights() {
  if (highlightRanges.length > 0) {
    var allRanges = viewer.timeline._highlightRanges;
    for (var i = 0; i < highlightRanges.length; i++) {
      var idx = allRanges.indexOf(highlightRanges[i]);
      if (idx !== -1) { allRanges.splice(idx, 1); }
    }
    highlightRanges = [];
    viewer.timeline.updateFromClock();
  }
  clearScrubHighlights();
}

function renderScrubHighlights(merged) {
  clearScrubHighlights();
  var track = document.getElementById("scrub-track");
  var axis = document.getElementById("scrub-axis");
  if (merged.length === 0) return;

  var startVal = document.getElementById("history_start").value;
  var endVal = document.getElementById("history_end").value;
  var startMs = startVal ? new Date(startVal).getTime() : merged[0][0];
  var endMs = endVal ? new Date(endVal).getTime() : merged[merged.length - 1][1];
  var totalSpan = endMs - startMs;
  if (totalSpan <= 0) return;

  for (var i = 0; i < merged.length; i++) {
    var leftPct = ((merged[i][0] - startMs) / totalSpan) * 100;
    var widthPct = ((merged[i][1] - merged[i][0]) / totalSpan) * 100;
    var el = document.createElement('div');
    el.className = 'scrub-highlight';
    el.style.left = Math.max(0, leftPct) + '%';
    el.style.width = Math.min(widthPct, 100 - leftPct) + '%';
    track.appendChild(el);
  }

  var nowMs = Date.now();
  if (nowMs >= startMs && nowMs <= endMs) {
    var headPct = ((nowMs - startMs) / totalSpan) * 100;
    var head = document.createElement('div');
    head.className = 'scrub-head';
    head.style.left = headPct + '%';
    track.appendChild(head);
  }

  axis.innerHTML = '';
  for (var t = 0; t < 4; t++) {
    var tickMs = startMs + (totalSpan * t / 3);
    var d = new Date(tickMs);
    var label = document.createElement('span');
    label.textContent = String(d.getUTCHours()).padStart(2, '0') + ':' + String(d.getUTCMinutes()).padStart(2, '0');
    axis.appendChild(label);
  }
}

function clearScrubHighlights() {
  var track = document.getElementById("scrub-track");
  track.querySelectorAll('.scrub-highlight, .scrub-head').forEach(function(e) { e.remove(); });
  document.getElementById("scrub-axis").innerHTML = '';
}

// Record History toggle
var lobHistoryToggle = document.getElementById("lob-history-toggle");
var recPill = document.getElementById("rec-pill");
lobHistoryToggle.addEventListener("click", function() {
  lobHistoryToggle.classList.toggle("on");
  var isOn = lobHistoryToggle.classList.contains("on");
  fetch("/update?lob_history=" + (isOn ? "true" : "false"));
  recPill.style.display = isOn ? "" : "none";
});
if (lobHistoryToggle.classList.contains("on")) {
  recPill.style.display = "";
}

// Time range presets
var presetGroup = document.getElementById("time-presets");
presetGroup.querySelectorAll('.seg-btn').forEach(function(btn) {
  btn.addEventListener("click", function() {
    presetGroup.querySelectorAll('.seg-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    var minutes = parseInt(btn.getAttribute("data-minutes"));
    var now = new Date();
    var start = new Date(now.getTime() - minutes * 60000);
    document.getElementById("history_start").value = toLocalISOString(start);
    document.getElementById("history_end").value = toLocalISOString(now);
  });
});

// Mode segmented control
var modeGroup = document.getElementById("history-mode-group");
modeGroup.querySelectorAll('.seg-btn').forEach(function(btn) {
  btn.addEventListener("click", function() {
    modeGroup.querySelectorAll('.seg-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
  });
});

function toLocalISOString(date) {
  var offset = date.getTimezoneOffset();
  var local = new Date(date.getTime() - offset * 60000);
  return local.toISOString().slice(0, 19);
}

(function setDefaults() {
  var now = new Date();
  var start = new Date(now.getTime() - 3600000);
  document.getElementById("history_start").value = toLocalISOString(start);
  document.getElementById("history_end").value = toLocalISOString(now);
})();

// Load History
document.getElementById("loadHistoryBtn").addEventListener("click", function() {
  var startInput = document.getElementById("history_start").value;
  var endInput = document.getElementById("history_end").value;

  if (!startInput || !endInput) {
    alert("Please select a time range.");
    return;
  }

  var startMs = new Date(startInput).getTime();
  var endMs = new Date(endInput).getTime();
  var activeMode = modeGroup.querySelector('.seg-btn.active');
  var mode = activeMode ? activeMode.getAttribute('data-mode') : 'flash';
  var freqInput = document.getElementById("history_frequency").value;

  var params = "start=" + startMs + "&end=" + endMs + "&mode=" + mode;
  if (freqInput) {
    params += "&frequency=" + freqInput;
  }

  var spinner = document.getElementById("loader");
  spinner.style.visibility = "visible";
  spinner.style.zIndex = "10";

  if (isHistoryMode) {
    viewer.dataSources.remove(lobHistoryDataSource, true);
    lobHistoryDataSource = new Cesium.CzmlDataSource();
  }

  lobHistoryDataSource.load("/lob_history.czml?" + params).then(function() {
    viewer.dataSources.add(lobHistoryDataSource);
    enterHistoryMode();
    renderTimelineHighlights(lobHistoryDataSource);
    spinner.style.visibility = "hidden";
    spinner.style.zIndex = "0";
  }).catch(function(error) {
    console.error("Error loading LOB history:", error);
    spinner.style.visibility = "hidden";
    spinner.style.zIndex = "0";
  });
});

// Live button
document.getElementById("liveBtn").addEventListener("click", function() {
  exitHistoryMode();
});

function enterHistoryMode() {
  isHistoryMode = true;
  clearInterval(autoRefresh);
  document.querySelector(".cesium-viewer-animationContainer").classList.add("history-visible");
  document.querySelector(".cesium-viewer-timelineContainer").classList.add("history-visible");
  var liveBtn = document.getElementById("liveBtn");
  liveBtn.style.display = "";
  liveBtn.className = "btn btn-live";
  liveBtn.innerHTML = '<span class="live-dot"></span>LIVE';
  document.getElementById("loadHistoryBtn").innerHTML =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Reload History';
  statusBar.setMode(false);
}

function exitHistoryMode() {
  clearTimelineHighlights();
  isHistoryMode = false;
  viewer.dataSources.remove(lobHistoryDataSource, true);
  lobHistoryDataSource = new Cesium.CzmlDataSource();

  viewer.clock.clockStep = Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER;
  viewer.clock.currentTime = Cesium.JulianDate.now();
  viewer.clock.shouldAnimate = true;

  document.querySelector(".cesium-viewer-animationContainer").classList.remove("history-visible");
  document.querySelector(".cesium-viewer-timelineContainer").classList.remove("history-visible");

  autoRefresh = setInterval(function() { reloadRX(); }, refreshrate);
  reloadRX();

  var liveBtn = document.getElementById("liveBtn");
  liveBtn.style.display = "none";
  liveBtn.className = "btn btn-ghost";
  liveBtn.innerHTML = '<span class="live-dot"></span>Go Live';

  document.getElementById("loadHistoryBtn").innerHTML =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Load History';
  statusBar.setMode(true);
}
