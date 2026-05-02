(function() {
  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  var mTopbar = document.getElementById('m-topbar');
  var mTopbarRow = document.getElementById('m-topbar-row');
  var mBurger = document.getElementById('m-burger');
  var mScrim = document.getElementById('m-scrim');
  var mDrawer = document.getElementById('m-drawer');
  var mDrawerClose = document.getElementById('m-drawer-close');
  var mSheetScrim = document.getElementById('m-sheet-scrim');
  var mSheet = document.getElementById('m-sheet');
  var mSheetClose = document.getElementById('m-sheet-close');
  var mScrubdock = document.getElementById('m-scrubdock');

  var mTopExpanded = false;

  // ── Status strip expand / collapse ──
  mTopbarRow.addEventListener('click', function(e) {
    if (e.target.closest('#m-burger')) return;
    mTopExpanded = !mTopExpanded;
    mTopbar.classList.toggle('expanded', mTopExpanded);
  });

  // ── Drawer ──
  function openDrawer(tab) {
    mScrim.classList.add('open');
    mDrawer.classList.add('open');
    document.body.style.overflow = 'hidden';
    if (tab) switchTab(tab);
  }
  function closeDrawer() {
    mScrim.classList.remove('open');
    mDrawer.classList.remove('open');
    document.body.style.overflow = '';
  }

  mBurger.addEventListener('click', function(e) {
    e.stopPropagation();
    openDrawer();
  });
  mScrim.addEventListener('click', closeDrawer);
  mDrawerClose.addEventListener('click', closeDrawer);

  // ── Tabs ──
  var tabButtons = mDrawer.querySelectorAll('.m-drawer-tab');
  var tabPanes = mDrawer.querySelectorAll('.m-tab-pane');

  function switchTab(key) {
    tabButtons.forEach(function(btn) {
      btn.classList.toggle('active', btn.getAttribute('data-tab') === key);
    });
    tabPanes.forEach(function(pane) {
      pane.classList.toggle('active', pane.id === 'm-pane-' + key);
    });
  }

  tabButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      switchTab(btn.getAttribute('data-tab'));
    });
  });

  // ── Bottom sheet ──
  function openSheet() {
    mSheetScrim.classList.add('open');
    mSheet.classList.add('open');
    syncSheetInputs();
  }
  function closeSheet() {
    mSheetScrim.classList.remove('open');
    mSheet.classList.remove('open');
  }

  document.getElementById('m-edit-range-btn').addEventListener('click', openSheet);
  mSheetScrim.addEventListener('click', closeSheet);
  mSheetClose.addEventListener('click', closeSheet);

  // ── Scrub dock edit → drawer + sheet ──
  document.getElementById('m-scrub-edit').addEventListener('click', function() {
    openDrawer('history');
    setTimeout(openSheet, 200);
  });

  // ── Sync sheet datetime inputs with desktop inputs ──
  function syncSheetInputs() {
    var dStart = document.getElementById('history_start');
    var dEnd = document.getElementById('history_end');
    var mStart = document.getElementById('m-history-start');
    var mEnd = document.getElementById('m-history-end');
    if (dStart && mStart) mStart.value = dStart.value;
    if (dEnd && mEnd) mEnd.value = dEnd.value;
  }

  // ── Filters tab wiring ──
  function mWireToggle(mId, desktopId, onChange) {
    var mEl = document.getElementById(mId);
    var dEl = document.getElementById(desktopId);
    mEl.addEventListener('click', function() {
      mEl.classList.toggle('on');
      var isOn = mEl.classList.contains('on');
      if (dEl) {
        if (isOn && !dEl.classList.contains('on')) dEl.classList.add('on');
        else if (!isOn && dEl.classList.contains('on')) dEl.classList.remove('on');
      }
      if (onChange) onChange(isOn);
      if (typeof saveFilters === 'function') saveFilters();
    });
  }

  mWireToggle('m-rx-en-toggle', 'rx-en-toggle', function(on) {
    updateParams('rx=' + (on ? 'true' : 'false'));
  });
  mWireToggle('m-clustering-toggle', 'clustering-toggle', function() {
    updateParams('');
  });
  mWireToggle('m-intersect-toggle', 'intersect-toggle', function() {
    updateParams('');
  });
  mWireToggle('m-lob-history-toggle', 'lob-history-toggle', function(on) {
    fetch('/update?lob_history=' + (on ? 'true' : 'false'));
    var recPill = document.getElementById('rec-pill');
    if (recPill) recPill.style.display = on ? '' : 'none';
  });

  // Slider wiring
  function mWireSlider(mSliderId, mValId, desktopSliderId, desktopValId, autoAt0, paramBuilder) {
    var mSlider = document.getElementById(mSliderId);
    var mVal = document.getElementById(mValId);
    var dSlider = document.getElementById(desktopSliderId);
    var dVal = document.getElementById(desktopValId);

    mSlider.addEventListener('input', function() {
      var v = mSlider.value;
      if (autoAt0 && parseFloat(v) === 0) {
        mVal.textContent = 'AUTO';
        mVal.className = 'm-filt-val auto';
      } else {
        mVal.textContent = v;
        mVal.className = 'm-filt-val';
      }
      if (dSlider) dSlider.value = v;
      if (dVal) {
        if (autoAt0 && parseFloat(v) === 0) {
          dVal.textContent = 'AUTO';
          dVal.className = 'filt-val filt-val-auto';
        } else {
          dVal.textContent = v;
          dVal.className = 'filt-val';
        }
      }
    });

    mSlider.addEventListener('pointerup', function() {
      if (paramBuilder) {
        updateParams(paramBuilder(mSlider.value));
      } else {
        updateParams('');
      }
      if (typeof saveFilters === 'function') saveFilters();
    });
  }

  mWireSlider('m-powerRange', 'm-power-val', 'powerRange', 'power-val', false, function(v) { return 'minpower=' + v; });
  mWireSlider('m-confRange', 'm-conf-val', 'confRange', 'conf-val', false, function(v) { return 'minconf=' + v; });
  mWireSlider('m-epsilonRange', 'm-eps-val', 'epsilonRange', 'eps-val', true, null);
  mWireSlider('m-minpointRange', 'm-minpoint-val', 'minpointRange', 'minpoint-val', true, null);

  // Apply & Refresh
  document.getElementById('m-refresh-btn').addEventListener('click', function() {
    updateParams('');
  });

  // ── History tab wiring ──
  var mTimePresets = document.getElementById('m-time-presets');
  mTimePresets.querySelectorAll('button').forEach(function(btn) {
    btn.addEventListener('click', function() {
      mTimePresets.querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var minutes = parseInt(btn.getAttribute('data-minutes'));
      var now = new Date();
      var start = new Date(now.getTime() - minutes * 60000);
      document.getElementById('history_start').value = toLocalISOString(start);
      document.getElementById('history_end').value = toLocalISOString(now);
      mUpdateWindowDisplay();
      // Sync desktop presets
      var dPresets = document.getElementById('time-presets');
      if (dPresets) {
        dPresets.querySelectorAll('.seg-btn').forEach(function(b) { b.classList.remove('active'); });
        var matching = dPresets.querySelector('[data-minutes="' + minutes + '"]');
        if (matching) matching.classList.add('active');
      }
    });
  });

  var mModeGroup = document.getElementById('m-mode-group');
  mModeGroup.querySelectorAll('button').forEach(function(btn) {
    btn.addEventListener('click', function() {
      mModeGroup.querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      // Sync desktop mode
      var dModeGroup = document.getElementById('history-mode-group');
      if (dModeGroup) {
        dModeGroup.querySelectorAll('.seg-btn').forEach(function(b) { b.classList.remove('active'); });
        var matching = dModeGroup.querySelector('[data-mode="' + btn.getAttribute('data-mode') + '"]');
        if (matching) matching.classList.add('active');
      }
    });
  });

  // LIVE / GO LIVE
  var mLiveBtn = document.getElementById('m-live-btn');
  mLiveBtn.addEventListener('click', function() {
    if (typeof isHistoryMode !== 'undefined' && isHistoryMode) {
      exitHistoryMode();
      mSetLiveState(true);
    } else {
      mSetLiveState(false);
    }
  });

  function mSetLiveState(isLive) {
    if (isLive) {
      mLiveBtn.className = 'm-bigbtn ghost';
      mLiveBtn.textContent = 'GO LIVE';
      mScrubdock.classList.remove('visible');
      mUpdateModePill(true);
    } else {
      mLiveBtn.className = 'm-bigbtn live';
      mLiveBtn.innerHTML = '<span class="m-rec-dot" style="width:6px;height:6px;border-radius:50%;background:currentColor;animation:pulse 1.4s infinite"></span> LIVE';
      mScrubdock.classList.add('visible');
      mUpdateModePill(false);
    }
  }

  // ── Load History (sheet) ──
  document.getElementById('m-load-history-btn').addEventListener('click', function() {
    var startVal = document.getElementById('m-history-start').value;
    var endVal = document.getElementById('m-history-end').value;
    if (!startVal || !endVal) return;

    // Sync to desktop inputs
    document.getElementById('history_start').value = startVal;
    document.getElementById('history_end').value = endVal;
    var mFreq = document.getElementById('m-history-freq').value;
    if (mFreq) document.getElementById('history_frequency').value = mFreq;

    closeSheet();

    var startMs = new Date(startVal).getTime();
    var endMs = new Date(endVal).getTime();
    var activeMode = mModeGroup.querySelector('button.active');
    var mode = activeMode ? activeMode.getAttribute('data-mode') : 'flash';
    var params = 'start=' + startMs + '&end=' + endMs + '&mode=' + mode;
    if (mFreq) params += '&frequency=' + mFreq;

    var spinner = document.getElementById('loader');
    spinner.style.visibility = 'visible';
    spinner.style.zIndex = '10';

    if (typeof isHistoryMode !== 'undefined' && isHistoryMode) {
      viewer.dataSources.remove(lobHistoryDataSource);
    }
    lobHistoryDataSource = new Cesium.CzmlDataSource();

    lobHistoryDataSource.load('/lob_history.czml?' + params).then(function() {
      viewer.dataSources.add(lobHistoryDataSource);
      enterHistoryMode();
      mSetLiveState(false);
      renderTimelineHighlights(lobHistoryDataSource);
      mUpdateScrubDock();
      spinner.style.visibility = 'hidden';
      spinner.style.zIndex = '0';
    }).catch(function(error) {
      console.error('Error loading LOB history:', error);
      spinner.style.visibility = 'hidden';
      spinner.style.zIndex = '0';
    });
  });

  function mUpdateWindowDisplay() {
    var startEl = document.getElementById('history_start');
    var endEl = document.getElementById('history_end');
    var fromEl = document.getElementById('m-window-from');
    var toEl = document.getElementById('m-window-to');
    fromEl.textContent = startEl.value ? startEl.value.replace('T', ' ') : '—';
    toEl.textContent = endEl.value ? endEl.value.replace('T', ' ') : '—';
  }

  // ── Scrub dock ──
  function mUpdateScrubDock() {
    var startVal = document.getElementById('history_start').value;
    var endVal = document.getElementById('history_end').value;
    if (!startVal || !endVal) return;

    var startDate = new Date(startVal);
    var endDate = new Date(endVal);
    var fmt = function(d) {
      return String(d.getUTCHours()).padStart(2, '0') + ':' + String(d.getUTCMinutes()).padStart(2, '0');
    };
    document.getElementById('m-scrub-time').textContent = fmt(startDate) + ' → ' + fmt(endDate) + ' UTC';

    mRenderScrubHighlights();
  }

  function mRenderScrubHighlights() {
    var track = document.getElementById('m-scrub-track');
    var axis = document.getElementById('m-scrub-axis');
    track.querySelectorAll('.m-scrub-hl, .m-scrub-head').forEach(function(e) { e.remove(); });
    axis.innerHTML = '';

    if (typeof lobHistoryDataSource === 'undefined') return;
    var intervals = extractIntervals(lobHistoryDataSource);
    var merged = mergeIntervals(intervals);
    if (merged.length === 0) return;

    var startVal = document.getElementById('history_start').value;
    var endVal = document.getElementById('history_end').value;
    var startMs = startVal ? new Date(startVal).getTime() : merged[0][0];
    var endMs = endVal ? new Date(endVal).getTime() : merged[merged.length - 1][1];
    var totalSpan = endMs - startMs;
    if (totalSpan <= 0) return;

    for (var i = 0; i < merged.length; i++) {
      var leftPct = ((merged[i][0] - startMs) / totalSpan) * 100;
      var widthPct = ((merged[i][1] - merged[i][0]) / totalSpan) * 100;
      var el = document.createElement('div');
      el.className = 'm-scrub-hl';
      el.style.left = Math.max(0, leftPct) + '%';
      el.style.width = Math.min(widthPct, 100 - leftPct) + '%';
      track.appendChild(el);
    }

    var nowMs = Date.now();
    if (nowMs >= startMs && nowMs <= endMs) {
      var headPct = ((nowMs - startMs) / totalSpan) * 100;
      var head = document.createElement('div');
      head.className = 'm-scrub-head';
      head.style.left = headPct + '%';
      track.appendChild(head);
    }

    for (var t = 0; t < 4; t++) {
      var tickMs = startMs + (totalSpan * t / 3);
      var d = new Date(tickMs);
      var label = document.createElement('span');
      label.textContent = String(d.getUTCHours()).padStart(2, '0') + ':' + String(d.getUTCMinutes()).padStart(2, '0');
      axis.appendChild(label);
    }
  }

  // ── Mobile stats updates ──
  function mUpdateModePill(isLive) {
    var pill = document.getElementById('m-mode-pill');
    var meterMode = document.getElementById('m-meter-mode');
    if (isLive) {
      pill.className = 'm-mode live';
      pill.innerHTML = '<span class="m-rec-dot"></span>LIVE';
      meterMode.textContent = 'LIVE capture';
    } else {
      pill.className = 'm-mode history';
      pill.innerHTML = '<span class="m-rec-dot"></span>HIST';
      meterMode.textContent = 'HISTORY';
    }
  }

  // Expose update functions so desktop JS can call them after data loads
  window.mobileUI = {
    updateReceiverStats: function(rxJson) {
      var receivers = rxJson.receivers;
      var total = Object.keys(receivers).length;
      var online = 0;
      var freqs = {};
      for (var i = 0; i < total; i++) {
        if (receivers[i].active) {
          online++;
          freqs[receivers[i].frequency] = true;
        }
      }

      // Strip cells
      document.getElementById('m-stat-rx').innerHTML = online + '<span style="color:var(--fg-3)">/' + total + '</span>';

      var uniqueFreqs = Object.keys(freqs);
      var freqEl = document.getElementById('m-stat-freq');
      if (uniqueFreqs.length === 0) {
        freqEl.textContent = '—';
        freqEl.style.color = '';
      } else if (uniqueFreqs.length === 1) {
        freqEl.textContent = parseFloat(uniqueFreqs[0]).toFixed(1);
        freqEl.style.color = 'var(--accent)';
      } else {
        freqEl.textContent = 'MIXED';
        freqEl.style.color = 'var(--warn)';
      }

      // Expanded meters
      document.getElementById('m-meter-rx').innerHTML = '<span class="m-dot m-dot-good" style="display:inline-block;margin-right:6px"></span>' + online + ' <span class="unit">/ ' + total + ' online</span>';

      var mFreqMeter = document.getElementById('m-meter-freq');
      if (uniqueFreqs.length === 0) {
        mFreqMeter.innerHTML = '— <span class="unit">no active rx</span>';
      } else if (uniqueFreqs.length === 1) {
        mFreqMeter.innerHTML = parseFloat(uniqueFreqs[0]).toFixed(1) + ' <span class="unit">MHz</span>';
        mFreqMeter.style.color = 'var(--accent)';
      } else {
        mFreqMeter.innerHTML = 'MIXED <span class="unit">' + uniqueFreqs.length + ' freqs</span>';
        mFreqMeter.style.color = 'var(--warn)';
      }

      // Tab count
      document.getElementById('m-tab-rx-count').textContent = total;
      document.getElementById('m-rx-pill').textContent = total;

      // Build mobile receiver cards
      mBuildReceiverCards(rxJson);
    },

    updateAoiStats: function(aoiJson) {
      var aois = aoiJson.aois;
      var aoiCount = 0;
      var exCount = 0;
      for (var i = 0; i < aois.length; i++) {
        if (aois[i].aoi_type === 'exclusion') exCount++;
        else aoiCount++;
      }
      document.getElementById('m-meter-aoi').innerHTML = aoiCount + ' <span class="unit">aoi</span> · ' + exCount + ' <span class="unit">excl</span>';
      document.getElementById('m-tab-aoi-count').textContent = aoiCount + exCount;
      document.getElementById('m-aoi-pill').textContent = aoiCount;
      document.getElementById('m-ex-pill').textContent = exCount;

      mBuildAoiCards(aoiJson);
    },

    updatePipelineStats: function(data) {
      var fmt = function(n) { return n == null ? '—' : n.toLocaleString(); };
      var dbInt = data.db_intersections || 0;
      document.getElementById('m-pipe-intersects').textContent = fmt(dbInt);

      var inclusterWrap = document.getElementById('m-pipe-incluster-wrap');
      var clustersWrap = document.getElementById('m-pipe-clusters-wrap');
      var arrow1 = document.getElementById('m-pipe-arrow-1');
      var arrow2 = document.getElementById('m-pipe-arrow-2');
      var warnEl = document.getElementById('m-pipe-warn');
      var warnText = document.getElementById('m-pipe-warn-text');
      var clustEl = document.getElementById('m-stat-clust');

      if (!data.clustering_enabled) {
        inclusterWrap.style.display = 'none';
        clustersWrap.style.display = 'none';
        arrow1.style.display = 'none';
        arrow2.style.display = 'none';
        clustEl.textContent = '—';
        if (dbInt === 0) {
          warnText.textContent = 'No intersections in time window';
          warnEl.classList.remove('hidden');
        } else {
          warnEl.classList.add('hidden');
        }
        return;
      }

      inclusterWrap.style.display = '';
      clustersWrap.style.display = '';
      arrow1.style.display = '';
      arrow2.style.display = '';

      var totals = data.totals || {};
      var inCluster = totals.in_cluster || 0;
      var clusters = totals.clusters || 0;

      document.getElementById('m-pipe-incluster').textContent = fmt(inCluster);
      document.getElementById('m-pipe-clusters').textContent = fmt(clusters);
      clustEl.textContent = fmt(clusters);
      clustEl.style.color = clusters === 0 ? 'var(--warn)' : 'var(--accent)';

      if (clusters > 0) {
        clustersWrap.className = 'm-pipe-step accent';
      } else {
        clustersWrap.className = 'm-pipe-step warn';
      }
      if (inCluster === 0 && dbInt > 0) {
        inclusterWrap.className = 'm-pipe-step warn';
      } else {
        inclusterWrap.className = 'm-pipe-step';
      }

      var warn = '';
      if (dbInt === 0) {
        warn = 'No intersections in time window';
      }
      if (warn) {
        warnText.textContent = warn;
        warnEl.classList.remove('hidden');
      } else {
        warnEl.classList.add('hidden');
      }
    },

    setMode: function(isLive) {
      mUpdateModePill(isLive);
      mSetLiveState(isLive);
    }
  };

  // ── Build mobile receiver cards ──
  function mBuildReceiverCards(rxJson) {
    var container = document.getElementById('m-rx-cards');
    container.innerHTML = '';
    var receivers = rxJson.receivers;
    var total = Object.keys(receivers).length;

    for (var i = 0; i < total; i++) {
      var rx = receivers[i];
      var card = document.createElement('div');
      card.className = 'm-card';

      var html = '<div class="m-rxhead">';
      html += '<span class="m-dot ' + (rx.active ? 'm-dot-good' : 'm-dot-bad') + '"></span>';
      html += '<span class="m-rxid">' + esc(rx.station_id) + '</span>';
      html += '<span class="m-rxpill ' + (rx.active ? 'on' : 'off') + '">' + (rx.active ? 'ONLINE' : 'OFFLINE') + '</span>';
      html += '<span class="m-rx-toggle ' + (rx.active ? 'on' : '') + '" data-uid="' + rx.uid + '"><span class="m-rx-thumb"></span></span>';
      html += '</div>';

      html += '<div class="m-kvgrid">';
      html += '<div class="m-kv"><span class="m-k">LAT</span><span class="m-v">' + parseFloat(rx.latitude).toFixed(5) + '°</span></div>';
      html += '<div class="m-kv"><span class="m-k">LON</span><span class="m-v">' + parseFloat(rx.longitude).toFixed(5) + '°</span></div>';
      html += '<div class="m-kv"><span class="m-k">HDG</span><span class="m-v">' + rx.heading + '°</span></div>';
      html += '<div class="m-kv"><span class="m-k">FREQ</span><span class="m-v accent">' + rx.frequency + ' MHz</span></div>';
      html += '</div>';

      if (rx.active) {
        var sig = rx.signal || 0;
        var conf = rx.conf || 0;
        html += '<div class="m-meterbar">';
        html += '<div class="m-mlbl">SIG</div>';
        html += '<div class="m-mtrack"><div class="m-mfill" style="width:' + sig + '%"></div></div>';
        html += '<div class="m-mval">' + sig + '</div>';
        html += '</div>';
        html += '<div class="m-meterbar">';
        html += '<div class="m-mlbl">CONF</div>';
        html += '<div class="m-mtrack"><div class="m-mfill alt" style="width:' + Math.min(conf, 100) + '%"></div></div>';
        html += '<div class="m-mval">' + conf + '</div>';
        html += '</div>';
      }

      card.innerHTML = html;
      container.appendChild(card);
    }

    // Wire toggles
    container.querySelectorAll('.m-rx-toggle').forEach(function(toggle) {
      toggle.addEventListener('click', function() {
        var uid = parseInt(toggle.getAttribute('data-uid'));
        var isCurrentlyOn = toggle.classList.contains('on');
        activateReceiver(uid, !isCurrentlyOn);
      });
    });
  }

  // ── Build mobile AOI cards ──
  function mBuildAoiCards(aoiJson) {
    var aoiContainer = document.getElementById('m-aoi-cards');
    var exContainer = document.getElementById('m-exclusion-cards');
    aoiContainer.innerHTML = '';
    exContainer.innerHTML = '';

    var aois = aoiJson.aois;
    for (var i = 0; i < aois.length; i++) {
      var aoi = aois[i];
      var isExclusion = aoi.aoi_type === 'exclusion';
      var kind = isExclusion ? 'exclusion' : 'aoi';
      var dotClass = isExclusion ? 'm-dot-warn' : 'm-dot-acc';

      var card = document.createElement('div');
      card.className = 'm-card ' + kind;

      var html = '<div class="m-aoi-head">';
      html += '<span class="m-dot ' + dotClass + '"></span>';
      html += '<span class="m-aoi-label">' + esc(aoi.label || kind.toUpperCase() + '-' + aoi.uid) + '</span>';
      html += '<button class="m-remove-btn" data-uid="' + aoi.uid + '">Remove</button>';
      html += '</div>';
      html += '<div class="m-kvgrid">';
      html += '<div class="m-kv"><span class="m-k">LAT</span><span class="m-v">' + parseFloat(aoi.latitude).toFixed(4) + '°</span></div>';
      html += '<div class="m-kv"><span class="m-k">LON</span><span class="m-v">' + parseFloat(aoi.longitude).toFixed(4) + '°</span></div>';
      html += '<div class="m-kv" style="grid-column:1/-1"><span class="m-k">RAD</span><span class="m-v">' + Number(aoi.radius).toLocaleString() + ' m</span></div>';
      html += '</div>';

      card.innerHTML = html;
      (isExclusion ? exContainer : aoiContainer).appendChild(card);
    }

    // Wire remove buttons
    document.querySelectorAll('#m-aoi-cards .m-remove-btn, #m-exclusion-cards .m-remove-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        deleteAoi(parseInt(btn.getAttribute('data-uid')));
      });
    });
  }

  // ── Mobile add buttons ──
  document.getElementById('m-add-rx-btn').addEventListener('click', function() {
    var url = prompt('Enter receiver URL (e.g. http://receiver:8081/doa):');
    if (url && url.trim()) {
      makeNewRx(url.trim());
    }
  });

  document.getElementById('m-add-aoi-btn').addEventListener('click', function() {
    closeDrawer();
    var lat = document.getElementById('aoi-new-lat');
    var lon = document.getElementById('aoi-new-lon');
    var rad = document.getElementById('aoi-new-radius');
    lat.value = '';
    lon.value = '';
    rad.value = '';
    pickCenter(lat, lon, rad, Cesium.Color.CORNFLOWERBLUE);
  });

  document.getElementById('m-add-exclusion-btn').addEventListener('click', function() {
    closeDrawer();
    var lat = document.getElementById('exclusion-new-lat');
    var lon = document.getElementById('exclusion-new-lon');
    var rad = document.getElementById('exclusion-new-radius');
    lat.value = '';
    lon.value = '';
    rad.value = '';
    pickCenter(lat, lon, rad, Cesium.Color.ORANGE);
  });

  // ── Init: set defaults ──
  mUpdateWindowDisplay();
})();
