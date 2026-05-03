import time
import threading
import urllib.request
import http.client
import urllib.error
import socket
from contextlib import contextmanager

import numpy as np
from lxml import etree

import vincenty as v
from config import (LOB_DRAW_DISTANCE_METERS, MAX_TIME_DIFF_MS,
    SINGLE_RX_MIN_TIME_DIFF_MS, HISTORICAL_LOB_WINDOW_MS,
    MIN_SPATIAL_DIVERSITY_METERS, MIN_LOB_PAIR_BEARING_DIFF_DEG,
    RECEIVER_MAX_RETRIES_TRANSIENT,
    RECEIVER_MAX_RETRIES_PERSISTENT, RECEIVER_BACKOFF_BASE_S,
    RECEIVER_PROBE_INTERVAL_S, clear)
from geo import plot_intersects


# Secure XML parser: receiver responses come from arbitrary network endpoints,
# so disable entity resolution and DTD loading to prevent XXE attacks.
_secure_parser = etree.XMLParser(
    resolve_entities=False,
    remove_comments=True,
    dtd_validation=False,
    load_dtd=False
)


# HTTP client policy for receiver polling — intentional choices, do not "fix":
#   - Stdlib urllib (not requests): receivers are KrakenSDR boxes on a LAN
#     speaking a tiny fixed XML protocol; pulling in `requests` adds a
#     dependency for zero functional gain.
#   - 5s timeout: receivers are polled ~once per second on a LAN; 5s is already
#     generous. Larger timeouts would stall the polling loop on a dead box.
#   - No custom User-Agent: receiver firmware does not inspect UA. The default
#     `Python-urllib/3.x` is fine.
#   - Redirects disabled: a redirecting receiver would point us at an
#     unintended endpoint whose body we'd then parse as XML. Fail loudly
#     instead — the resulting 3xx surfaces as HTTPError and is routed through
#     _classify_error's retry path.
class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_no_redirect_opener = urllib.request.build_opener(_NoRedirectHandler())


def _classify_error(ex):
    if isinstance(ex, urllib.error.HTTPError):
        if ex.code >= 500:
            return ('transient', RECEIVER_MAX_RETRIES_TRANSIENT)
        elif 400 <= ex.code < 500:
            return ('persistent', RECEIVER_MAX_RETRIES_PERSISTENT)
    transient_types = (
        http.client.IncompleteRead,
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        socket.error,
        OSError,
    )
    if isinstance(ex, transient_types):
        return ('transient', RECEIVER_MAX_RETRIES_TRANSIENT)
    persistent_types = (
        etree.XMLSyntaxError,
        ValueError,
        TypeError,
        AttributeError,
    )
    if isinstance(ex, persistent_types):
        return ('persistent', RECEIVER_MAX_RETRIES_PERSISTENT)
    return ('transient', RECEIVER_MAX_RETRIES_TRANSIENT)


