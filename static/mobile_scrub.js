(function() {
  var track = document.getElementById('m-scrub-track');
  var timeLabel = document.getElementById('m-scrub-time');
  var playBtn = document.getElementById('m-scrub-play');
  var scrubEl = document.getElementById('m-scrub');

  var startMs, endMs, totalSpan;
  var tickListener;
  var dragging = false;
  var wasAnimating = false;
  var head;

  var pauseIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>';
  var playIcon = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6,4 20,12 6,20"/></svg>';

  function isVertical() {
    return track.clientHeight > track.clientWidth;
  }

  function fractionToTime(frac) {
    frac = Math.max(0, Math.min(1, frac));
    return startMs + frac * totalSpan;
  }

  function timeToFraction(ms) {
    if (totalSpan <= 0) return 0;
    return Math.max(0, Math.min(1, (ms - startMs) / totalSpan));
  }

  function touchToFraction(touch) {
    var rect = track.getBoundingClientRect();
    if (isVertical()) {
      var raw = (touch.clientY - rect.top) / rect.height;
      return 1 - Math.max(0, Math.min(1, raw));
    } else {
      return Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
    }
  }

  function positionHead(frac) {
    if (!head) return;
    if (isVertical()) {
      var pct = (1 - frac) * 100;
      head.style.top = pct + '%';
      head.style.left = '';
    } else {
      head.style.left = (frac * 100) + '%';
      head.style.top = '';
    }
  }

  function positionTimeLabel(frac) {
    if (isVertical()) {
      var pct = (1 - frac) * 100;
      timeLabel.style.top = pct + '%';
      timeLabel.style.transform = 'translateY(-50%)';
      timeLabel.style.left = '';
      timeLabel.style.bottom = '';
    } else {
      timeLabel.style.left = (frac * 100) + '%';
      timeLabel.style.transform = 'translateX(-50%)';
      timeLabel.style.top = '';
    }
  }

  function updateTimeText(ms) {
    var d = new Date(ms);
    var h = String(d.getUTCHours()).padStart(2, '0');
    var m = String(d.getUTCMinutes()).padStart(2, '0');
    var s = String(d.getUTCSeconds()).padStart(2, '0');
    timeLabel.textContent = h + ':' + m + ':' + s + ' UTC';
  }

  function setClockTime(frac) {
    var ms = fractionToTime(frac);
    var jd = Cesium.JulianDate.fromDate(new Date(ms));
    viewer.clock.currentTime = jd;
    updateTimeText(ms);
    positionHead(frac);
    positionTimeLabel(frac);
  }

  function onTick() {
    if (dragging) return;
    var now = Cesium.JulianDate.toDate(viewer.clock.currentTime).getTime();
    var frac = timeToFraction(now);
    positionHead(frac);
    positionTimeLabel(frac);
    updateTimeText(now);
  }

  function renderHighlights(merged) {
    for (var i = 0; i < merged.length; i++) {
      var fracStart = timeToFraction(merged[i][0]);
      var fracEnd = timeToFraction(merged[i][1]);
      var el = document.createElement('div');
      el.className = 'm-scrub-hl';

      if (isVertical()) {
        var topPct = (1 - fracEnd) * 100;
        var heightPct = (fracEnd - fracStart) * 100;
        el.style.top = topPct + '%';
        el.style.height = heightPct + '%';
      } else {
        el.style.left = (fracStart * 100) + '%';
        el.style.width = ((fracEnd - fracStart) * 100) + '%';
      }
      track.appendChild(el);
    }
  }

  function clearTrack() {
    track.querySelectorAll('.m-scrub-hl, .m-scrub-head').forEach(function(e) { e.remove(); });
    head = null;
  }

  function onTouchStart(e) {
    e.preventDefault();
    dragging = true;
    wasAnimating = viewer.clock.shouldAnimate;
    viewer.clock.shouldAnimate = false;
    var frac = touchToFraction(e.touches[0]);
    setClockTime(frac);
  }

  function onTouchMove(e) {
    if (!dragging) return;
    e.preventDefault();
    var frac = touchToFraction(e.touches[0]);
    setClockTime(frac);
  }

  function onTouchEnd(e) {
    if (!dragging) return;
    dragging = false;
    if (wasAnimating) {
      viewer.clock.shouldAnimate = true;
    }
    updatePlayBtn();
  }

  function updatePlayBtn() {
    playBtn.innerHTML = viewer.clock.shouldAnimate ? pauseIcon : playIcon;
  }

  function onOrientationChange() {
    if (!scrubEl.classList.contains('active')) return;
    clearTrack();
    head = document.createElement('div');
    head.className = 'm-scrub-head';
    track.appendChild(head);
    renderHighlights(currentMerged);
    onTick();
  }

  var orientationMq = window.matchMedia('(orientation: portrait)');
  orientationMq.addEventListener('change', onOrientationChange);

  var currentMerged = [];

  playBtn.addEventListener('click', function() {
    viewer.clock.shouldAnimate = !viewer.clock.shouldAnimate;
    updatePlayBtn();
  });

  window.mScrub = {
    show: function(start, end, merged) {
      startMs = start;
      endMs = end;
      totalSpan = endMs - startMs;
      currentMerged = merged;

      clearTrack();
      head = document.createElement('div');
      head.className = 'm-scrub-head';
      track.appendChild(head);

      renderHighlights(merged);
      scrubEl.classList.add('active');

      var now = Cesium.JulianDate.toDate(viewer.clock.currentTime).getTime();
      var frac = timeToFraction(now);
      positionHead(frac);
      positionTimeLabel(frac);
      updateTimeText(now);
      updatePlayBtn();

      tickListener = viewer.clock.onTick.addEventListener(onTick);

      scrubEl.addEventListener('touchstart', onTouchStart, { passive: false });
      scrubEl.addEventListener('touchmove', onTouchMove, { passive: false });
      scrubEl.addEventListener('touchend', onTouchEnd);
    },

    hide: function() {
      scrubEl.classList.remove('active');
      if (tickListener) {
        tickListener();
        tickListener = null;
      }
      clearTrack();
      currentMerged = [];
      dragging = false;

      scrubEl.removeEventListener('touchstart', onTouchStart);
      scrubEl.removeEventListener('touchmove', onTouchMove);
      scrubEl.removeEventListener('touchend', onTouchEnd);
    }
  };
})();
