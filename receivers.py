import time
import sqlite3
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
    MIN_SPATIAL_DIVERSITY_METERS, RECEIVER_MAX_RETRIES_TRANSIENT,
    RECEIVER_MAX_RETRIES_PERSISTENT, RECEIVER_BACKOFF_BASE_S,
    RECEIVER_PROBE_INTERVAL_S, clear)
from geo import plot_intersects


_secure_parser = etree.XMLParser(
    resolve_entities=False,
    remove_comments=True,
    dtd_validation=False,
    load_dtd=False
)


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


class receiver:
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
        self.update(first_run=True)

    def update(self, first_run=False):
        try:
            with urllib.request.urlopen(self.station_url, timeout=5) as resp:
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

    latitude = 0.0
    longitude = 0.0
    heading = 0.0
    raw_doa = 0.0
    doa = 0.0
    frequency = 0.0
    power = 0.0
    confidence = 0
    doa_time = 0
    isMobile = False
    isSingle = False
    previous_doa_time = 0
    last_processed_at = 0
    d_2_last_intersection = [LOB_DRAW_DISTANCE_METERS]
    last_error = ""
    next_retry_time = 0
    next_probe_time = 0
    max_retries = 0


class ReceiverManager:
    def __init__(self, db):
        self.db = db
        self.receivers = []
        self._lock = threading.Lock()

    @contextmanager
    def lock(self):
        with self._lock:
            yield

    def add(self, receiver_url):
        try:
            if any(x.station_url == receiver_url for x in self.receivers):
                print("Duplicate receiver, ignoring.")
            else:
                self.receivers.append(receiver(receiver_url))
                new_rx = self.receivers[-1].receiver_dict()
                to_table = [new_rx['station_id'], new_rx['station_url'], new_rx['auto'],
                            new_rx['mobile'], new_rx['single'], new_rx['latitude'], new_rx['longitude']]
                command = "INSERT OR IGNORE INTO receivers VALUES (?,?,?,?,?,?,?)"
                self.db.execute(command, [to_table], wait=True)
                self.db.commit(wait=True)
                row = self.db.query_one("SELECT isMobile, isSingle FROM receivers WHERE station_id = ?",
                                        [new_rx['station_id']])
                self.receivers[-1].isMobile = bool(row[0])
                self.receivers[-1].isSingle = bool(row[1])
                print("Created new DF Station at " + receiver_url)
        except AttributeError:
            pass

    def remove(self, index):
        command = "DELETE FROM receivers WHERE station_id=?"
        self.db.execute(command, [(self.receivers[index].station_id,)], wait=True)
        self.db.commit()
        del self.receivers[index]

    def read_from_db(self):
        try:
            rx_list = self.db.query("SELECT station_url FROM receivers")
            for x in rx_list:
                receiver_url = x[0].replace('\n', '')
                self.add(receiver_url)
        except Exception:
            pass

    def save_to_db(self):
        for item in self.receivers:
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

        conn = sqlite3.connect(config.database_name)
        c = conn.cursor()

        while ms.receiving:
            if not config.debugging:
                print("Receiving" + dots * '.')
                print("Press Control+C to process data and exit.")

            now = time.time()
            for rx in self.receivers:
                try:
                    if rx.isActive:
                        if rx.error_count > 0 and now < rx.next_retry_time:
                            continue
                        rx.update()
                except IOError:
                    print("Problem connecting to receiver.")

            for rx in self.receivers:
                if not rx.isActive and rx.next_probe_time > 0 and now >= rx.next_probe_time:
                    print(f"Probing deactivated receiver {rx.station_url}...")
                    rx.update()
                    if rx.error_count == 0:
                        rx.isActive = True
                        rx.next_probe_time = 0
                        print(f"Receiver {rx.station_url} reactivated successfully.")
                    else:
                        rx.next_probe_time = now + RECEIVER_PROBE_INTERVAL_S

            with self._lock:
                for rx in self.receivers:
                    rx.d_2_last_intersection = []
                rx_snapshot = [(i, rx) for i, rx in enumerate(self.receivers)]

            for rx in self.receivers:
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

            for rx in self.receivers:
                if (rx.isSingle and rx.isMobile and rx.isActive and
                    rx.confidence >= ms.min_conf and
                    rx.power >= ms.min_power and
                        rx.doa_time >= rx.previous_doa_time + SINGLE_RX_MIN_TIME_DIFF_MS):
                    current_doa = [rx.doa_time, rx.station_id, rx.latitude,
                                   rx.longitude, rx.confidence, rx.doa]
                    min_time = rx.doa_time - HISTORICAL_LOB_WINDOW_MS
                    c.execute('''SELECT latitude, longitude, confidence, lob FROM lobs
                     WHERE station_id = ? AND time > ?''', [rx.station_id, min_time])
                    lob_array = c.fetchall()
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
                            if (spacial_diversity > min_diversity and
                                    abs(doa_rxa - doa_rxb) > 5):
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

        conn.close()
