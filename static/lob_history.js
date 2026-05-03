const HIGHLIGHT_GAP_THRESHOLD_MS = 10000;
let highlightRanges = [];
let isHistoryMode = false;

function extractIntervals(dataSource) {
  const intervals = [];
  const entities = dataSource.entities.values;
  for (let i = 0; i < entities.length; i++) {
    const entity = entities[i];
    if (entity.availability) {
      for (let j = 0; j < entity.availability.length; j++) {
        const interval = entity.availability.get(j);
        const startMs = Cesium.JulianDate.toDate(interval.start).getTime();
        const stopMs = Cesium.JulianDate.toDate(interval.stop).getTime();
        intervals.push([startMs, stopMs]);
      }
    }
  }
  intervals.sort(function(a, b) { return a[0] - b[0]; });
  return intervals;
}

function mergeIntervals(intervals) {
  if (intervals.length === 0) return [];
  const merged = [[intervals[0][0], intervals[0][1]]];
  for (let i = 1; i < intervals.length; i++) {
    const last = merged[merged.length - 1];
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
  const intervals = extractIntervals(dataSource);
  const merged = mergeIntervals(intervals);

  const color = Cesium.Color.GREEN.withAlpha(0.4);
  for (let i = 0; i < merged.length; i++) {
    const range = viewer.timeline.addHighlightRange(color, 5);
    range.setRange(
      Cesium.JulianDate.fromDate(new Date(merged[i][0])),
      Cesium.JulianDate.fromDate(new Date(merged[i][1]))
    );
    highlightRanges.push(range);
  }
  viewer.timeline.updateFromClock();

  renderScrubHighlights(merged);
  return merged;
}

function clearTimelineHighlights() {
  if (highlightRanges.length > 0) {
    const allRanges = viewer.timeline._highlightRanges;
    for (let i = 0; i < highlightRanges.length; i++) {
      const idx = allRanges.indexOf(highlightRanges[i]);
      if (idx !== -1) { allRanges.splice(idx, 1); }
    }
    highlightRanges = [];
    viewer.timeline.updateFromClock();
  }
  clearScrubHighlights();
}

function renderScrubHighlights(merged) {
  clearScrubHighlights();
  const track = document.getElementById("scrub-track");
  const axis = document.getElementById("scrub-axis");
  if (merged.length === 0) return;

  const startVal = document.getElementById("history_start").value;
  const endVal = document.getElementById("history_end").value;
  const startMs = startVal ? new Date(startVal).getTime() : merged[0][0];
  const endMs = endVal ? new Date(endVal).getTime() : merged[merged.length - 1][1];
  const totalSpan = endMs - startMs;
  if (totalSpan <= 0) return;

  for (let i = 0; i < merged.length; i++) {
    const leftPct = ((merged[i][0] - startMs) / totalSpan) * 100;
    const widthPct = ((merged[i][1] - merged[i][0]) / totalSpan) * 100;
    const el = document.createElement('div');
    el.className = 'scrub-highlight';
    el.style.left = Math.max(0, leftPct) + '%';
    el.style.width = Math.min(widthPct, 100 - leftPct) + '%';
    track.appendChild(el);
  }

  const nowMs = Date.now();
  if (nowMs >= startMs && nowMs <= endMs) {
    const headPct = ((nowMs - startMs) / totalSpan) * 100;
    const head = document.createElement('div');
    head.className = 'scrub-head';
    head.style.left = headPct + '%';
    track.appendChild(head);
  }

  axis.innerHTML = '';
  for (let t = 0; t < 4; t++) {
    const tickMs = startMs + (totalSpan * t / 3);
    const d = new Date(tickMs);
    const label = document.createElement('span');
    label.textContent = String(d.getUTCHours()).padStart(2, '0') + ':' + String(d.getUTCMinutes()).padStart(2, '0');
    axis.appendChild(label);
  }
}

function clearScrubHighlights() {
  const track = document.getElementById("scrub-track");
  track.querySelectorAll('.scrub-highlight, .scrub-head').forEach(function(e) { e.remove(); });
  document.getElementById("scrub-axis").innerHTML = '';
}

// Record History toggle
const lobHistoryToggle = document.getElementById("lob-history-toggle");
const recPill = document.getElementById("rec-pill");
lobHistoryToggle.addEventListener("click", function() {
  lobHistoryToggle.classList.toggle("on");
  const isOn = lobHistoryToggle.classList.contains("on");
  fetch("/update?lob_history=" + (isOn ? "true" : "false"));
  recPill.style.display = isOn ? "" : "none";
  if (typeof saveFilters === "function") saveFilters();
});
if (lobHistoryToggle.classList.contains("on")) {
  recPill.style.display = "";
}

// Time range presets
const presetGroup = document.getElementById("time-presets");
presetGroup.querySelectorAll('.seg-btn').forEach(function(btn) {
  btn.addEventListener("click", function() {
    presetGroup.querySelectorAll('.seg-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    const minutes = parseInt(btn.getAttribute("data-minutes"));
    const now = new Date();
    const start = new Date(now.getTime() - minutes * 60000);
    document.getElementById("history_start").value = toLocalISOString(start);
    document.getElementById("history_end").value = toLocalISOString(now);
  });
});

// Mode segmented control
const modeGroup = document.getElementById("history-mode-group");
modeGroup.querySelectorAll('.seg-btn').forEach(function(btn) {
  btn.addEventListener("click", function() {
    modeGroup.querySelectorAll('.seg-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
  });
});

function toLocalISOString(date) {
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60000);
  return local.toISOString().slice(0, 19);
}

(function setDefaults() {
  const now = new Date();
  const start = new Date(now.getTime() - 3600000);
  document.getElementById("history_start").value = toLocalISOString(start);
  document.getElementById("history_end").value = toLocalISOString(now);
})();

// Load History
document.getElementById("loadHistoryBtn").addEventListener("click", function() {
  const startInput = document.getElementById("history_start").value;
  const endInput = document.getElementById("history_end").value;

  if (!startInput || !endInput) {
    alert("Please select a time range.");
    return;
  }

  const startMs = new Date(startInput).getTime();
  const endMs = new Date(endInput).getTime();
  const activeMode = modeGroup.querySelector('.seg-btn.active');
  const mode = activeMode ? activeMode.getAttribute('data-mode') : 'flash';
  const freqInput = document.getElementById("history_frequency").value;

  let params = "start=" + startMs + "&end=" + endMs + "&mode=" + mode;
  if (freqInput) {
    params += "&frequency=" + freqInput;
  }

  const spinner = document.getElementById("loader");
  spinner.style.visibility = "visible";
  spinner.style.zIndex = "10";

  if (isHistoryMode) {
    viewer.dataSources.remove(lobHistoryDataSource);
  }
  window.lobHistoryDataSource = new Cesium.CzmlDataSource();

  lobHistoryDataSource.load("/lob_history.czml?" + params).then(function() {
    viewer.dataSources.add(lobHistoryDataSource);
    viewer.automaticallyTrackDataSourceClocks = false;
    viewer.clock.clockRange = Cesium.ClockRange.CLAMPED;
    enterHistoryMode();
    const merged = renderTimelineHighlights(lobHistoryDataSource);
    if (window.mScrub) mScrub.show(startMs, endMs, merged);
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
  const liveBtn = document.getElementById("liveBtn");
  liveBtn.style.display = "";
  liveBtn.className = "btn btn-live";
  liveBtn.innerHTML = '<span class="live-dot"></span>LIVE';
  document.getElementById("loadHistoryBtn").innerHTML =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Reload History';
  statusBar.setMode(false);
  if (window.mobileUI) mobileUI.setMode(false);
}

function exitHistoryMode() {
  clearTimelineHighlights();
  if (window.mScrub) mScrub.hide();
  isHistoryMode = false;
  viewer.dataSources.remove(lobHistoryDataSource);
  window.lobHistoryDataSource = new Cesium.CzmlDataSource();

  viewer.automaticallyTrackDataSourceClocks = true;
  viewer.clock.clockRange = Cesium.ClockRange.UNBOUNDED;
  viewer.clock.clockStep = Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER;
  viewer.clock.currentTime = Cesium.JulianDate.now();
  viewer.clock.shouldAnimate = true;

  document.querySelector(".cesium-viewer-animationContainer").classList.remove("history-visible");
  document.querySelector(".cesium-viewer-timelineContainer").classList.remove("history-visible");

  window.autoRefresh = setInterval(function() { reloadRX(); }, refreshrate);
  reloadRX();

  const liveBtn = document.getElementById("liveBtn");
  liveBtn.style.display = "none";
  liveBtn.className = "btn btn-ghost";
  liveBtn.innerHTML = '<span class="live-dot"></span>Go Live';

  document.getElementById("loadHistoryBtn").innerHTML =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> Load History';
  statusBar.setMode(true);
  if (window.mobileUI) mobileUI.setMode(true);
}
