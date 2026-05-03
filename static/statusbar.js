function fmtCount(n) {
  if (n == null) return '—';
  return n.toLocaleString();
}

const statusBar = {
  els: {},
  _pipelineTimer: null,

  init: function() {
    this.els.rxCount = document.getElementById('stat-rx-count');
    this.els.rxTotal = document.getElementById('stat-rx-total');
    this.els.aoiCount = document.getElementById('stat-aoi-count');
    this.els.exCount = document.getElementById('stat-ex-count');
    this.els.freqValue = document.getElementById('stat-freq-value');
    this.els.freqUnit = document.getElementById('stat-freq-unit');
    this.els.freqStat = document.getElementById('stat-freq');
    this.els.modePill = document.getElementById('stat-mode-pill');
    this.els.connPill = document.getElementById('conn-pill');
    this.els.clockTime = document.getElementById('clock-time');
    this.els.clockDate = document.getElementById('clock-date');
    this.els.dbIntersections = document.getElementById('stat-db-intersections');
    this.els.inCluster = document.getElementById('stat-in-cluster');
    this.els.clusters = document.getElementById('stat-clusters');
    this.els.pipelineWarn = document.getElementById('pipeline-warn');
    this.els.pipelineGroup = document.getElementById('stat-pipeline-group');
    this.els.inclusterWrap = document.getElementById('stat-incluster-wrap');
    this.els.clustersWrap = document.getElementById('stat-clusters-wrap');
    this.els.arrow1 = document.getElementById('pipeline-arrow-1');
    this.els.arrow2 = document.getElementById('pipeline-arrow-2');
    this.startClock();
  },

  startClock: function() {
    const tick = () => {
      const now = new Date();
      this.els.clockTime.textContent = now.toISOString().slice(11, 19) + ' UTC';
      const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
      const day = String(now.getUTCDate()).padStart(2, '0');
      this.els.clockDate.textContent = day + ' ' + months[now.getUTCMonth()] + ' ' + now.getUTCFullYear();
    };
    tick();
    setInterval(tick, 1000);
  },

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
    this.els.rxCount.textContent = online;
    this.els.rxTotal.textContent = '/' + total;

    const uniqueFreqs = Object.keys(freqs);
    if (uniqueFreqs.length === 0) {
      this.els.freqValue.textContent = '—';
      this.els.freqUnit.textContent = 'no active rx';
      this.els.freqStat.removeAttribute('title');
      this.els.freqValue.className = 'stat-value mono';
    } else if (uniqueFreqs.length === 1) {
      this.els.freqValue.textContent = Number.parseFloat(uniqueFreqs[0]).toFixed(1);
      this.els.freqUnit.textContent = 'MHz';
      this.els.freqStat.removeAttribute('title');
      this.els.freqValue.className = 'stat-value mono accent';
    } else {
      this.els.freqValue.innerHTML =
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M12 9v2m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/></svg> MIXED';
      this.els.freqUnit.textContent = uniqueFreqs.length + ' freqs';
      this.els.freqStat.title = 'Receivers tuned to: ' + uniqueFreqs.map(function(f) { return f + ' MHz'; }).join(', ');
      this.els.freqValue.className = 'stat-value mono warn';
    }
  },

  updateAoiStats: function(aoiJson) {
    const aois = aoiJson.aois;
    let aoiCount = 0;
    let exCount = 0;
    for (const aoi of aois) {
      if (aoi.aoi_type === 'exclusion') {
        exCount++;
      } else {
        aoiCount++;
      }
    }
    this.els.aoiCount.textContent = aoiCount;
    this.els.exCount.textContent = exCount;
  },

  setMode: function(isLive) {
    if (isLive) {
      this.els.modePill.className = 'mode-pill live';
      this.els.modePill.innerHTML = '<span class="rec-dot"></span>LIVE';
    } else {
      this.els.modePill.className = 'mode-pill history';
      this.els.modePill.innerHTML = '<span class="dot dot-accent"></span>HISTORY';
    }
  },

  setConnected: function(isConnected) {
    if (!this.els?.connPill) return;
    if (isConnected) {
      this.els.connPill.classList.remove('disconnected');
      this.els.connPill.classList.add('connected');
      this.els.connPill.title = 'Server connection: live';
    } else {
      this.els.connPill.classList.remove('connected');
      this.els.connPill.classList.add('disconnected');
      this.els.connPill.title = 'Server connection: lost (auto-reconnecting)';
    }
  },

  fetchPipelineStats: function() {
    if (this._pipelineTimer) clearTimeout(this._pipelineTimer);
    this._pipelineTimer = setTimeout(() => {
      fetch('/api/pipeline-stats')
        .then(function(r) { return r.json(); })
        .then((data) => { this.updatePipelineStats(data); })
        .catch(function() {});
    }, 250);
  },

  updatePipelineStats: function(data) {
    const dbInt = data.db_intersections || 0;
    this.els.dbIntersections.textContent = fmtCount(dbInt);

    if (!data.clustering_enabled) {
      this.els.inclusterWrap.style.display = 'none';
      this.els.arrow2.style.display = 'none';
      this.els.clustersWrap.style.display = 'none';
      this.els.arrow1.style.display = 'none';
      this._setPipelineWarn(dbInt === 0 ? 'No intersections in time window' : '');
      return;
    }

    this.els.inclusterWrap.style.display = '';
    this.els.clustersWrap.style.display = '';
    this.els.arrow1.style.display = '';
    this.els.arrow2.style.display = '';

    const totals = data.totals || {};
    const inCluster = totals.in_cluster || 0;
    const clusters = totals.clusters || 0;

    this.els.inCluster.textContent = fmtCount(inCluster);
    this.els.clusters.textContent = fmtCount(clusters);

    let tooltip = '';
    if (data.per_aoi && data.per_aoi.length > 1) {
      tooltip = data.per_aoi.map(function(a) {
        const label = a.aoi_id === -1 ? 'Global' : 'AOI-' + a.aoi_id;
        return label + ': ' + fmtCount(a.in_cluster) + ' in clusters / ' + fmtCount(a.clusters) + ' clusters';
      }).join('\n');
    }
    this.els.pipelineGroup.title = tooltip;

    let warn = '';
    if (dbInt === 0) {
      warn = 'No intersections in time window';
    }
    this._setPipelineWarn(warn);
    if (globalThis.mobileUI) globalThis.mobileUI.updatePipelineStats(data);
  },

  _setPipelineWarn: function(msg) {
    if (msg) {
      this.els.pipelineWarn.textContent = msg;
      this.els.pipelineWarn.classList.remove('hidden');
    } else {
      this.els.pipelineWarn.textContent = '';
      this.els.pipelineWarn.classList.add('hidden');
    }
  }
};
