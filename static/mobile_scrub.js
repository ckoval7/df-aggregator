(function() {
  const track = document.getElementById('m-scrub-track');
  const timeLabel = document.getElementById('m-scrub-time');
  const startLabel = document.getElementById('m-scrub-start');
  const endLabel = document.getElementById('m-scrub-end');
  const scrubEl = document.getElementById('m-scrub');

  let startMs, endMs, totalSpan;
  let tickListener;
  let dragging = false;
  let wasAnimating = false;
  let head;


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
    const rect = track.getBoundingClientRect();
    if (isVertical()) {
      const raw = (touch.clientY - rect.top) / rect.height;
      return 1 - Math.max(0, Math.min(1, raw));
    } else {
      return Math.max(0, Math.min(1, (touch.clientX - rect.left) / rect.width));
    }
  }

  function positionHead(frac) {
    if (!head) return;
    if (isVertical()) {
      const pct = (1 - frac) * 100;
      head.style.top = pct + '%';
      head.style.left = '';
    } else {
      head.style.left = (frac * 100) + '%';
      head.style.top = '';
    }
  }

  function positionTimeLabel(frac) {
    if (isVertical()) {
      const pct = (1 - frac) * 100;
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

  function formatUTC(ms) {
    const d = new Date(ms);
    return String(d.getUTCHours()).padStart(2, '0') + ':' +
           String(d.getUTCMinutes()).padStart(2, '0') + ':' +
           String(d.getUTCSeconds()).padStart(2, '0');
  }

  function updateTimeText(ms) {
    timeLabel.textContent = formatUTC(ms) + ' UTC';
  }

  function updateBoundLabels() {
    startLabel.textContent = formatUTC(startMs);
    endLabel.textContent = formatUTC(endMs);
  }

  function setClockTime(frac) {
    const ms = fractionToTime(frac);
    const jd = Cesium.JulianDate.fromDate(new Date(ms));
    viewer.clock.currentTime = jd;
    updateTimeText(ms);
    positionHead(frac);
    positionTimeLabel(frac);
  }

  function onTick() {
    if (dragging) return;
    const now = Cesium.JulianDate.toDate(viewer.clock.currentTime).getTime();
    const frac = timeToFraction(now);
    positionHead(frac);
    positionTimeLabel(frac);
    updateTimeText(now);
  }

  function renderHighlights(merged) {
    for (let i = 0; i < merged.length; i++) {
      const fracStart = timeToFraction(merged[i][0]);
      const fracEnd = timeToFraction(merged[i][1]);
      const el = document.createElement('div');
      el.className = 'm-scrub-hl';

      if (isVertical()) {
        const topPct = (1 - fracEnd) * 100;
        const heightPct = (fracEnd - fracStart) * 100;
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
    const frac = touchToFraction(e.touches[0]);
    setClockTime(frac);
  }

  function onTouchMove(e) {
    if (!dragging) return;
    e.preventDefault();
    const frac = touchToFraction(e.touches[0]);
    setClockTime(frac);
  }

  function onTouchEnd(e) {
    if (!dragging) return;
    dragging = false;
    if (wasAnimating) {
      viewer.clock.shouldAnimate = true;
    }
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

  const orientationMq = globalThis.matchMedia('(orientation: portrait)');
  orientationMq.addEventListener('change', onOrientationChange);

  let currentMerged = [];


  globalThis.mScrub = {
    show: function(start, end, merged) {
      startMs = start;
      endMs = end;
      totalSpan = endMs - startMs;
      currentMerged = merged;

      clearTrack();
      scrubEl.classList.add('active');

      head = document.createElement('div');
      head.className = 'm-scrub-head';
      track.appendChild(head);

      renderHighlights(merged);
      updateBoundLabels();

      const now = Cesium.JulianDate.toDate(viewer.clock.currentTime).getTime();
      const frac = timeToFraction(now);
      positionHead(frac);
      positionTimeLabel(frac);
      updateTimeText(now);

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
