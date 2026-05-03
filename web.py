import gzip
import json
import logging
import math
import socket
from urllib.parse import urlsplit

from bottle import Bottle, run, request, response, redirect, template, static_file, HTTPError
from bottle.ext.websocket import GeventWebSocketServer, websocket

import geo

log = logging.getLogger(__name__)

_NO_CACHE = 'no-cache, no-store, must-revalidate, max-age=0'
_JSON_CT = 'application/json'


# NOTE: there is intentionally no authentication on these routes. The default
# bind is 127.0.0.1 (see config.AppConfig). If you bind to a non-loopback
# address (e.g. --ip 0.0.0.0), anyone on that network can mutate state. Adding
# auth is a product decision (token? basic auth? reverse-proxy?) and is out of
# scope here — the validation below only narrows the blast radius of malformed
# or hostile payloads, it does not authorize callers.


def _read_json_body(required_keys=()):
    try:
        data = json.load(request.body)
    except (ValueError, TypeError):
        raise HTTPError(400, "malformed JSON body")
    if not isinstance(data, dict):
        raise HTTPError(400, "JSON body must be an object")
    for k in required_keys:
        if k not in data:
            raise HTTPError(400, f"missing required field: {k}")
    return data


def _require_int(data, key, lo=None, hi=None):
    try:
        value = int(data[key])
    except (KeyError, TypeError, ValueError):
        raise HTTPError(400, f"field '{key}' must be an integer")
    if lo is not None and value < lo:
        raise HTTPError(400, f"field '{key}' below minimum {lo}")
    if hi is not None and value > hi:
        raise HTTPError(400, f"field '{key}' above maximum {hi}")
    return value


def _require_float(data, key, lo=None, hi=None):
    try:
        value = float(data[key])
    except (KeyError, TypeError, ValueError):
        raise HTTPError(400, f"field '{key}' must be a number")
    if math.isnan(value):
        raise HTTPError(400, f"field '{key}' must be finite")
    if lo is not None and value < lo:
        raise HTTPError(400, f"field '{key}' below minimum {lo}")
    if hi is not None and value > hi:
        raise HTTPError(400, f"field '{key}' above maximum {hi}")
    return value


def _rx_resolve(data, receiver_manager):
    # Returns the receiver object for the given uid, raising 400 if it's
    # gone. Resolution is atomic on the manager's lock — callers must not
    # then re-index `receiver_manager.receivers[uid]` (TOCTOU with remove()).
    idx = _require_int(data, 'uid', lo=0)
    rx = receiver_manager.get_by_index(idx)
    if rx is None:
        raise HTTPError(400, "uid out of range")
    return idx, rx


# Receiver URL validation. KrakenSDR boxes live on the same LAN (often the
# same host) as the aggregator, so loopback / RFC1918 / link-local addresses
# are the *normal* case — we deliberately do NOT block them. We only reject
# things that are clearly not a receiver:
#   - non-http(s) schemes (file://, gopher://, etc.)
#   - missing host
#   - hosts that don't resolve
# Combined with the no-redirect opener in receivers.py, that's the layer.
# Real SSRF mitigation here would mean an allowlist of operator-trusted hosts;
# adding auth (see top-of-file note) is the more honest fix.
def _validate_receiver_url(url):
    try:
        parts = urlsplit(url)
    except ValueError:
        raise HTTPError(400, "invalid receiver URL")
    if parts.scheme not in ('http', 'https'):
        raise HTTPError(400, "receiver URL must be http or https")
    host = parts.hostname
    if not host:
        raise HTTPError(400, "receiver URL must include a host")
    try:
        socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPError(400, "receiver host did not resolve")


def _apply_cesium_updates(ms, query):
    if query.minconf:
        ms.min_conf = float(query.minconf)
    if query.minpower:
        ms.min_power = float(query.minpower)
    if query.rx == "true":
        ms.receiving = True
    elif query.rx == "false":
        ms.receiving = False
    if query.lob_history == "true":
        ms.lob_history_enabled = True
    elif query.lob_history == "false":
        ms.lob_history_enabled = False


