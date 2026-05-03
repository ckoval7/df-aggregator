(function() {
  function bind() {
    const es = new EventSource('/events');

    es.addEventListener('rx_config', function(e) {
      const data = JSON.parse(e.data);
      if (typeof createReceivers === 'function') createReceivers(data);
      if (globalThis.statusBar) statusBar.updateReceiverStats(data);
      if (globalThis.mobileUI) mobileUI.updateReceiverStats(data);
      if (!isHistoryMode && typeof loadRxCzml === 'function') loadRxCzml();
    });

    es.addEventListener('rx_telemetry', function(e) {
      const data = JSON.parse(e.data);
      if (typeof applyTelemetryUpdates === 'function') applyTelemetryUpdates(data);
      if (!isHistoryMode && typeof loadRxCzml === 'function') loadRxCzml();
    });

    es.addEventListener('aoi_config', function(e) {
      const data = JSON.parse(e.data);
      if (typeof createAois === 'function') createAois(data);
      if (globalThis.statusBar) statusBar.updateAoiStats(data);
      if (globalThis.mobileUI) mobileUI.updateAoiStats(data);
      if (!isHistoryMode && typeof loadAoiCzml === 'function') loadAoiCzml();
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
