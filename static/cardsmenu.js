// Receiver add form
const addRxBtn = document.getElementById("add-rx-btn");
const newRxForm = document.getElementById("new-rx-form");
const newRxUrl = document.getElementById("new-rx-url");

addRxBtn.addEventListener("click", function() {
  newRxForm.classList.toggle("hidden");
  newRxUrl.value = "";
  if (!newRxForm.classList.contains("hidden")) {
    newRxUrl.focus();
  }
});

document.getElementById("save-new-rx").addEventListener("click", function() {
  const url = newRxUrl.value.trim();
  if (url) {
    makeNewRx(url);
  }
  newRxForm.classList.add("hidden");
});

document.getElementById("cancel-new-rx").addEventListener("click", function() {
  newRxForm.classList.add("hidden");
});

// AOI add form
const addAoiBtn = document.getElementById("add-aoi-btn");
const newAoiForm = document.getElementById("new-aoi-form");
const aoiLat = document.getElementById("aoi-new-lat");
const aoiLon = document.getElementById("aoi-new-lon");
const aoiRadius = document.getElementById("aoi-new-radius");

addAoiBtn.addEventListener("click", function() {
  if (!newAoiForm.classList.contains("hidden")) {
    newAoiForm.classList.add("hidden");
    clearHover();
    return;
  }
  clearHover();
  aoiLat.value = "";
  aoiLon.value = "";
  aoiRadius.value = "";
  newAoiForm.classList.remove("hidden");
  pickCenter(aoiLat, aoiLon, aoiRadius, Cesium.Color.CORNFLOWERBLUE);
});

document.getElementById("save-new-aoi").addEventListener("click", function() {
  if (aoiLat.value && aoiLon.value && aoiRadius.value) {
    makeNewAoi("aoi", aoiLat.value, aoiLon.value, aoiRadius.value);
  }
  newAoiForm.classList.add("hidden");
  clearHover();
});

document.getElementById("cancel-new-aoi").addEventListener("click", function() {
  newAoiForm.classList.add("hidden");
  clearHover();
});

// Exclusion add form
const addExBtn = document.getElementById("add-exclusion-btn");
const newExForm = document.getElementById("new-exclusion-form");
const exLat = document.getElementById("exclusion-new-lat");
const exLon = document.getElementById("exclusion-new-lon");
const exRadius = document.getElementById("exclusion-new-radius");

addExBtn.addEventListener("click", function() {
  if (!newExForm.classList.contains("hidden")) {
    newExForm.classList.add("hidden");
    clearHover();
    return;
  }
  clearHover();
  exLat.value = "";
  exLon.value = "";
  exRadius.value = "";
  newExForm.classList.remove("hidden");
  pickCenter(exLat, exLon, exRadius, Cesium.Color.ORANGE);
});

document.getElementById("save-new-exclusion").addEventListener("click", function() {
  if (exLat.value && exLon.value && exRadius.value) {
    makeNewAoi("exclusion", exLat.value, exLon.value, exRadius.value);
  }
  newExForm.classList.add("hidden");
  clearHover();
});

document.getElementById("cancel-new-exclusion").addEventListener("click", function() {
  newExForm.classList.add("hidden");
  clearHover();
});

// AOI Rules
document.getElementById("run-aoi-rules-btn").addEventListener("click", function() {
  const confirmed = confirm(
    "Did you define every AOI first?\n" +
    "You are about to delete every intersection outside of the currently defined AOIs. " +
    "This cannot be undone! When in doubt, backup your database."
  );
  if (confirmed) { runAoi(); }
});