def _resolve_plotallintersects(query, ms):
    if query.plotpts == "true":
        return True
    if query.plotpts == "false":
        return False
    return ms.plotintersects


def _snapshot_rx_properties(receiver_manager):
    with receiver_manager.lock():
        snapshot = list(enumerate(receiver_manager.receivers))
    rx_properties = []
    for index, x in snapshot:
        rx = x.receiver_dict()
        rx['uid'] = index
        rx_properties.append(rx)
    return rx_properties


def _rx_action_new(receiver_manager):
    data = _read_json_body(required_keys=('station_url',))
    url = data['station_url']
    if not isinstance(url, str):
        raise HTTPError(400, "station_url must be a string")
    url = url.replace('\n', '').strip()
    _validate_receiver_url(url)
    receiver_manager.add(url)


def _rx_action_del(receiver_manager):
    data = _read_json_body(required_keys=('uid',))
    index, _ = _rx_resolve(data, receiver_manager)
    receiver_manager.remove(index)


def _rx_action_activate(receiver_manager):
    data = _read_json_body(required_keys=('uid', 'state'))
    _, rx = _rx_resolve(data, receiver_manager)
    state = bool(data['state'])
    rx.isActive = state
    if state:
        rx.error_count = 0
        rx.last_error = ""
        rx.next_retry_time = 0
        rx.next_probe_time = 0
        rx.max_retries = 0
    else:
        rx.next_probe_time = 0


def _rx_action_configure(action, receiver_manager):
    try:
        index = int(action)
    except ValueError:
        raise HTTPError(400, "action must be 'new', 'del', 'activate', or an integer index")
    data = _read_json_body(required_keys=('mobile', 'inverted', 'single'))
    rx = receiver_manager.get_by_index(index)
    if rx is None:
        raise HTTPError(400, "receiver index out of range")
    rx.isMobile = bool(data['mobile'])
    rx.inverted = bool(data['inverted'])
    rx.isSingle = bool(data['single'])
    # Don't call rx.update() here — that's a 5s blocking HTTP fetch
    # in a request handler. The polling loop calls update() every
    # ~1s and will apply the new isMobile/inverted/isSingle flags
    # on the next cycle (raw_doa interpretation reads them by ref).
    # The redirect target /rx_params returns cached state anyway,
    # so the synchronous fetch wasn't even visible to the client.
    receiver_manager.save_to_db()


def _dispatch_rx_action(action, receiver_manager):
    match action:
        case "new":
            _rx_action_new(receiver_manager)
        case "del":
            _rx_action_del(receiver_manager)
        case "activate":
            _rx_action_activate(receiver_manager)
        case _:
            _rx_action_configure(action, receiver_manager)


def _aoi_action_new(db):
    data = _read_json_body(required_keys=('aoi_type', 'latitude', 'longitude', 'radius'))
    if "" in data.values():
        raise HTTPError(400, "AOI fields must not be empty")
    aoi_type = data['aoi_type']
    if aoi_type not in ('aoi', 'exclusion'):
        raise HTTPError(400, "aoi_type must be 'aoi' or 'exclusion'")
    # Earth's circumference is ~40,000 km; cap radius well above any
    # realistic AOI to keep downstream geodesy from running away.
    lat = _require_float(data, 'latitude', lo=-90.0, hi=90.0)
    lon = _require_float(data, 'longitude', lo=-180.0, hi=180.0)
    radius = _require_float(data, 'radius', lo=1.0, hi=20_000_000.0)
    db.add_aoi(aoi_type, lat, lon, radius)


def _aoi_action_del(db):
    data = _read_json_body(required_keys=('uid',))
    uid = _require_int(data, 'uid', lo=0)
    db.execute("UPDATE intersects SET aoi_id=? WHERE aoi_id=?", [(-1, uid)], wait=True)
    db.execute("DELETE FROM interest_areas WHERE uid=?", [(str(uid),)], wait=True)
    db.commit_and_invalidate_aoi_cache()


