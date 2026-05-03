(function() {
  function bind() {
    var es = new EventSource('/events');

    es.addEventListener('rx_config', function(e) {
      var data = JSON.parse(e.data);
      if (typeof createReceivers === 'function') createReceivers(data);
      if (globalThis.statusBar) statusBar.updateReceiverStats(data);
      if (globalThis.mobileUI) mobileUI.updateReceiverStats(data);
      if (typeof loadRxCzml === 'function') loadRxCzml();
    });

    es.addEventListener('rx_telemetry', function(e) {
      var data = JSON.parse(e.data);
      if (typeof applyTelemetryUpdates === 'function') applyTelemetryUpdates(data);
      if (typeof loadRxCzml === 'function') loadRxCzml();
    });

    es.addEventListener('pipeline', function(e) {
      var data = JSON.parse(e.data);
      if (globalThis.statusBar) statusBar.updatePipelineStats(data);
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
