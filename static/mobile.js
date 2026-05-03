(function() {
  function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function fmt(n) { return n == null ? '—' : n.toLocaleString(); }

  const mTopbar = document.getElementById('m-topbar');
  const mTopbarRow = document.getElementById('m-topbar-row');
  const mBurger = document.getElementById('m-burger');
  const mScrim = document.getElementById('m-scrim');
  const mDrawer = document.getElementById('m-drawer');
  const mDrawerClose = document.getElementById('m-drawer-close');
  const mSheetScrim = document.getElementById('m-sheet-scrim');
  const mSheet = document.getElementById('m-sheet');
  const mSheetClose = document.getElementById('m-sheet-close');


  let mTopExpanded = false;

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
  const tabButtons = mDrawer.querySelectorAll('.m-drawer-tab');
  const tabPanes = mDrawer.querySelectorAll('.m-tab-pane');

  function switchTab(key) {
    tabButtons.forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.tab === key);
    });
    tabPanes.forEach(function(pane) {
      pane.classList.toggle('active', pane.id === 'm-pane-' + key);
    });
  }

  tabButtons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      switchTab(btn.dataset.tab);
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

  // ── Sync sheet datetime inputs with desktop inputs ──
  function syncSheetInputs() {
    const dStart = document.getElementById('history_start');
    const dEnd = document.getElementById('history_end');
    const mStart = document.getElementById('m-history-start');
    const mEnd = document.getElementById('m-history-end');
    if (dStart && mStart) mStart.value = dStart.value;
    if (dEnd && mEnd) mEnd.value = dEnd.value;
  }

  // ── Filters tab wiring ──
  function mWireToggle(mId, desktopId, onChange) {
    const mEl = document.getElementById(mId);
    const dEl = document.getElementById(desktopId);
    mEl.addEventListener('click', function() {
      mEl.classList.toggle('on');
      const isOn = mEl.classList.contains('on');
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
    const recPill = document.getElementById('rec-pill');
    if (recPill) recPill.style.display = on ? '' : 'none';
  });

  // Slider wiring
  function mWireSlider(mSliderId, mValId, desktopSliderId, desktopValId, autoAt0, paramBuilder) {
    const mSlider = document.getElementById(mSliderId);
    const mVal = document.getElementById(mValId);
    const dSlider = document.getElementById(desktopSliderId);
    const dVal = document.getElementById(desktopValId);

    mSlider.addEventListener('input', function() {
      const v = mSlider.value;
      if (autoAt0 && Number.parseFloat(v) === 0) {
        mVal.textContent = 'AUTO';
        mVal.className = 'm-filt-val auto';
      } else {
        mVal.textContent = v;
        mVal.className = 'm-filt-val';
      }
      if (dSlider) dSlider.value = v;
      if (dVal) {
        if (autoAt0 && Number.parseFloat(v) === 0) {
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
  const mTimePresets = document.getElementById('m-time-presets');
  mTimePresets.querySelectorAll('button').forEach(function(btn) {
    btn.addEventListener('click', function() {
      mTimePresets.querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      const minutes = Number.parseInt(btn.dataset.minutes);
      const now = new Date();
      const start = new Date(now.getTime() - minutes * 60000);
      document.getElementById('history_start').value = toLocalISOString(start);
      document.getElementById('history_end').value = toLocalISOString(now);
      mUpdateWindowDisplay();
      // Sync desktop presets
      const dPresets = document.getElementById('time-presets');
      if (dPresets) {
        dPresets.querySelectorAll('.seg-btn').forEach(function(b) { b.classList.remove('active'); });
        const matching = dPresets.querySelector('[data-minutes="' + minutes + '"]');
        if (matching) matching.classList.add('active');
      }
    });
  });

  const mModeGroup = document.getElementById('m-mode-group');
  mModeGroup.querySelectorAll('button').forEach(function(btn) {
    btn.addEventListener('click', function() {
      mModeGroup.querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      // Sync desktop mode
      const dModeGroup = document.getElementById('history-mode-group');
      if (dModeGroup) {
        dModeGroup.querySelectorAll('.seg-btn').forEach(function(b) { b.classList.remove('active'); });
        const matching = dModeGroup.querySelector('[data-mode="' + btn.dataset.mode + '"]');
        if (matching) matching.classList.add('active');
      }
    });
  });

  // ── Go Live button — only active during history mode ──
  const mLiveBtn = document.getElementById('m-live-btn');
  mLiveBtn.addEventListener('click', function() {
    if (typeof isHistoryMode !== 'undefined' && isHistoryMode) {
      exitHistoryMode();
    }
  });

  const mLoadMainBtn = document.getElementById('m-load-history-main-btn');
  const clockIcon = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg> ';

  function mSetLiveState(isLive) {
    if (isLive) {
      mLiveBtn.style.display = 'none';
      mLoadMainBtn.innerHTML = clockIcon + 'Load History';
      mUpdateModePill(true);
    } else {
      mLiveBtn.style.display = '';
      mLoadMainBtn.innerHTML = clockIcon + 'Reload History';
      mUpdateModePill(false);
      mUpdateWindowDisplay();
    }
  }

  // ── Load History (main pane button) — presets already sync to desktop inputs ──
  document.getElementById('m-load-history-main-btn').addEventListener('click', function() {
    document.getElementById('loadHistoryBtn').click();
  });

  // ── Load History (sheet) — sync inputs to desktop and reuse desktop handler ──
  document.getElementById('m-load-history-btn').addEventListener('click', function() {
    const startVal = document.getElementById('m-history-start').value;
    const endVal = document.getElementById('m-history-end').value;
    if (!startVal || !endVal) return;

    document.getElementById('history_start').value = startVal;
    document.getElementById('history_end').value = endVal;
    const mFreq = document.getElementById('m-history-freq').value;
    document.getElementById('history_frequency').value = mFreq || '';

    closeSheet();
    document.getElementById('loadHistoryBtn').click();
  });

  function mUpdateWindowDisplay() {
    const startEl = document.getElementById('history_start');
    const endEl = document.getElementById('history_end');
    const fromEl = document.getElementById('m-window-from');
    const toEl = document.getElementById('m-window-to');
    fromEl.textContent = startEl.value ? startEl.value.replace('T', ' ') : '—';
    toEl.textContent = endEl.value ? endEl.value.replace('T', ' ') : '—';
  }

  // ── Mobile stats updates ──
  function mUpdateModePill(isLive) {
    const pill = document.getElementById('m-mode-pill');
    const meterMode = document.getElementById('m-meter-mode');
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
      const receivers = rxJson.receivers;
      const total = Object.keys(receivers).length;
      let online = 0;
      const freqs = {};
      for (let i = 0; i < total; i++) {
        if (receivers[i].active) {
          online++;
          freqs[receivers[i].frequency] = true;
        }
      }

      // Strip cells
      document.getElementById('m-stat-rx').innerHTML = online + '<span style="color:var(--fg-3)">/' + total + '</span>';

      const uniqueFreqs = Object.keys(freqs);
      const freqEl = document.getElementById('m-stat-freq');
      if (uniqueFreqs.length === 0) {
        freqEl.textContent = '—';
        freqEl.style.color = '';
      } else if (uniqueFreqs.length === 1) {
        freqEl.textContent = Number.parseFloat(uniqueFreqs[0]).toFixed(1);
        freqEl.style.color = 'var(--accent)';
      } else {
        freqEl.textContent = 'MIXED';
        freqEl.style.color = 'var(--warn)';
      }

      // Expanded meters
      document.getElementById('m-meter-rx').innerHTML = '<span class="m-dot m-dot-good" style="display:inline-block;margin-right:6px"></span>' + online + ' <span class="unit">/ ' + total + ' online</span>';

      const mFreqMeter = document.getElementById('m-meter-freq');
      if (uniqueFreqs.length === 0) {
        mFreqMeter.innerHTML = '— <span class="unit">no active rx</span>';
      } else if (uniqueFreqs.length === 1) {
        mFreqMeter.innerHTML = Number.parseFloat(uniqueFreqs[0]).toFixed(1) + ' <span class="unit">MHz</span>';
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
      const aois = aoiJson.aois;
      let aoiCount = 0;
      let exCount = 0;
      for (let i = 0; i < aois.length; i++) {
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
      const dbInt = data.db_intersections || 0;
      document.getElementById('m-pipe-intersects').textContent = fmt(dbInt);

      const inclusterWrap = document.getElementById('m-pipe-incluster-wrap');
      const clustersWrap = document.getElementById('m-pipe-clusters-wrap');
      const arrow1 = document.getElementById('m-pipe-arrow-1');
      const arrow2 = document.getElementById('m-pipe-arrow-2');
      const warnEl = document.getElementById('m-pipe-warn');
      const warnText = document.getElementById('m-pipe-warn-text');
      const clustEl = document.getElementById('m-stat-clust');

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

      const totals = data.totals || {};
      const inCluster = totals.in_cluster || 0;
      const clusters = totals.clusters || 0;

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

      let warn = '';
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
      mSetLiveState(isLive);
    }
  };

  // ── Build mobile receiver cards ──
  function mBuildReceiverCards(rxJson) {
    const container = document.getElementById('m-rx-cards');
    container.innerHTML = '';
    const receivers = rxJson.receivers;
    const total = Object.keys(receivers).length;

    for (let i = 0; i < total; i++) {
      const rx = receivers[i];
      const card = document.createElement('div');
      card.className = 'm-card';

      let html = '<div class="m-rxhead">';
      html += '<span class="m-dot ' + (rx.active ? 'm-dot-good' : 'm-dot-bad') + '"></span>';
      html += '<span class="m-rxid">' + esc(rx.station_id) + '</span>';
      html += '<span class="m-rxpill ' + (rx.active ? 'on' : 'off') + '">' + (rx.active ? 'ONLINE' : 'OFFLINE') + '</span>';
      html += '<span class="m-rx-toggle ' + (rx.active ? 'on' : '') + '" data-uid="' + rx.uid + '"><span class="m-rx-thumb"></span></span>';
      html += '</div>';

      html += '<div class="m-kvgrid">';
      html += '<div class="m-kv"><span class="m-k">LAT</span><span class="m-v">' + Number.parseFloat(rx.latitude).toFixed(5) + '°</span></div>';
      html += '<div class="m-kv"><span class="m-k">LON</span><span class="m-v">' + Number.parseFloat(rx.longitude).toFixed(5) + '°</span></div>';
      html += '<div class="m-kv"><span class="m-k">HDG</span><span class="m-v">' + rx.heading + '°</span></div>';
      html += '<div class="m-kv"><span class="m-k">FREQ</span><span class="m-v accent">' + rx.frequency + ' MHz</span></div>';
      html += '</div>';

      if (rx.active) {
        const sig = rx.signal || 0;
        const conf = rx.conf || 0;
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
        const uid = Number.parseInt(toggle.dataset.uid);
        const isCurrentlyOn = toggle.classList.contains('on');
        activateReceiver(uid, !isCurrentlyOn);
      });
    });
  }

  // ── Build mobile AOI cards ──
  function mBuildAoiCards(aoiJson) {
    const aoiContainer = document.getElementById('m-aoi-cards');
    const exContainer = document.getElementById('m-exclusion-cards');
    aoiContainer.innerHTML = '';
    exContainer.innerHTML = '';

    const aois = aoiJson.aois;
    for (let i = 0; i < aois.length; i++) {
      const aoi = aois[i];
      const isExclusion = aoi.aoi_type === 'exclusion';
      const kind = isExclusion ? 'exclusion' : 'aoi';
      const dotClass = isExclusion ? 'm-dot-warn' : 'm-dot-acc';

      const card = document.createElement('div');
      card.className = 'm-card ' + kind;

      let html = '<div class="m-aoi-head">';
      html += '<span class="m-dot ' + dotClass + '"></span>';
      html += '<span class="m-aoi-label">' + esc(aoi.label || kind.toUpperCase() + '-' + aoi.uid) + '</span>';
      html += '<button class="m-remove-btn" data-uid="' + aoi.uid + '">Remove</button>';
      html += '</div>';
      html += '<div class="m-kvgrid">';
      html += '<div class="m-kv"><span class="m-k">LAT</span><span class="m-v">' + Number.parseFloat(aoi.latitude).toFixed(4) + '°</span></div>';
      html += '<div class="m-kv"><span class="m-k">LON</span><span class="m-v">' + Number.parseFloat(aoi.longitude).toFixed(4) + '°</span></div>';
      html += '<div class="m-kv" style="grid-column:1/-1"><span class="m-k">RAD</span><span class="m-v">' + Number(aoi.radius).toLocaleString() + ' m</span></div>';
      html += '</div>';

      card.innerHTML = html;
      (isExclusion ? exContainer : aoiContainer).appendChild(card);
    }

    // Wire remove buttons
    document.querySelectorAll('#m-aoi-cards .m-remove-btn, #m-exclusion-cards .m-remove-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        deleteAoi(Number.parseInt(btn.dataset.uid));
      });
    });
  }

  // ── Mobile add buttons ──
  document.getElementById('m-add-rx-btn').addEventListener('click', function() {
    const url = prompt('Enter receiver URL (e.g. http://receiver:8081/doa):');
    if (url?.trim()) {
      makeNewRx(url.trim());
    }
  });

  document.getElementById('m-add-aoi-btn').addEventListener('click', function() {
    closeDrawer();
    const lat = document.getElementById('aoi-new-lat');
    const lon = document.getElementById('aoi-new-lon');
    const rad = document.getElementById('aoi-new-radius');
    lat.value = '';
    lon.value = '';
    rad.value = '';
    pickCenter(lat, lon, rad, Cesium.Color.CORNFLOWERBLUE);
  });

  document.getElementById('m-add-exclusion-btn').addEventListener('click', function() {
    closeDrawer();
    const lat = document.getElementById('exclusion-new-lat');
    const lon = document.getElementById('exclusion-new-lon');
    const rad = document.getElementById('exclusion-new-radius');
    lat.value = '';
    lon.value = '';
    rad.value = '';
    pickCenter(lat, lon, rad, Cesium.Color.ORANGE);
  });

  // ── Init: set defaults ──
  mUpdateWindowDisplay();
})();