def _aoi_action_purge(db):
    data = _read_json_body(required_keys=('uid',))
    uid = _require_int(data, 'uid', lo=0)
    row = db.query_one(
        "SELECT aoi_type, latitude, longitude, radius FROM interest_areas WHERE uid=?",
        [uid])
    if row is None:
        raise HTTPError(404, "AOI not found")
    # Purge is only defined for exclusion zones — see purge_database.
    # The UI only offers the button for exclusions; reject anything
    # else with a 400 instead of letting the ValueError become a 500.
    if row[0] != "exclusion":
        raise HTTPError(400, "purge is only defined for exclusion zones")
    db.purge_database(*row)


def _dispatch_aoi_action(action, db):
    match action:
        case "new":
            _aoi_action_new(db)
        case "del":
            _aoi_action_del(db)
        case "purge":
            _aoi_action_purge(db)
        case _:
            raise HTTPError(400, "unknown action")


def create_routes(config, ms, db, receiver_manager):
    app = Bottle()

    @app.route('/static/<filepath:path>', name='static')
    def server_static(filepath):
        resp = static_file(filepath, root='./static')
        resp.set_header('Cache-Control', _NO_CACHE)
        return resp

    @app.get('/')
    @app.get('/index')
    @app.get('/cesium')
    def cesium():
        response.set_header('Cache-Control', _NO_CACHE)
        return template('cesium.tpl',
                        {'access_token': config.access_token,
                         'epsilon': ms.eps,
                         'minpower': ms.min_power,
                         'minconf': ms.min_conf,
                         'minpoints': ms.min_samp,
                         'rx_state': "checked" if ms.receiving is True else "",
                         'intersect_state': "checked" if ms.plotintersects is True else "",
                         'lob_history_state': "checked" if ms.lob_history_enabled is True else "",
                         'receivers': receiver_manager.receivers})

    @app.get('/update')
    def update_cesium():
        _apply_cesium_updates(ms, request.query)
        return "OK"

    @app.get('/rx_params')
    def rx_params():
        # No rx.update() here — the run_loop polls every ~1s; this endpoint
        # just returns cached state for the UI cards.
        response.headers['Content-Type'] = _JSON_CT
        return json.dumps({'receivers': _snapshot_rx_properties(receiver_manager)})

    @app.get('/output.czml')
    def tx_czml_out():
        eps = request.query.eps if request.query.eps else str(ms.eps)
        min_samp = request.query.minpts if request.query.minpts else str(ms.min_samp)
        plotallintersects = _resolve_plotallintersects(request.query, ms)
        response.set_header('Cache-Control', _NO_CACHE)
        output = geo.write_czml(*geo.process_data(db, eps, min_samp), plotallintersects, eps)
        return str(output)

    @app.get('/api/pipeline-stats')
    def pipeline_stats():
        response.headers['Content-Type'] = _JSON_CT
        response.set_header('Cache-Control', _NO_CACHE)
        return json.dumps(geo.get_pipeline_stats())

    @app.put('/rx_params/<action>')
    def update_rx(action):
        _dispatch_rx_action(action, receiver_manager)
        return redirect('/rx_params')

    @app.get('/interest_areas')
    def load_interest_areas():
        aoi_properties = [
            {'uid': x[0], 'aoi_type': x[1], 'latitude': x[2], 'longitude': x[3], 'radius': x[4]}
            for x in db.fetch_aoi_data()
        ]
        response.headers['Content-Type'] = _JSON_CT
        return json.dumps({'aois': aoi_properties})

    @app.put('/interest_areas/<action>')
    def handle_interest_areas(action):
        _dispatch_aoi_action(action, db)

    @app.get('/run_all_aoi_rules')
    def run_aoi_rules():
        response.headers['Content-Type'] = _JSON_CT
        return json.dumps(db.run_aoi_rules())

    @app.get('/receivers.czml')
    def rx_czml():
        response.set_header('Cache-Control', _NO_CACHE)
        return geo.write_rx_czml(receiver_manager, ms)

    @app.get('/lob_history.czml')
    def lob_history():
        response.set_header('Cache-Control', _NO_CACHE)
        params = {
            'start': request.query.start,
            'end': request.query.end,
            'min_conf': request.query.min_conf,
            'min_power': request.query.min_power,
            'mode': request.query.mode,
            'frequency': request.query.frequency,
        }
        return geo.lob_history_czml(db, ms, params)

    @app.get('/aoi.czml')
    def aoi_czml():
        response.set_header('Cache-Control', _NO_CACHE)
        return geo.wr_aoi_czml(db)

    return app


