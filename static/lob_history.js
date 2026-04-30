var HIGHLIGHT_GAP_THRESHOLD_MS = 10000;
var highlightRanges = [];

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
}

function clearTimelineHighlights() {
  if (highlightRanges.length === 0) return;
  var allRanges = viewer.timeline._highlightRanges;
  for (var i = 0; i < highlightRanges.length; i++) {
    var idx = allRanges.indexOf(highlightRanges[i]);
    if (idx !== -1) {
      allRanges.splice(idx, 1);
    }
  }
  highlightRanges = [];
  viewer.timeline.updateFromClock();
}

var isHistoryMode = false;

var lobHistoryEn = document.getElementById("lob_history_en");
lobHistoryEn.onchange = function() {
  if (lobHistoryEn.checked) {
    fetch("/update?lob_history=true");
  } else {
    fetch("/update?lob_history=false");
  }
};

var presetButtons = document.querySelectorAll(".history-card-btn[data-minutes]");
presetButtons.forEach(function(btn) {
  btn.addEventListener("click", function() {
    var minutes = parseInt(btn.getAttribute("data-minutes"));
    var now = new Date();
    var start = new Date(now.getTime() - minutes * 60000);
    document.getElementById("history_start").value = toLocalISOString(start);
    document.getElementById("history_end").value = toLocalISOString(now);
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

document.getElementById("loadHistoryBtn").addEventListener("click", function() {
  var startInput = document.getElementById("history_start").value;
  var endInput = document.getElementById("history_end").value;

  if (!startInput || !endInput) {
    alert("Please select a time range.");
    return;
  }

  var startMs = new Date(startInput).getTime();
  var endMs = new Date(endInput).getTime();
  var mode = document.querySelector('input[name="history_mode"]:checked').value;
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

document.getElementById("liveBtn").addEventListener("click", function() {
  exitHistoryMode();
});

function enterHistoryMode() {
  isHistoryMode = true;
  clearInterval(autoRefresh);
  document.querySelector(".cesium-viewer-animationContainer").classList.add("history-visible");
  document.querySelector(".cesium-viewer-timelineContainer").classList.add("history-visible");
  document.getElementById("liveBtn").style.display = "inline-block";
  document.getElementById("loadHistoryBtn").value = "Reload History";
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

  document.getElementById("liveBtn").style.display = "none";
  document.getElementById("loadHistoryBtn").value = "Load History";
}