class Receiver:
    def __init__(self, station_url):
        self.station_url = station_url
        self.isAuto = True
        self.isActive = True
        self.flipped = False
        self.inverted = True
        self.error_count = 0
        self.last_error = ""
        self.next_retry_time = 0
        self.next_probe_time = 0
        self.max_retries = 0
        self.latitude = 0.0
        self.longitude = 0.0
        self.heading = 0.0
        self.raw_doa = 0.0
        self.doa = 0.0
        self.frequency = 0.0
        self.power = 0.0
        self.confidence = 0
        self.doa_time = 0
        self.isMobile = False
        self.isSingle = False
        self.previous_doa_time = 0
        self.d_2_last_intersection = [LOB_DRAW_DISTANCE_METERS]
        self.station_id = "Unknown"
        self.update(first_run=True)

    def update(self, first_run=False):
        try:
            # Read the raw bytes first, then hand to the secure parser — never
            # let lxml fetch the URL itself (would bypass _secure_parser hardening).
            # Uses _no_redirect_opener (see module-level policy comment) — do
            # not swap back to bare urlopen() or to requests.get().
            req = urllib.request.Request(self.station_url, method='GET')
            with _no_redirect_opener.open(req, timeout=5) as resp:
                xml_data = resp.read()
            xml_contents = etree.fromstring(xml_data, parser=_secure_parser)
            xml_station_id = xml_contents.find('STATION_ID')
            self.station_id = xml_station_id.text
            xml_doa_time = xml_contents.find('TIME')
            self.doa_time = int(xml_doa_time.text)
            xml_freq = xml_contents.find('FREQUENCY')
            self.frequency = float(xml_freq.text)
            xml_latitude = xml_contents.find('LOCATION/LATITUDE')
            self.latitude = float(xml_latitude.text)
            xml_longitude = xml_contents.find('LOCATION/LONGITUDE')
            self.longitude = float(xml_longitude.text)
            xml_heading = xml_contents.find('LOCATION/HEADING')
            self.heading = float(xml_heading.text)
            xml_doa = xml_contents.find('DOA')
            self.raw_doa = float(xml_doa.text)
            if self.inverted:
                self.doa = self.heading + (360 - self.raw_doa)
            elif self.flipped:
                self.doa = self.heading + (180 + self.raw_doa)
            else:
                self.doa = self.heading + self.raw_doa
            self.doa = self.doa % 360
            xml_power = xml_contents.find('PWR')
            self.power = float(xml_power.text)
            xml_conf = xml_contents.find('CONF')
            self.confidence = int(xml_conf.text)
            self.error_count = 0
            self.last_error = ""
            self.next_retry_time = 0
            self.next_probe_time = 0
            self.max_retries = 0
        except KeyboardInterrupt:
            raise
        except Exception as ex:
            error_type, max_retries = _classify_error(ex)
            self.error_count += 1
            self.last_error = f"{type(ex).__name__}: {ex}"
            self.max_retries = max_retries
            backoff = min(RECEIVER_BACKOFF_BASE_S ** self.error_count, 64)
            self.next_retry_time = time.time() + backoff
            print(f"{ex} — {self.station_url} "
                  f"({error_type} error {self.error_count}/{max_retries}, "
                  f"retry in {backoff}s)")
            if first_run or self.error_count >= max_retries:
                if first_run:
                    self.station_id = "Unknown"
                self.latitude = 0.0
                self.longitude = 0.0
                self.heading = 0.0
                self.raw_doa = 0.0
                self.doa = 0.0
                self.frequency = 0.0
                self.power = 0.0
                self.confidence = 0
                self.doa_time = 0
                self.isActive = False
                self.error_count = 0
                self.next_retry_time = 0
                self.next_probe_time = time.time() + RECEIVER_PROBE_INTERVAL_S
                self.max_retries = 0
                print(
                    f"Problem connecting to {self.station_url}, receiver deactivated. "
                    f"Will auto-probe in {RECEIVER_PROBE_INTERVAL_S}s.")

    def receiver_dict(self):
        return ({'station_id': self.station_id, 'station_url': self.station_url,
                 'latitude': self.latitude, 'longitude': self.longitude, 'heading': self.heading,
                 'doa': self.doa, 'frequency': self.frequency, 'power': self.power,
                 'confidence': self.confidence, 'doa_time': self.doa_time, 'mobile': self.isMobile,
                 'active': self.isActive, 'auto': self.isAuto, 'inverted': self.inverted,
                 'single': self.isSingle})

    def lob_length(self):
        if self.d_2_last_intersection:
            return round(max(self.d_2_last_intersection)) + 200
        else:
            return LOB_DRAW_DISTANCE_METERS


