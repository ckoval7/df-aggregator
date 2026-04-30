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
  document.getElementById("liveBtn").style.display = "inline-block";
  document.getElementById("loadHistoryBtn").value = "Reload History";
}

function exitHistoryMode() {
  isHistoryMode = false;
  viewer.dataSources.remove(lobHistoryDataSource, true);
  lobHistoryDataSource = new Cesium.CzmlDataSource();

  viewer.clock.clockStep = Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER;
  viewer.clock.currentTime = Cesium.JulianDate.now();
  viewer.clock.shouldAnimate = true;

  autoRefresh = setInterval(function() { reloadRX(); }, refreshrate);
  reloadRX();

  document.getElementById("liveBtn").style.display = "none";
  document.getElementById("loadHistoryBtn").value = "Load History";
}
