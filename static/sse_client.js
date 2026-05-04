(function() {
  // Trailing-edge debounce. Telemetry can fire several times per second per
  // receiver. loadRxCzml() merges via CzmlDataSource.process() so each call
  // is cheap, but coalescing still saves a network round trip per burst.
  function debounce(fn, wait) {
    let timer = null;
    return function() {
      if (timer !== null) clearTimeout(timer);
      timer = setTimeout(function() { timer = null; fn(); }, wait);
    };
  }

  function bind() {
    const es = new EventSource('/events');

    const debouncedLoadRx = debounce(function() {
      if (!isHistoryMode && typeof loadRxCzml === 'function') loadRxCzml();
    }, 1000);
    const debouncedLoadAoi = debounce(function() {
      if (!isHistoryMode && typeof loadAoiCzml === 'function') loadAoiCzml();
    }, 1000);

    es.addEventListener('rx_config', function(e) {
      const data = JSON.parse(e.data);
      if (typeof createReceivers === 'function') createReceivers(data);
      if (globalThis.statusBar) statusBar.updateReceiverStats(data);
      if (globalThis.mobileUI) mobileUI.updateReceiverStats(data);
      // Reconcile deletions immediately. The CZML emitter only sends packets
      // for stations that still exist; without this, stale receiver/LOB
      // entities would persist in the long-lived receiversDataSource.
      if (typeof pruneReceiverEntities === 'function') {
        const ids = (data.receivers || []).map(function(r) { return r.station_id; });
        pruneReceiverEntities(ids);
      }
      debouncedLoadRx();
    });

    es.addEventListener('rx_telemetry', function(e) {
      const data = JSON.parse(e.data);
      if (typeof applyTelemetryUpdates === 'function') applyTelemetryUpdates(data);
      debouncedLoadRx();
    });

    es.addEventListener('aoi_config', function(e) {
      const data = JSON.parse(e.data);
      if (typeof createAois === 'function') createAois(data);
      if (globalThis.statusBar) statusBar.updateAoiStats(data);
      if (globalThis.mobileUI) mobileUI.updateAoiStats(data);
      debouncedLoadAoi();
    });

    es.addEventListener('heartbeat', function() {
      if (globalThis.statusBar) statusBar.setConnected(true);
    });

    es.onopen = function() {
      if (globalThis.statusBar) statusBar.setConnected(true);
    };
    es.onerror = function() {
      if (globalThis.statusBar) statusBar.setConnected(false);
      // EventSource auto-reconnects; we don't recreate it here.
    };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
