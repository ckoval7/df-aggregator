<!DOCTYPE html>

<!-- df-aggregator, networked radio direction finding software.
    Copyright (C) 2020 Corey Koval

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>. -->

<html lang="en">
<head>
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">
  <meta name="viewport" content="width=device-width, height=device-height">
  <meta charset="utf-8">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cesium.com/downloads/cesiumjs/releases/1.135/Build/Cesium/Cesium.js"></script>
  <link href="https://cesium.com/downloads/cesiumjs/releases/1.135/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
  <link href="/static/ui.css" rel="stylesheet">
</head>
<body>
  <div id="loader" class="loader"></div>
  <div id="cesiumContainer"></div>

  <!-- ===== Status Bar ===== -->
  <header class="statusbar">
    <div class="brand">
      <div class="brand-logo">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="2"/>
          <path d="M16.24 7.76a6 6 0 0 1 0 8.49M7.76 16.24a6 6 0 0 1 0-8.49"/>
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 19.07a10 10 0 0 1 0-14.14"/>
        </svg>
      </div>
      <div class="brand-text">
        <div class="brand-name">DF AGGREGATOR</div>
        <div class="brand-sub">Networked Direction Finding</div>
      </div>
    </div>

    <div class="stat-group">
      <div class="stat">
        <div class="stat-label">RECEIVERS</div>
        <div class="stat-value"><span class="dot dot-good"></span><span id="stat-rx-count">0</span><span class="muted" id="stat-rx-total">/0</span></div>
      </div>
      <div class="stat">
        <div class="stat-label">AOI</div>
        <div class="stat-value" id="stat-aoi-count">0</div>
      </div>
      <div class="stat">
        <div class="stat-label">EXCLUSIONS</div>
        <div class="stat-value" id="stat-ex-count">0</div>
      </div>
      <div class="stat" id="stat-freq">
        <div class="stat-label">FREQUENCY</div>
        <div class="stat-value mono" id="stat-freq-value">&mdash; <span class="unit" id="stat-freq-unit">no active rx</span></div>
      </div>
      <div class="stat">
        <div class="stat-label">MODE</div>
        <div class="stat-value">
          <span class="mode-pill live" id="stat-mode-pill"><span class="rec-dot"></span>LIVE</span>
        </div>
      </div>
    </div>

    <div class="stat-group stat-group-pipeline" id="stat-pipeline-group">
      <div class="stat">
        <div class="stat-label">INTERSECTS</div>
        <div class="stat-value mono" id="stat-db-intersections">—</div>
      </div>
      <div class="pipeline-arrow" id="pipeline-arrow-1">→</div>
      <div class="stat" id="stat-incluster-wrap">
        <div class="stat-label">IN CLUSTERS</div>
        <div class="stat-value mono" id="stat-in-cluster">—</div>
      </div>
      <div class="pipeline-arrow" id="pipeline-arrow-2">→</div>
      <div class="stat" id="stat-clusters-wrap">
        <div class="stat-label">CLUSTERS</div>
        <div class="stat-value mono accent" id="stat-clusters">—</div>
      </div>
      <div class="pipeline-warn hidden" id="pipeline-warn"></div>
    </div>

    <div class="clock">
      <div class="clock-time" id="clock-time">--:--:-- UTC</div>
      <div class="clock-date" id="clock-date">-- --- ----</div>
    </div>
    <button class="panel-toggle" id="panel-toggle" title="Toggle panel">
      <span class="hamburger-icon"></span>
    </button>
  </header>

  <!-- ===== Signal Filters ===== -->
  <div class="filters-host" id="filters-host">
    <div class="filters-card" id="filters-card">
      <div class="filters-head">
        <div class="filters-title">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
          Signal Filters
        </div>
        <button class="icon-btn-sm" id="filters-collapse" title="Collapse">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
        </button>
      </div>

      <div class="filt-section">
        <label class="filt-toggle">
          <span class="filt-toggle-text">
            <span class="filt-label">Enable Processing</span>
            <span class="filt-hint">Process intersections from active receivers</span>
          </span>
          <span class="toggle {{'on' if rx_state else ''}}" id="rx-en-toggle" role="switch">
            <span class="toggle-thumb"></span>
          </span>
        </label>
      </div>

      <div class="filt-section">
        <div class="filt-row">
          <div class="filt-label">Min Power</div>
          <input type="range" min="0" max="100" value="{{minpower}}" class="filt-slider" id="powerRange">
          <div class="filt-val" id="power-val">{{minpower}}</div>
        </div>
        <div class="filt-row">
          <div class="filt-label">Min Confidence</div>
          <input type="range" min="0" max="300" value="{{minconf}}" class="filt-slider" id="confRange">
          <div class="filt-val" id="conf-val">{{minconf}}</div>
        </div>
      </div>

      <div class="filt-section">
        <label class="filt-toggle">
          <span class="filt-toggle-text">
            <span class="filt-label">Clustering</span>
            <span class="filt-hint">Draw confidence ellipses around clusters</span>
          </span>
          <span class="toggle {{'on' if epsilon == 'auto' else ''}}" id="clustering-toggle" role="switch">
            <span class="toggle-thumb"></span>
          </span>
        </label>
        <div class="filt-row">
          <div class="filt-label">Epsilon</div>
          <input type="range" min="0" max="2" step="0.01" value="{{0 if epsilon == 'auto' else epsilon}}" class="filt-slider" id="epsilonRange">
          <div class="filt-val {{'filt-val-auto' if epsilon == 'auto' else ''}}" id="eps-val">{{'AUTO' if epsilon == 'auto' else epsilon}}</div>
        </div>
        <div class="filt-row">
          <div class="filt-label">Min Samples</div>
          <input type="range" min="0" max="300" step="5" value="{{0 if minpoints == 'auto' else minpoints}}" class="filt-slider" id="minpointRange">
          <div class="filt-val {{'filt-val-auto' if minpoints == 'auto' else ''}}" id="minpoint-val">{{'AUTO' if minpoints == 'auto' else minpoints}}</div>
        </div>
      </div>

      <div class="filt-section">
        <label class="filt-toggle">
          <span class="filt-toggle-text">
            <span class="filt-label">Plot All Intersect Points</span>
          </span>
          <span class="toggle {{'on' if intersect_state else ''}}" id="intersect-toggle" role="switch">
            <span class="toggle-thumb"></span>
          </span>
        </label>
      </div>

      <div class="filt-foot">
        <button class="btn btn-primary" id="refreshbutton">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          Refresh
        </button>
      </div>
    </div>
    <button class="filt-fab hidden" id="filters-fab" title="Show signal filters">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
      <span>Filters</span>
    </button>
  </div>

  <!-- ===== Side Panel ===== -->
  <aside class="sidepanel" id="sidepanel">
    <!-- Receivers Section -->
    <div class="panel-section">
      <div class="section-head">
        <div class="section-title">
          <span>Receivers</span>
          <span class="count-pill" id="rx-count-pill">0</span>
        </div>
        <div class="section-actions">
          <button class="icon-btn" id="add-rx-btn" title="Add Receiver">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
      </div>
      <div class="new-item-form hidden" id="new-rx-form">
        <label>
          Station URL
          <input type="text" id="new-rx-url" placeholder="http://receiver:8081/doa">
        </label>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-primary" id="save-new-rx" style="flex:1">Save</button>
          <button class="btn btn-ghost" id="cancel-new-rx" style="flex:0">Cancel</button>
        </div>
      </div>
      <div class="cards" id="rx-cards"></div>
    </div>

    <!-- Areas of Interest Section -->
    <div class="panel-section">
      <div class="section-head">
        <div class="section-title">
          <span>Areas of Interest</span>
          <span class="count-pill" id="aoi-count-pill">0</span>
        </div>
        <div class="section-actions">
          <button class="icon-btn" id="run-aoi-rules-btn" title="Apply AOI rules">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
          </button>
          <button class="icon-btn" id="add-aoi-btn" title="Add Area of Interest">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
      </div>
      <div class="new-item-form hidden" id="new-aoi-form">
        <label>Lat <input type="text" id="aoi-new-lat" readonly></label>
        <label>Lon <input type="text" id="aoi-new-lon" readonly></label>
        <label>Radius (m) <input type="text" id="aoi-new-radius" readonly></label>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-primary" id="save-new-aoi" style="flex:1">Save</button>
          <button class="btn btn-ghost" id="cancel-new-aoi" style="flex:0">Cancel</button>
        </div>
      </div>
      <div class="cards" id="aoi-cards"></div>
    </div>

    <!-- Exclusion Areas Section -->
    <div class="panel-section">
      <div class="section-head">
        <div class="section-title">
          <span>Exclusion Areas</span>
          <span class="count-pill" id="ex-count-pill">0</span>
        </div>
        <div class="section-actions">
          <button class="icon-btn" id="add-exclusion-btn" title="Add Exclusion Area">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          </button>
        </div>
      </div>
      <div class="new-item-form hidden" id="new-exclusion-form">
        <label>Lat <input type="text" id="exclusion-new-lat" readonly></label>
        <label>Lon <input type="text" id="exclusion-new-lon" readonly></label>
        <label>Radius (m) <input type="text" id="exclusion-new-radius" readonly></label>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-primary" id="save-new-exclusion" style="flex:1">Save</button>
          <button class="btn btn-ghost" id="cancel-new-exclusion" style="flex:0">Cancel</button>
        </div>
      </div>
      <div class="cards" id="exclusion-cards"></div>
    </div>

    <!-- LOB History Section -->
    <div class="panel-section">
      <div class="section-head">
        <div class="section-title">
          <span>LOB History</span>
          <span class="rec-pill" id="rec-pill" style="display:none"><span class="rec-dot"></span>REC</span>
        </div>
      </div>
      <div class="card timeline-card">
        <label class="filt-toggle">
          <span class="filt-toggle-text">
            <span class="filt-label">Record History</span>
            <span class="filt-hint">Persist LOB data to database</span>
          </span>
          <span class="toggle {{'on' if lob_history_state else ''}}" id="lob-history-toggle" role="switch">
            <span class="toggle-thumb"></span>
          </span>
        </label>

        <div class="tl-row">
          <div class="tl-row-label">Time Range</div>
          <div class="seg-group" id="time-presets">
            <button class="seg-btn" data-minutes="30">30 min</button>
            <button class="seg-btn active" data-minutes="60">1 hour</button>
            <button class="seg-btn" data-minutes="240">4 hours</button>
            <button class="seg-btn" data-minutes="1440">24 hours</button>
          </div>
        </div>

        <div class="tl-row">
          <div class="tl-row-label">Start</div>
          <input type="datetime-local" class="tl-input" id="history_start" step="1">
        </div>
        <div class="tl-row">
          <div class="tl-row-label">End</div>
          <input type="datetime-local" class="tl-input" id="history_end" step="1">
        </div>

        <div class="tl-row">
          <div class="tl-row-label">Mode</div>
          <div class="seg-group" id="history-mode-group">
            <button class="seg-btn active" data-mode="flash">Flash</button>
            <button class="seg-btn" data-mode="accumulate">Accumulate</button>
          </div>
        </div>

        <div class="tl-row">
          <div class="tl-row-label">Frequency</div>
          <div class="tl-input-group">
            <input type="text" class="tl-input" id="history_frequency" placeholder="All frequencies">
            <span class="tl-input-suffix">Hz</span>
          </div>
        </div>

        <div class="scrub" id="scrub-container">
          <div class="scrub-track" id="scrub-track"></div>
          <div class="scrub-axis" id="scrub-axis"></div>
        </div>

        <div class="tl-foot">
          <button class="btn btn-primary" id="loadHistoryBtn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            Load History
          </button>
          <button class="btn btn-ghost" id="liveBtn" style="display:none">
            <span class="live-dot"></span>Go Live
          </button>
        </div>
      </div>
    </div>
  </aside>

  <!-- ===== Mobile Layout (<=768px) ===== -->

  <!-- Mobile: Top Status Strip -->
  <div class="m-topbar" id="m-topbar">
    <div class="m-topbar-row" id="m-topbar-row">
      <button class="m-burger" id="m-burger" title="Menu">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
      </button>
      <span class="m-mode live" id="m-mode-pill">
        <span class="m-rec-dot"></span>LIVE
      </span>
      <div class="m-strip">
        <div class="m-strip-cell"><span class="m-cap">RX</span><span class="m-val" id="m-stat-rx">0<span style="color:var(--fg-3)">/0</span></span></div>
        <div class="m-strip-cell"><span class="m-cap">FREQ</span><span class="m-val" id="m-stat-freq">&mdash;</span></div>
        <div class="m-strip-cell"><span class="m-cap">CLUST</span><span class="m-val" id="m-stat-clust">&mdash;</span></div>
      </div>
      <div class="m-chev">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
      </div>
    </div>
    <div class="m-topbar-expanded">
      <div class="m-row-grid">
        <div class="m-meter"><span class="m-cap">Receivers</span><span class="m-val" id="m-meter-rx"><span class="m-dot m-dot-good" style="display:inline-block;margin-right:6px"></span>0 <span class="unit">/ 0 online</span></span></div>
        <div class="m-meter"><span class="m-cap">AOI · Excl</span><span class="m-val" id="m-meter-aoi">0 <span class="unit">aoi</span> · 0 <span class="unit">excl</span></span></div>
        <div class="m-meter"><span class="m-cap">Frequency</span><span class="m-val" id="m-meter-freq">&mdash; <span class="unit">no active rx</span></span></div>
        <div class="m-meter"><span class="m-cap">Mode</span><span class="m-val" id="m-meter-mode">LIVE capture</span></div>
      </div>
      <div class="m-pipeline">
        <span class="m-pipe-cap">DBSCAN Pipeline</span>
        <div class="m-pipe-row">
          <div class="m-pipe-step"><span class="m-pipe-num" id="m-pipe-intersects">&mdash;</span><span class="m-pipe-lbl">intersects</span></div>
          <svg class="m-pipe-arrow" id="m-pipe-arrow-1" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="9 18 15 12 9 6"/></svg>
          <div class="m-pipe-step" id="m-pipe-incluster-wrap"><span class="m-pipe-num" id="m-pipe-incluster">&mdash;</span><span class="m-pipe-lbl" id="m-pipe-incluster-lbl">in cluster</span></div>
          <svg class="m-pipe-arrow" id="m-pipe-arrow-2" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="9 18 15 12 9 6"/></svg>
          <div class="m-pipe-step" id="m-pipe-clusters-wrap"><span class="m-pipe-num" id="m-pipe-clusters">&mdash;</span><span class="m-pipe-lbl">clusters</span></div>
        </div>
        <div class="m-pipe-warn hidden" id="m-pipe-warn">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 9v2m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg>
          <span id="m-pipe-warn-text"></span>
        </div>
      </div>
    </div>
  </div>

  <!-- Mobile: Drawer Scrim -->
  <div class="m-scrim" id="m-scrim"></div>

  <!-- Mobile: Drawer -->
  <aside class="m-drawer" id="m-drawer">
    <div class="m-drawer-head">
      <div class="m-drawer-logo">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="2"/><path d="M16.24 7.76a6 6 0 0 1 0 8.49M7.76 16.24a6 6 0 0 1 0-8.49"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 19.07a10 10 0 0 1 0-14.14"/></svg>
      </div>
      <div>
        <div class="m-drawer-title">DF AGGREGATOR</div>
        <div class="m-drawer-sub">Field Operator</div>
      </div>
      <button class="m-drawer-close" id="m-drawer-close" title="Close">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
    <div class="m-drawer-tabs">
      <button class="m-drawer-tab active" data-tab="receivers">Recv<span class="m-tab-count" id="m-tab-rx-count">0</span></button>
      <button class="m-drawer-tab" data-tab="aois">Areas<span class="m-tab-count" id="m-tab-aoi-count">0</span></button>
      <button class="m-drawer-tab" data-tab="filters">Filters</button>
      <button class="m-drawer-tab" data-tab="history">History</button>
    </div>
    <div class="m-drawer-body">

      <!-- Receivers Tab -->
      <div class="m-tab-pane active" id="m-pane-receivers">
        <div class="m-section-head">
          <span class="m-section-title">Receivers</span>
          <span class="m-pill" id="m-rx-pill">0</span>
        </div>
        <div id="m-rx-cards"></div>
        <button class="m-add-btn" id="m-add-rx-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Add receiver
        </button>
      </div>

      <!-- Areas Tab -->
      <div class="m-tab-pane" id="m-pane-aois">
        <div class="m-section-head">
          <span class="m-section-title">Areas of Interest</span>
          <span class="m-pill" id="m-aoi-pill">0</span>
        </div>
        <div id="m-aoi-cards"></div>
        <button class="m-add-btn" id="m-add-aoi-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Add AOI
        </button>
        <div class="m-divider"></div>
        <div class="m-section-head">
          <span class="m-section-title">Exclusions</span>
          <span class="m-pill" id="m-ex-pill">0</span>
        </div>
        <div id="m-exclusion-cards"></div>
        <button class="m-add-btn" id="m-add-exclusion-btn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Add exclusion
        </button>
      </div>

      <!-- Filters Tab -->
      <div class="m-tab-pane" id="m-pane-filters">
        <div class="m-filt-section">
          <div class="m-filt-row toggle-row">
            <div>
              <div class="m-filt-label">Enable Processing</div>
              <div class="m-filt-hint">Process intersections from active receivers</div>
            </div>
            <span class="m-rx-toggle {{'on' if rx_state else ''}}" id="m-rx-en-toggle"><span class="m-rx-thumb"></span></span>
          </div>
          <div class="m-filt-row">
            <div class="m-filt-head">
              <div class="m-filt-label">Min Power</div>
              <div class="m-filt-val" id="m-power-val">{{minpower}}</div>
            </div>
            <input type="range" class="m-slider" min="0" max="100" value="{{minpower}}" id="m-powerRange">
          </div>
          <div class="m-filt-row">
            <div class="m-filt-head">
              <div class="m-filt-label">Min Confidence</div>
              <div class="m-filt-val" id="m-conf-val">{{minconf}}</div>
            </div>
            <input type="range" class="m-slider" min="0" max="300" value="{{minconf}}" id="m-confRange">
          </div>
          <div class="m-filt-row toggle-row">
            <div>
              <div class="m-filt-label">Clustering</div>
              <div class="m-filt-hint">Draw confidence ellipses around clusters</div>
            </div>
            <span class="m-rx-toggle {{'on' if epsilon == 'auto' else ''}}" id="m-clustering-toggle"><span class="m-rx-thumb"></span></span>
          </div>
          <div class="m-filt-row">
            <div class="m-filt-head">
              <div>
                <div class="m-filt-label">Epsilon (ε)</div>
                <div class="m-filt-hint">DBSCAN neighborhood radius — 0 lets server pick</div>
              </div>
              <div class="m-filt-val {{'auto' if epsilon == 'auto' else ''}}" id="m-eps-val">{{'AUTO' if epsilon == 'auto' else epsilon}}</div>
            </div>
            <input type="range" class="m-slider" min="0" max="2" step="0.01" value="{{0 if epsilon == 'auto' else epsilon}}" id="m-epsilonRange">
          </div>
          <div class="m-filt-row">
            <div class="m-filt-head">
              <div>
                <div class="m-filt-label">Min Samples</div>
                <div class="m-filt-hint">Min points to form a cluster</div>
              </div>
              <div class="m-filt-val {{'auto' if minpoints == 'auto' else ''}}" id="m-minpoint-val">{{'AUTO' if minpoints == 'auto' else minpoints}}</div>
            </div>
            <input type="range" class="m-slider" min="0" max="300" step="5" value="{{0 if minpoints == 'auto' else minpoints}}" id="m-minpointRange">
          </div>
          <div class="m-filt-row toggle-row">
            <div>
              <div class="m-filt-label">Plot All Intersect Points</div>
              <div class="m-filt-hint">Show every intersection, skip clustering</div>
            </div>
            <span class="m-rx-toggle {{'on' if intersect_state else ''}}" id="m-intersect-toggle"><span class="m-rx-thumb"></span></span>
          </div>
          <button class="m-bigbtn primary" id="m-refresh-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            Refresh
          </button>
        </div>
      </div>

      <!-- History Tab -->
      <div class="m-tab-pane" id="m-pane-history">
        <div class="m-filt-section">
          <div class="m-filt-row toggle-row">
            <div>
              <div class="m-filt-label">Record History</div>
              <div class="m-filt-hint">Persist LOB data to database</div>
            </div>
            <span class="m-rx-toggle {{'on' if lob_history_state else ''}}" id="m-lob-history-toggle"><span class="m-rx-thumb"></span></span>
          </div>
          <div class="m-hist-row">
            <span class="m-row-lbl">Time Range</span>
            <div class="m-seg" id="m-time-presets">
              <button data-minutes="30">30m</button>
              <button class="active" data-minutes="60">1h</button>
              <button data-minutes="240">4h</button>
              <button data-minutes="1440">24h</button>
            </div>
          </div>
          <div class="m-hist-row">
            <span class="m-row-lbl">Mode</span>
            <div class="m-seg two-col" id="m-mode-group">
              <button class="active" data-mode="flash">Flash</button>
              <button data-mode="accumulate">Accumulate</button>
            </div>
          </div>
          <div class="m-hist-row">
            <span class="m-row-lbl">Window</span>
            <div class="m-window-block">
              <div><span class="m-window-label">FROM</span><span id="m-window-from">—</span></div>
              <div><span class="m-window-label">&nbsp; TO</span><span id="m-window-to">—</span></div>
            </div>
          </div>
          <button class="m-bigbtn ghost" id="m-edit-range-btn">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            Edit Range…
          </button>
          <div class="m-hist-foot">
            <button class="m-bigbtn primary" id="m-load-history-main-btn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
              Load History
            </button>
            <button class="m-bigbtn ghost" id="m-live-btn" style="display:none">
              <span class="live-dot"></span>Go Live
            </button>
          </div>
        </div>
      </div>

    </div>
  </aside>

  <!-- Mobile: Bottom Sheet -->
  <div class="m-sheet-scrim" id="m-sheet-scrim"></div>
  <div class="m-sheet" id="m-sheet">
    <div class="m-sheet-handle"></div>
    <div class="m-sheet-head">
      <div class="m-sheet-title">Edit Time Range</div>
      <button class="m-sheet-close" id="m-sheet-close">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
      </button>
    </div>
    <div class="m-sheet-body">
      <div class="m-hist-row">
        <span class="m-row-lbl">Start</span>
        <input type="datetime-local" class="m-time-input" id="m-history-start" step="1">
      </div>
      <div class="m-hist-row">
        <span class="m-row-lbl">End</span>
        <input type="datetime-local" class="m-time-input" id="m-history-end" step="1">
      </div>
      <div class="m-hist-row">
        <span class="m-row-lbl">Frequency</span>
        <input type="text" class="m-time-input" id="m-history-freq" placeholder="All frequencies">
      </div>
      <button class="m-bigbtn primary" id="m-load-history-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
        Load History
      </button>
    </div>
  </div>

  <!-- Mobile: Scrub Bar (history playback) -->
  <div class="m-scrub" id="m-scrub">
    <div class="m-scrub-track" id="m-scrub-track"></div>
    <span class="m-scrub-bound m-scrub-start" id="m-scrub-start"></span>
    <span class="m-scrub-bound m-scrub-end" id="m-scrub-end"></span>
    <div class="m-scrub-time" id="m-scrub-time">00:00:00 UTC</div>
    <button class="m-scrub-play" id="m-scrub-play">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/></svg>
    </button>
  </div>

  <!-- ===== CesiumJS Init ===== -->
  <script>
    var transmittersDataSource = new Cesium.CzmlDataSource();
    var receiversDataSource = new Cesium.CzmlDataSource();
    var aoiDataSource = new Cesium.CzmlDataSource();
    var lobHistoryDataSource = new Cesium.CzmlDataSource();

    % if access_token:
    Cesium.Ion.defaultAccessToken = '{{access_token}}';
    % end

    var defaultImageryViewModels = Cesium.createDefaultImageryProviderViewModels();
    var esriViewModel = defaultImageryViewModels.find(function(vm) {
      return vm.name === 'ArcGIS World Imagery';
    });

    var viewer = new Cesium.Viewer('cesiumContainer', {
      imageryProviderViewModels: defaultImageryViewModels,
      selectedImageryProviderViewModel: esriViewModel,
      sceneModePicker: true,
      baseLayerPicker: true,
      homeButton: false,
      geocoder: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      timeline: true,
      animation: true,
      mapProjection: new Cesium.WebMercatorProjection(),
    });

    viewer.infoBox.frame.setAttribute("sandbox", "allow-same-origin allow-popups allow-popups-to-escape-sandbox");
    viewer.infoBox.frame.src = "about:blank";

    var cesiumToolbar = document.querySelector('.cesium-viewer-toolbar');
    var statusbarEl = document.querySelector('.statusbar');
    var clockEl = document.querySelector('.clock');
    if (cesiumToolbar && statusbarEl && clockEl) {
      statusbarEl.insertBefore(cesiumToolbar, clockEl);
    }

    var clock = new Cesium.Clock({
      clockStep: Cesium.ClockStep.SYSTEM_CLOCK_MULTIPLIER
    });
    viewer.clock.shouldAnimate = true;

    var hpr = new Cesium.HeadingPitchRange(0.0, -1.57, 0.0);
    viewer.flyTo(loadAllCzml(), {'offset': hpr});

    var scene = viewer.scene;
    if (!scene.pickPositionSupported) {
      window.alert("This browser does not support pickPosition.");
    }

    var handler;
    var cartesian;
    var cartographic;
    var rad_cartesian;
    var center_lat;
    var center_lon;
    var radius;

    var noSelect = false;
    var myClickFunction = function(event) {
      if (noSelect) {
        viewer.selectedEntity = undefined;
        viewer.trackedEntity = undefined;
        return;
      }
      var pickedObjects = scene.drillPick(event.position);
      if (pickedObjects.length === 0) {
        viewer.selectedEntity = undefined;
        return;
      }
      var bestEntity = null;
      for (var i = 0; i < pickedObjects.length; i++) {
        var entity = pickedObjects[i].id;
        if (entity && entity.point) {
          bestEntity = entity;
          break;
        }
      }
      if (!bestEntity) {
        bestEntity = pickedObjects[0].id;
      }
      viewer.selectedEntity = bestEntity;
    };
    viewer.screenSpaceEventHandler.setInputAction(myClickFunction, Cesium.ScreenSpaceEventType.LEFT_CLICK);

    function pickCenter(lat_element_id, lon_element_id, radius_element_id, outlineColor) {
      noSelect = true;
      scene.canvas.style.cursor = "crosshair";
      var entity = viewer.entities.add({
        label: {
          show: false, showBackground: true, font: "14px monospace",
          horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(15, 0),
        },
      });
      handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
      handler.setInputAction(function(movement) {
        cartesian = viewer.camera.pickEllipsoid(movement.endPosition, scene.globe.ellipsoid);
        if (cartesian) {
          cartographic = Cesium.Cartographic.fromCartesian(cartesian);
          var center_lon = Cesium.Math.toDegrees(cartographic.longitude).toFixed(5);
          var center_lat = Cesium.Math.toDegrees(cartographic.latitude).toFixed(5);
          lat_element_id.value = center_lat;
          lon_element_id.value = center_lon;
          entity.position = cartesian;
          entity.label.show = true;
          entity.label.text = "Lat: " + ("   " + center_lat).slice(-10) + "\nLon: " + ("   " + center_lon).slice(-10);
        } else {
          entity.label.show = false;
        }
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
      handler.setInputAction(function() {
        handler = handler && handler.destroy();
        viewer.entities.remove(entity);
        pickRadius(radius_element_id, cartographic, outlineColor);
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    }

    function clearHover() {
      noSelect = false;
      scene.canvas.style.cursor = "default";
      viewer.entities.removeAll();
      handler = handler && handler.destroy();
    }

    function pickRadius(radius_element_id, center_carto, outlineColor) {
      noSelect = true;
      var currentRadius = 0;
      var centerPosition = Cesium.Cartesian3.fromRadians(center_carto.longitude, center_carto.latitude);
      var circleEntity = viewer.entities.add({
        position: centerPosition,
        ellipse: {
          semiMajorAxis: new Cesium.CallbackProperty(function() { return currentRadius; }, false),
          semiMinorAxis: new Cesium.CallbackProperty(function() { return currentRadius; }, false),
          fill: false, outline: true, outlineColor: outlineColor, outlineWidth: 3, height: 0,
        },
      });
      var labelEntity = viewer.entities.add({
        label: {
          show: false, showBackground: true, font: "14px monospace",
          horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
          verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
          pixelOffset: new Cesium.Cartesian2(15, 0),
        },
      });
      handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
      handler.setInputAction(function(movement) {
        rad_cartesian = viewer.camera.pickEllipsoid(movement.endPosition, scene.globe.ellipsoid);
        if (rad_cartesian) {
          cartographic = Cesium.Cartographic.fromCartesian(rad_cartesian);
          var ellipsoidGeodesic = new Cesium.EllipsoidGeodesic(center_carto, cartographic);
          currentRadius = Math.max(1, Number(ellipsoidGeodesic.surfaceDistance.toFixed(0)));
          radius_element_id.value = currentRadius;
          labelEntity.position = rad_cartesian;
          labelEntity.label.show = true;
          labelEntity.label.text = currentRadius + " m";
        } else {
          labelEntity.label.show = false;
        }
      }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
      handler.setInputAction(function() {
        circleEntity.ellipse.semiMajorAxis = currentRadius;
        circleEntity.ellipse.semiMinorAxis = currentRadius;
        viewer.entities.remove(labelEntity);
        noSelect = false;
        scene.canvas.style.cursor = "default";
        handler = handler && handler.destroy();
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
    }

    function updateParams(parameter) {
      clearOld();
      fetch("/update?" + (parameter || ""))
        .then(function() {
          loadRx(function(rx_json) {
            refreshRx(rx_json);
            statusBar.updateReceiverStats(rx_json);
            if (window.mobileUI) mobileUI.updateReceiverStats(rx_json);
          });
          loadAllCzml();
        });
    }

    function loadTxCzml() {
      var parameter = "";
      var spinner = document.getElementById("loader");
      spinner.style.visibility = "visible";
      spinner.style.zIndex = "10";

      var epsslider = document.getElementById("epsilonRange");
      var minpointslider = document.getElementById("minpointRange");
      var intersect_en = document.getElementById("intersect-toggle");
      var clustering_en = document.getElementById("clustering-toggle");

      if (minpointslider !== null) {
        if (parseInt(minpointslider.value) > 0) {
          parameter += "minpts=" + minpointslider.value + "&";
        } else {
          parameter += "minpts=auto&";
        }
      }
      if (clustering_en !== null) {
        if (clustering_en.classList.contains('on')) {
          if (parseFloat(epsslider.value) === 0) {
            parameter += "eps=auto&";
          } else {
            parameter += "eps=" + epsslider.value + "&";
          }
        } else {
          parameter += "eps=0&";
        }
      }
      if (intersect_en !== null) {
        if (intersect_en.classList.contains('on')) {
          parameter += "plotpts=true&";
        } else {
          parameter += "plotpts=false&";
        }
      }
      var promise1 = transmittersDataSource.load('/output.czml?' + parameter);
      promise1.then(function(dataSource1) {
        spinner.style.visibility = "hidden";
        spinner.style.zIndex = "0";
        statusBar.fetchPipelineStats();
      }).catch(function(error) {
        console.error('Error loading transmitters CZML:', error);
        spinner.style.visibility = "hidden";
        spinner.style.zIndex = "0";
      });
      viewer.dataSources.add(transmittersDataSource);
      return transmittersDataSource;
    }

    function loadRxCzml() {
      receiversDataSource.load('/receivers.czml');
      viewer.dataSources.add(receiversDataSource);
      return receiversDataSource;
    }

    function loadAoiCzml() {
      aoiDataSource.load('/aoi.czml');
      viewer.dataSources.add(aoiDataSource);
      return aoiDataSource;
    }

    function loadAllCzml() {
      loadAoiCzml();
      loadRxCzml();
      return loadTxCzml();
    }

    function clearOld() {
      viewer.dataSources.remove(receiversDataSource, true);
      viewer.dataSources.remove(aoiDataSource, true);
      viewer.dataSources.remove(transmittersDataSource, true);
    }

    function reloadRX() {
      viewer.dataSources.remove(receiversDataSource, true);
      loadRxCzml();
    }

    function reloadAoi() {
      viewer.dataSources.remove(aoiDataSource, true);
      loadAoiCzml();
    }
  </script>

  <!-- ===== Component Scripts ===== -->
  <script src="/static/statusbar.js"></script>
  <script src="/static/receiver_configurator.js"></script>
  <script src="/static/interest_areas.js"></script>
  <script src="/static/cardsmenu.js"></script>
  <script src="/static/lob_history.js"></script>
  <script src="/static/mobile.js"></script>
  <script src="/static/mobile_scrub.js"></script>

  <!-- ===== Init & Filter Wiring ===== -->
  <script>
    statusBar.init();
    statusBar.setMode(true);

    loadRx(function(rx_json, id) {
      createReceivers(rx_json, id);
      statusBar.updateReceiverStats(rx_json);
      if (window.mobileUI) mobileUI.updateReceiverStats(rx_json);
    });
    loadAoi(function(aoi_json, id) {
      createAois(aoi_json, id);
      statusBar.updateAoiStats(aoi_json);
      if (window.mobileUI) mobileUI.updateAoiStats(aoi_json);
    });

    function saveFilters() {
      var state = {
        minpower: document.getElementById("powerRange").value,
        minconf: document.getElementById("confRange").value,
        epsilon: document.getElementById("epsilonRange").value,
        minpoints: document.getElementById("minpointRange").value,
        clustering: document.getElementById("clustering-toggle").classList.contains("on"),
        intersects: document.getElementById("intersect-toggle").classList.contains("on"),
        processing: document.getElementById("rx-en-toggle").classList.contains("on"),
        lob_history: document.getElementById("lob-history-toggle").classList.contains("on")
      };
      localStorage.setItem('df-signal-filters', JSON.stringify(state));
    }

    (function restoreFilters() {
      var raw = localStorage.getItem('df-signal-filters');
      if (!raw) return;
      try { var s = JSON.parse(raw); } catch(e) { return; }

      var powerSlider = document.getElementById("powerRange");
      var confSlider = document.getElementById("confRange");
      var epsSlider = document.getElementById("epsilonRange");
      var minpointSlider = document.getElementById("minpointRange");

      if (s.minpower != null) {
        powerSlider.value = s.minpower;
        document.getElementById("power-val").textContent = s.minpower;
      }
      if (s.minconf != null) {
        confSlider.value = s.minconf;
        document.getElementById("conf-val").textContent = s.minconf;
      }
      if (s.epsilon != null) {
        epsSlider.value = s.epsilon;
        var epsVal = document.getElementById("eps-val");
        if (parseFloat(s.epsilon) > 0) {
          epsVal.textContent = s.epsilon;
          epsVal.className = 'filt-val';
        } else {
          epsVal.textContent = 'AUTO';
          epsVal.className = 'filt-val filt-val-auto';
        }
      }
      if (s.minpoints != null) {
        minpointSlider.value = s.minpoints;
        var mpVal = document.getElementById("minpoint-val");
        if (parseInt(s.minpoints) > 0) {
          mpVal.textContent = s.minpoints;
          mpVal.className = 'filt-val';
        } else {
          mpVal.textContent = 'AUTO';
          mpVal.className = 'filt-val filt-val-auto';
        }
      }

      var clusterToggle = document.getElementById("clustering-toggle");
      if (s.clustering === true && !clusterToggle.classList.contains("on")) clusterToggle.classList.add("on");
      else if (s.clustering === false && clusterToggle.classList.contains("on")) clusterToggle.classList.remove("on");

      var intersectToggle = document.getElementById("intersect-toggle");
      if (s.intersects === true && !intersectToggle.classList.contains("on")) intersectToggle.classList.add("on");
      else if (s.intersects === false && intersectToggle.classList.contains("on")) intersectToggle.classList.remove("on");

      var rxToggle = document.getElementById("rx-en-toggle");
      if (s.processing === true && !rxToggle.classList.contains("on")) rxToggle.classList.add("on");
      else if (s.processing === false && rxToggle.classList.contains("on")) rxToggle.classList.remove("on");

      var lobToggle = document.getElementById("lob-history-toggle");
      if (s.lob_history === true && !lobToggle.classList.contains("on")) lobToggle.classList.add("on");
      else if (s.lob_history === false && lobToggle.classList.contains("on")) lobToggle.classList.remove("on");
      var recPill = document.getElementById("rec-pill");
      if (recPill) recPill.style.display = lobToggle.classList.contains("on") ? "" : "none";

      if (window.mobileUI) {
        var mPower = document.getElementById('m-powerRange');
        var mConf = document.getElementById('m-confRange');
        var mEps = document.getElementById('m-epsilonRange');
        var mMinpt = document.getElementById('m-minpointRange');
        if (mPower) { mPower.value = powerSlider.value; document.getElementById('m-power-val').textContent = powerSlider.value; }
        if (mConf) { mConf.value = confSlider.value; document.getElementById('m-conf-val').textContent = confSlider.value; }
        if (mEps) {
          mEps.value = epsSlider.value;
          var mEpsVal = document.getElementById('m-eps-val');
          if (parseFloat(epsSlider.value) > 0) { mEpsVal.textContent = epsSlider.value; mEpsVal.className = 'm-filt-val'; }
          else { mEpsVal.textContent = 'AUTO'; mEpsVal.className = 'm-filt-val auto'; }
        }
        if (mMinpt) {
          mMinpt.value = minpointSlider.value;
          var mMinptVal = document.getElementById('m-minpoint-val');
          if (parseInt(minpointSlider.value) > 0) { mMinptVal.textContent = minpointSlider.value; mMinptVal.className = 'm-filt-val'; }
          else { mMinptVal.textContent = 'AUTO'; mMinptVal.className = 'm-filt-val auto'; }
        }

        var mCluster = document.getElementById('m-clustering-toggle');
        var mIntersect = document.getElementById('m-intersect-toggle');
        var mRxEn = document.getElementById('m-rx-en-toggle');
        var mLob = document.getElementById('m-lob-history-toggle');

        if (s.clustering === true && mCluster && !mCluster.classList.contains('on')) mCluster.classList.add('on');
        else if (s.clustering === false && mCluster && mCluster.classList.contains('on')) mCluster.classList.remove('on');

        if (s.intersects === true && mIntersect && !mIntersect.classList.contains('on')) mIntersect.classList.add('on');
        else if (s.intersects === false && mIntersect && mIntersect.classList.contains('on')) mIntersect.classList.remove('on');

        if (s.processing === true && mRxEn && !mRxEn.classList.contains('on')) mRxEn.classList.add('on');
        else if (s.processing === false && mRxEn && mRxEn.classList.contains('on')) mRxEn.classList.remove('on');

        if (s.lob_history === true && mLob && !mLob.classList.contains('on')) mLob.classList.add('on');
        else if (s.lob_history === false && mLob && mLob.classList.contains('on')) mLob.classList.remove('on');
      }

      updateParams("minpower=" + powerSlider.value + "&minconf=" + confSlider.value
        + "&rx=" + (rxToggle.classList.contains("on") ? "true" : "false")
        + "&lob_history=" + (lobToggle.classList.contains("on") ? "true" : "false"));
    })();

    function wireToggle(id, onChange) {
      var el = document.getElementById(id);
      el.addEventListener('click', function() {
        el.classList.toggle('on');
        if (onChange) onChange(el.classList.contains('on'));
        saveFilters();
      });
    }

    wireToggle('rx-en-toggle', function(on) {
      updateParams("rx=" + (on ? "true" : "false"));
    });
    wireToggle('clustering-toggle', function() {
      updateParams("");
    });
    wireToggle('intersect-toggle', function() {
      updateParams("");
    });

    document.querySelectorAll('.filt-slider').forEach(function(slider) {
      var wheelTimer = null;
      slider.addEventListener('wheel', function(e) {
        e.preventDefault();
        var step = parseFloat(this.step) || 1;
        var val = parseFloat(this.value) + (e.deltaY < 0 ? step : -step);
        this.value = Math.min(parseFloat(this.max), Math.max(parseFloat(this.min), val));
        this.dispatchEvent(new Event('input'));
        var self = this;
        clearTimeout(wheelTimer);
        wheelTimer = setTimeout(function() {
          self.dispatchEvent(new PointerEvent('pointerup'));
        }, 300);
      }, {passive: false});
    });

    var powerSlider = document.getElementById("powerRange");
    var powerVal = document.getElementById("power-val");
    powerSlider.oninput = function() { powerVal.textContent = this.value; };
    powerSlider.onpointerup = function() { updateParams("minpower=" + this.value); saveFilters(); };

    var confSlider = document.getElementById("confRange");
    var confVal = document.getElementById("conf-val");
    confSlider.oninput = function() { confVal.textContent = this.value; };
    confSlider.onpointerup = function() { updateParams("minconf=" + this.value); saveFilters(); };

    var epsSlider = document.getElementById("epsilonRange");
    var epsVal = document.getElementById("eps-val");
    epsSlider.oninput = function() {
      if (parseFloat(this.value) > 0) {
        epsVal.textContent = this.value;
        epsVal.className = 'filt-val';
      } else {
        epsVal.textContent = 'AUTO';
        epsVal.className = 'filt-val filt-val-auto';
      }
    };
    epsSlider.onpointerup = function() { updateParams(""); saveFilters(); };

    var minpointSlider = document.getElementById("minpointRange");
    var minpointVal = document.getElementById("minpoint-val");
    minpointSlider.oninput = function() {
      if (parseInt(this.value) > 0) {
        minpointVal.textContent = this.value;
        minpointVal.className = 'filt-val';
      } else {
        minpointVal.textContent = 'AUTO';
        minpointVal.className = 'filt-val filt-val-auto';
      }
    };
    minpointSlider.onpointerup = function() { updateParams(""); saveFilters(); };

    document.getElementById("refreshbutton").addEventListener("click", function() {
      updateParams("");
    });

    var filtersCard = document.getElementById("filters-card");
    var filtersFab = document.getElementById("filters-fab");
    document.getElementById("filters-collapse").addEventListener("click", function() {
      filtersCard.style.display = "none";
      filtersFab.classList.remove("hidden");
      localStorage.setItem('df-filters-collapsed', 'true');
    });
    filtersFab.addEventListener("click", function() {
      filtersCard.style.display = "";
      filtersFab.classList.add("hidden");
      localStorage.setItem('df-filters-collapsed', 'false');
    });

    var sidepanel = document.getElementById("sidepanel");
    var panelToggle = document.getElementById("panel-toggle");
    function setPanelOpen(open) {
      sidepanel.classList.toggle("collapsed", !open);
      document.body.classList.toggle("panel-collapsed", !open);
      panelToggle.classList.toggle("active", open);
      panelToggle.title = open ? "Close panel" : "Open panel";
      localStorage.setItem('df-panel-collapsed', !open);
    }
    panelToggle.addEventListener("click", function() {
      var isCollapsed = sidepanel.classList.contains("collapsed");
      setPanelOpen(isCollapsed);
    });
    if (localStorage.getItem('df-panel-collapsed') === 'true') {
      setPanelOpen(false);
    } else {
      setPanelOpen(true);
    }
    if (localStorage.getItem('df-filters-collapsed') === 'true') {
      filtersCard.style.display = "none";
      filtersFab.classList.remove("hidden");
    }
  </script>
</body>
</html>
