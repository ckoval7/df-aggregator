import json

from bottle import route, run, request, get, put, response, redirect, template, static_file, app as bottle_app
from bottle.ext.websocket import GeventWebSocketServer, websocket

import geo


def create_routes(config, ms, db, receiver_manager):

    @route('/static/<filepath:path>', name='static')
    def server_static(filepath):
        resp = static_file(filepath, root='./static')
        resp.set_header(
            'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        return resp

    @get('/')
    @get('/index')
    @get('/cesium')
    def cesium():
        response.set_header(
            'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
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

    @get('/update')
    def update_cesium():
        ms.min_conf = float(
            request.query.minconf) if request.query.minconf else ms.min_conf
        ms.min_power = float(
            request.query.minpower) if request.query.minpower else ms.min_power
        if request.query.rx == "true":
            ms.receiving = True
        elif request.query.rx == "false":
            ms.receiving = False
        if request.query.lob_history == "true":
            ms.lob_history_enabled = True
        elif request.query.lob_history == "false":
            ms.lob_history_enabled = False
        return "OK"

    @get('/rx_params')
    def rx_params():
        all_rx = {'receivers': {}}
        rx_properties = []
        for index, x in enumerate(receiver_manager.receivers):
            rx = x.receiver_dict()
            rx['uid'] = index
            rx_properties.append(rx)
        all_rx['receivers'] = rx_properties
        response.headers['Content-Type'] = 'application/json'
        return json.dumps(all_rx)

    @get('/output.czml')
    def tx_czml_out():
        eps = request.query.eps if request.query.eps else str(ms.eps)
        min_samp = request.query.minpts if request.query.minpts else str(ms.min_samp)
        if request.query.plotpts == "true":
            plotallintersects = True
        elif request.query.plotpts == "false":
            plotallintersects = False
        else:
            plotallintersects = ms.plotintersects
        response.set_header(
            'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        output = geo.write_czml(*geo.process_data(db, eps, min_samp), plotallintersects, eps)
        return str(output)

    @get('/api/pipeline-stats')
    def pipeline_stats():
        response.headers['Content-Type'] = 'application/json'
        response.set_header('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        return json.dumps(geo.get_pipeline_stats())

    @put('/rx_params/<action>')
    def update_rx(action):
        data = json.load(request.body)
        if action == "new":
            receiver_url = data['station_url'].replace('\n', '')
            receiver_manager.add(receiver_url)
        elif action == "del":
            index = int(data['uid'])
            receiver_manager.remove(index)
        elif action == "activate":
            index = int(data['uid'])
            receiver_manager.receivers[index].isActive = data['state']
            if data['state']:
                receiver_manager.receivers[index].error_count = 0
                receiver_manager.receivers[index].last_error = ""
                receiver_manager.receivers[index].next_retry_time = 0
                receiver_manager.receivers[index].next_probe_time = 0
                receiver_manager.receivers[index].max_retries = 0
            else:
                receiver_manager.receivers[index].next_probe_time = 0
        else:
            action = int(action)
            try:
                receiver_manager.receivers[action].isMobile = data['mobile']
                receiver_manager.receivers[action].inverted = data['inverted']
                receiver_manager.receivers[action].isSingle = data['single']
                receiver_manager.receivers[action].update()
                receiver_manager.save_to_db()
            except IndexError:
                print("I got some bad data. Doing nothing out of spite.")
        return redirect('/rx_params')

    @get('/interest_areas')
    def load_interest_areas():
        all_aoi = {'aois': {}}
        aoi_properties = []
        for x in db.fetch_aoi_data():
            aoi = {
                'uid': x[0], 'aoi_type': x[1],
                'latitude': x[2], 'longitude': x[3], 'radius': x[4]
            }
            aoi_properties.append(aoi)
        all_aoi['aois'] = aoi_properties
        response.headers['Content-Type'] = 'application/json'
        return json.dumps(all_aoi)

    @put('/interest_areas/<action>')
    def handle_interest_areas(action):
        data = json.load(request.body)
        if action == "new" and not "" in data.values():
            aoi_type = data['aoi_type']
            lat = data['latitude']
            lon = data['longitude']
            radius = data['radius']
            db.add_aoi(aoi_type, lat, lon, radius)
        elif action == "del":
            command = "UPDATE intersects SET aoi_id=? WHERE aoi_id=?"
            db.execute(command, [(-1, data['uid'])], wait=True)
            to_table = (str(data['uid']),)
            command = "DELETE FROM interest_areas WHERE uid=?"
            db.execute(command, [to_table], wait=True)
            db.commit()
            db.invalidate_aoi_cache()
        elif action == "purge":
            row = db.query_one("SELECT aoi_type, latitude, longitude, radius FROM interest_areas WHERE uid=?",
                               [data['uid']])
            db.purge_database(*row)

    @get('/run_all_aoi_rules')
    def run_aoi_rules():
        return db.run_aoi_rules()

    @get('/receivers.czml')
    def rx_czml():
        response.set_header(
            'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        return geo.write_rx_czml(receiver_manager, ms)

    @get('/lob_history.czml')
    def lob_history():
        response.set_header(
            'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        params = {
            'start': request.query.start,
            'end': request.query.end,
            'min_conf': request.query.min_conf,
            'min_power': request.query.min_power,
            'mode': request.query.mode,
            'frequency': request.query.frequency,
        }
        return geo.lob_history_czml(db, ms, params)

    @get('/aoi.czml')
    def aoi_czml():
        response.set_header(
            'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
        return geo.wr_aoi_czml(db)


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

    def __call__(self, environ, start_response):
        if (environ.get('HTTP_UPGRADE', '').lower() == 'websocket' and
                'upgrade' in environ.get('HTTP_CONNECTION', '').lower()):
            return self.app(environ, start_response)

        if 'gzip' not in environ.get('HTTP_ACCEPT_ENCODING', ''):
            return self.app(environ, start_response)

        captured_status = []
        captured_headers = []

        def _start_response(status, headers, exc_info=None):
            if exc_info:
                try:
                    if captured_status:
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None
            captured_status[:] = [status]
            captured_headers[:] = [headers]

        result = self.app(environ, _start_response)

        if not captured_status:
            return result

        status = captured_status[0]
        headers = captured_headers[0]

        content_type = ''
        already_encoded = False
        for name, value in headers:
            name_lower = name.lower()
            if name_lower == 'content-type':
                content_type = value.lower()
            elif name_lower == 'content-encoding':
                already_encoded = True

        compressible = (
            not already_encoded and
            any(ct in content_type for ct in self._COMPRESSIBLE)
        )

        if not compressible:
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

        import gzip as gzip_mod
        compressed = gzip_mod.compress(body, compresslevel=6)

        new_headers = [
            (name, value) for name, value in headers
            if name.lower() not in ('content-length', 'content-encoding', 'vary')
        ]
        new_headers.append(('Content-Encoding', 'gzip'))
        new_headers.append(('Content-Length', str(len(compressed))))
        new_headers.append(('Vary', 'Accept-Encoding'))

        start_response(status, new_headers)
        return [compressed]


def start_server(config):
    try:
        run(app=GzipMiddleware(bottle_app()), host=config.ip, port=config.port, quiet=True,
            server=GeventWebSocketServer, debug=True)
    except OSError:
        print(f"Port {config.port} seems to be in use. Please select another port or " +
              "check if another instance of DFA is already running.")