class ReceiverManager:
    def __init__(self, db):
        self.db = db
        self.receivers = []
        # Guards the *structure* of self.receivers (append/del) and the
        # write-back of d_2_last_intersection. Per-receiver field reads and
        # writes (isActive, error_count, doa, ...) are not guarded — they
        # rely on CPython's atomic-attribute-write guarantee. Iteration over
        # the list MUST go through a snapshot taken under the lock; never
        # iterate self.receivers directly from a worker thread, since add()
        # and remove() can mutate it underneath you.
        self._lock = threading.Lock()

    @contextmanager
    def lock(self):
        with self._lock:
            yield

    def _snapshot(self):
        with self._lock:
            return list(self.receivers)

    def get_by_index(self, index):
        # Resolve uid -> receiver object atomically. Callers that look up a
        # receiver and then mutate it should use this and operate on the
        # returned object — indexing self.receivers twice (once to bound-check,
        # once to mutate) has a TOCTOU window with concurrent remove().
        with self._lock:
            if not 0 <= index < len(self.receivers):
                return None
            return self.receivers[index]

    def add(self, receiver_url):
        # Build the receiver outside the lock — receiver.__init__ calls
        # update(), which does HTTP I/O and can take seconds. Holding the
        # lock across that would block the polling loop's snapshot and
        # any concurrent /rx_params read.
        with self._lock:
            if any(x.station_url == receiver_url for x in self.receivers):
                print("Duplicate receiver, ignoring.")
                return
        new_rx_obj = Receiver(receiver_url)
        new_rx = new_rx_obj.receiver_dict()
        to_table = [new_rx['station_id'], new_rx['station_url'], new_rx['auto'],
                    new_rx['mobile'], new_rx['single'], new_rx['latitude'], new_rx['longitude']]
        command = "INSERT OR IGNORE INTO receivers VALUES (?,?,?,?,?,?,?)"
        self.db.execute(command, [to_table], wait=True)
        self.db.commit(wait=True)
        row = self.db.query_one("SELECT isMobile, isSingle FROM receivers WHERE station_id = ?",
                                [new_rx['station_id']])
        if row is None:
            # INSERT OR IGNORE skipped because some other receiver already
            # had this station_id (URL was new but device reports a colliding
            # station_id). Surface it instead of crashing on row[0].
            print(f"Receiver at {receiver_url} reports station_id "
                  f"{new_rx['station_id']!r}, which is already registered. Ignoring.")
            return
        new_rx_obj.isMobile = bool(row[0])
        new_rx_obj.isSingle = bool(row[1])
        with self._lock:
            # Re-check for duplicates: another thread could have added the
            # same URL while we were doing network I/O above.
            if any(x.station_url == receiver_url for x in self.receivers):
                print("Duplicate receiver, ignoring.")
                return
            self.receivers.append(new_rx_obj)
        print("Created new DF Station at " + receiver_url)

    def remove(self, index):
        with self._lock:
            if not 0 <= index < len(self.receivers):
                return
            station_id = self.receivers[index].station_id
            del self.receivers[index]
        # DB write happens outside the lock — sqlite I/O can take a moment
        # and the in-memory list is already consistent.
        command = "DELETE FROM receivers WHERE station_id=?"
        self.db.execute(command, [(station_id,)], wait=True)
        self.db.commit()

    def read_from_db(self):
        # Loaded once at startup. The previous `except Exception: pass`
        # around the whole loop meant that one bad row killed the load of
        # every subsequent row, *and* that DB-level failures (corrupt
        # sqlite, missing table) silently produced an empty receiver list.
        # Per-row try/except + a print at least makes failures visible while
        # letting the rest of the receivers load.
        try:
            rx_list = self.db.query("SELECT station_url FROM receivers")
        except Exception as ex:
            print(f"Could not read receivers from DB: {type(ex).__name__}: {ex}")
            return
        for x in rx_list:
            try:
                receiver_url = x[0].replace('\n', '')
                self.add(receiver_url)
            except Exception as ex:
                print(f"Failed to load receiver row {x!r}: "
                      f"{type(ex).__name__}: {ex}")

    def save_to_db(self):
        # Snapshot under the lock; do the DB writes outside it so a slow
        # writer thread can't stall add()/remove() on the web side.
        for item in self._snapshot():
            rx = item.receiver_dict()
            to_table = [rx['auto'], rx['mobile'], rx['single'],
                        rx['latitude'], rx['longitude'], rx['station_id']]
            command = '''UPDATE receivers SET
                isAuto=?,
                isMobile=?,
                isSingle=?,
                latitude=?,
                longitude=?
                WHERE station_id = ?'''
            self.db.execute(command, [to_table], wait=True)
        self.db.commit()

    def run_loop(self, config, ms):
        clear(config.debugging)
        dots = 0

        while ms.receiving:
            if not config.debugging:
                print("Receiving" + dots * '.')
                print("Press Control+C to process data and exit.")

            # Take one snapshot per cycle and iterate it everywhere below.
            # Iterating self.receivers directly would race with add()/remove()
            # on the web thread (Python list iterators don't tolerate
            # structural changes mid-iteration). Per-attribute reads through
            # the snapshot are safe because the snapshot pins the *receiver
            # objects*, not their field values — concurrent attribute writes
            # remain individually atomic.
            with self._lock:
                for rx in self.receivers:
                    rx.d_2_last_intersection = []
                receivers_snapshot = list(self.receivers)
                rx_snapshot = list(enumerate(self.receivers))

            # Poll receivers outside the lock — network I/O can take seconds
            # and we don't want to block the web server / CZML generator.
            now = time.time()
            for rx in receivers_snapshot:
                try:
                    if rx.isActive:
                        if rx.error_count > 0 and now < rx.next_retry_time:
                            continue
                        rx.update()
                except IOError:
                    print("Problem connecting to receiver.")

            for rx in receivers_snapshot:
                if not rx.isActive and rx.next_probe_time > 0 and now >= rx.next_probe_time:
                    print(f"Probing deactivated receiver {rx.station_url}...")
                    rx.update()
                    if rx.error_count == 0:
                        rx.isActive = True
                        rx.next_probe_time = 0
                        print(f"Receiver {rx.station_url} reactivated successfully.")
                    else:
                        rx.next_probe_time = now + RECEIVER_PROBE_INTERVAL_S

            for rx in receivers_snapshot:
                is_single_rx = rx.isSingle and rx.isMobile
                if rx.isActive and rx.doa_time > rx.previous_doa_time and (ms.lob_history_enabled or is_single_rx):
                    to_lobs = [rx.doa_time, rx.station_id, rx.latitude,
                               rx.longitude, rx.confidence, rx.power,
                               rx.frequency, rx.doa]
                    command = '''INSERT INTO lobs
                        (time, station_id, latitude, longitude, confidence, power, frequency, lob)
                        VALUES (?,?,?,?,?,?,?,?)'''
                    self.db.execute(command, (to_lobs,), wait=True)
                    rx.previous_doa_time = rx.doa_time

            intersect_list = []
            latest_doa_time = 0
            d2_accum = {i: [] for i, _ in rx_snapshot}

            for x, rx_x in rx_snapshot:
                for y, rx_y in rx_snapshot[:x]:
                    if (rx_x.confidence >= ms.min_conf and
                        rx_y.confidence >= ms.min_conf and
                        rx_x.power >= ms.min_power and
                        rx_y.power >= ms.min_power and
                        abs(rx_x.doa_time - rx_y.doa_time) <= MAX_TIME_DIFF_MS and
                            rx_x.frequency == rx_y.frequency):
                        intersection = plot_intersects(rx_x.latitude, rx_x.longitude,
                                                       rx_x.doa, rx_y.latitude, rx_y.longitude, rx_y.doa)
                        if intersection:
                            print(intersection)
                            latest_doa_time = max(latest_doa_time, rx_x.doa_time, rx_y.doa_time)
                            d2_accum[x].append(v.haversine(
                                rx_x.latitude, rx_x.longitude, *intersection))
                            d2_accum[y].append(v.haversine(
                                rx_y.latitude, rx_y.longitude, *intersection))
                            avg_conf = (rx_x.confidence + rx_y.confidence) / 2.0
                            intersect_list.append([intersection[0], intersection[1], avg_conf])

            with self._lock:
                for i, rx in rx_snapshot:
                    rx.d_2_last_intersection = d2_accum[i]

            if intersect_list:
                intersect_array = np.array(intersect_list)
                avg_coord = np.average(
                    intersect_array[:, 0:3], weights=intersect_array[:, 2], axis=0)
                keep, in_aoi = self.db.check_aoi(*avg_coord[0:2])
                if keep:
                    to_table = [latest_doa_time, round(avg_coord[0], 6), round(avg_coord[1], 6),
                                len(intersect_list), avg_coord[2], in_aoi]
                    command = '''INSERT INTO intersects
                    (time, latitude, longitude, num_parents, confidence, aoi_id)
                    VALUES (?,?,?,?,?,?)'''
                    self.db.execute(command, (to_table,), wait=True)

            for rx in receivers_snapshot:
                if (rx.isSingle and rx.isMobile and rx.isActive and
                    rx.confidence >= ms.min_conf and
                    rx.power >= ms.min_power and
                        rx.doa_time >= rx.previous_doa_time + SINGLE_RX_MIN_TIME_DIFF_MS):
                    current_doa = [rx.doa_time, rx.station_id, rx.latitude,
                                   rx.longitude, rx.confidence, rx.doa]
                    min_time = rx.doa_time - HISTORICAL_LOB_WINDOW_MS
                    lob_array = self.db.query(
                        '''SELECT latitude, longitude, confidence, lob FROM lobs
                         WHERE station_id = ? AND time > ?''',
                        [rx.station_id, min_time])
                    current_time = current_doa[0]
                    lat_rxa = current_doa[2]
                    lon_rxa = current_doa[3]
                    conf_rxa = current_doa[4]
                    doa_rxa = current_doa[5]
                    keep_count = 0
                    if len(lob_array) > 1:
                        for previous in lob_array:
                            lat_rxb = previous[0]
                            lon_rxb = previous[1]
                            conf_rxb = previous[2]
                            doa_rxb = previous[3]
                            spacial_diversity, z = v.inverse(
                                (lat_rxa, lon_rxa), (lat_rxb, lon_rxb))
                            min_diversity = MIN_SPATIAL_DIVERSITY_METERS
                            # angular_diff, not abs() — wrap-aware compass
                            # difference. Plain abs() reports 358° between
                            # bearings 359° and 1° (actually 2° apart),
                            # accepting near-parallel pairs that produce
                            # poor-quality far intersections.
                            if (spacial_diversity > min_diversity and
                                    v.angular_diff_deg(doa_rxa, doa_rxb) > MIN_LOB_PAIR_BEARING_DIFF_DEG):
                                intersection = plot_intersects(lat_rxa, lon_rxa,
                                                               doa_rxa, lat_rxb, lon_rxb, doa_rxb)
                                if intersection:
                                    intersection = list(intersection)
                                    avg_conf = np.mean([conf_rxa, conf_rxb])
                                    intersection.append(avg_conf)
                                    keep, in_aoi = self.db.check_aoi(*intersection[0:2])
                                    if keep:
                                        keep_count += 1
                                        to_table = [current_time, round(intersection[0], 5), round(intersection[1], 5),
                                                    1, intersection[2], in_aoi]
                                        command = '''INSERT INTO intersects
                                        (time, latitude, longitude, num_parents, confidence, aoi_id)
                                        VALUES (?,?,?,?,?,?)'''
                                        self.db.execute(command, (to_table,), wait=True)
                    print(f"Computed and kept {keep_count} intersections.")

            self.db.commit()
            time.sleep(1)
            if dots > 5:
                dots = 1
            else:
                dots += 1
            clear(config.debugging)