class GzipMiddleware:
    _COMPRESSIBLE = (
        'text/',
        'application/json',
        'application/javascript',
        'application/x-javascript',
        'application/czml',
    )
    _MIN_SIZE = 512

    def __init__(self, wsgi_app):
        self.app = wsgi_app

    @staticmethod
    def _is_websocket_upgrade(environ):
        return (environ.get('HTTP_UPGRADE', '').lower() == 'websocket' and
                'upgrade' in environ.get('HTTP_CONNECTION', '').lower())

    def _is_compressible(self, headers):
        content_type = ''
        for name, value in headers:
            name_lower = name.lower()
            if name_lower == 'content-encoding':
                return False
            if name_lower == 'content-type':
                content_type = value.lower()
        return any(ct in content_type for ct in self._COMPRESSIBLE)

    @staticmethod
    def _rebuild_headers_for_gzip(headers, compressed_len):
        # Merge Accept-Encoding into any existing Vary token list rather
        # than replacing it. Stripping an upstream `Vary: Cookie` would tell
        # caches a per-user response is safe to share — silent correctness
        # bug if a future route ever needs cookie-varying caching.
        existing_vary_tokens = []
        new_headers = []
        for name, value in headers:
            lname = name.lower()
            if lname in ('content-length', 'content-encoding'):
                continue
            if lname == 'vary':
                existing_vary_tokens.extend(
                    t.strip() for t in value.split(',') if t.strip())
                continue
            new_headers.append((name, value))

        if not any(t.lower() == 'accept-encoding' for t in existing_vary_tokens):
            existing_vary_tokens.append('Accept-Encoding')

        new_headers.append(('Content-Encoding', 'gzip'))
        new_headers.append(('Content-Length', str(compressed_len)))
        new_headers.append(('Vary', ', '.join(existing_vary_tokens)))
        return new_headers

    def __call__(self, environ, start_response):
        if (self._is_websocket_upgrade(environ) or
                'gzip' not in environ.get('HTTP_ACCEPT_ENCODING', '')):
            return self.app(environ, start_response)

        captured_status = []
        captured_headers = []

        def _start_response(status, headers, exc_info=None):
            if exc_info and captured_status:
                raise exc_info[1].with_traceback(exc_info[2])
            captured_status[:] = [status]
            captured_headers[:] = [headers]

        result = self.app(environ, _start_response)

        if not captured_status:
            return result

        status = captured_status[0]
        headers = captured_headers[0]

        if not self._is_compressible(headers):
            start_response(status, headers)
            return result

        try:
            body = b''.join(result)
        finally:
            if hasattr(result, 'close'):
                result.close()

        if len(body) < self._MIN_SIZE:
            start_response(status, headers)
            return [body]

        compressed = gzip.compress(body, compresslevel=6)
        new_headers = self._rebuild_headers_for_gzip(headers, len(compressed))
        start_response(status, new_headers)
        return [compressed]


def start_server(config, app):
    try:
        run(app=GzipMiddleware(app), host=config.ip, port=config.port, quiet=True,
            server=GeventWebSocketServer, debug=config.debugging)
    except OSError:
        log.error("Port %d seems to be in use. Please select another port or "
                  "check if another instance of DFA is already running.", config.port)
