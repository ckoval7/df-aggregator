import logging
import sqlite3
import threading
import queue
import time

import numpy as np

import vincenty as v
from config import AppConfig

log = logging.getLogger(__name__)

# WGS-84 equatorial radius — same constant used by vincenty.haversine, kept
# local so the vectorized path doesn't reach into another module's globals.
_EARTH_RADIUS_M = 6378137.0


class Database:
    EDIT_QUEUE_MAXSIZE = 1000

    def __init__(self, config):
        self.config = config
        self._edit_q = queue.Queue(maxsize=self.EDIT_QUEUE_MAXSIZE)
        self._aoi_cache = None
        self._aoi_cache_lock = threading.Lock()

    def _submit(self, command, items, wait):
        reply_q = queue.Queue(maxsize=1) if wait else None
        self._edit_q.put((command, items, reply_q))
        if wait:
            result = reply_q.get()
            if isinstance(result, BaseException):
                raise result
            return result

    def execute(self, command, items, wait=False):
        return self._submit(command, items, wait)

    def commit(self, wait=False):
        return self._submit("done", None, wait)

    def close(self):
        self._submit("close", None, wait=True)

    # busy_timeout is per-connection: every short-lived reader needs it set
    # or only the writer benefits. WAL and synchronous=NORMAL are set once
    # by the writer at startup; WAL persists in the DB file so readers see
    # it without re-asking, and synchronous only affects writes.
    _BUSY_TIMEOUT_MS = 5000

    def _connect_reader(self):
        conn = sqlite3.connect(self.config.database_name)
        conn.execute(f"PRAGMA busy_timeout = {self._BUSY_TIMEOUT_MS}")
        return conn

    # Reads open a short-lived connection per call rather than reusing one:
    # sqlite3 connections are not safe to share across threads, and the writer
    # thread already owns a long-lived write connection in writer_loop().
    def query(self, sql, params=None):
        conn = self._connect_reader()
        c = conn.cursor()
        c.execute(sql, params or [])
        result = c.fetchall()
        conn.close()
        return result

    def query_one(self, sql, params=None):
        conn = self._connect_reader()
        c = conn.cursor()
        c.execute(sql, params or [])
        result = c.fetchone()
        conn.close()
        return result

    def writer_loop(self):
        conn = sqlite3.connect(self.config.database_name)
        # WAL: writers don't block readers, readers don't block writers.
        # Persists in the DB file across opens so future connections inherit
        # it. synchronous=NORMAL: durable across app crashes, only loses
        # in-flight commits on OS-level power loss (vs. FULL's per-commit
        # fsync). busy_timeout: wait up to 5s on contention before raising
        # SQLITE_BUSY — replaces the default "fail immediately" behavior.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute(f"PRAGMA busy_timeout = {self._BUSY_TIMEOUT_MS}")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS receivers (
            station_id TEXT UNIQUE,
            station_url TEXT,
            isAuto INTEGER,
            isMobile INTEGER,
            isSingle INTEGER,
            latitude REAL,
            longitude REAL)
        ''')
        c.execute('''CREATE TABLE IF NOT EXISTS interest_areas (
            uid INTEGER,
            aoi_type TEXT,
            latitude REAL,
            longitude REAL,
            radius INTEGER)
        ''')
        c.execute('''CREATE TABLE IF NOT EXISTS intersects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time INTEGER,
            latitude REAL,
            longitude REAL,
            num_parents INTEGER,
            confidence INTEGER,
            aoi_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS lobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time INTEGER,
            station_id TEXT,
            latitude REAL,
            longitude REAL,
            confidence INTEGER,
            power REAL,
            frequency REAL,
            lob REAL)''')

        # Schema evolution. The previous pattern was "try ALTER, swallow any
        # OperationalError" — that works in practice but quietly hides
        # unrelated failures (locked DB, missing table, syntax errors in a
        # future migration). Introspect explicitly via PRAGMA table_info and
        # only ALTER columns that are actually missing. If/when migrations
        # get DAG-shaped (column drops, conditional backfills, downgrade
        # paths), graduate this to a PRAGMA user_version framework — but
        # there's only ever been one migration event in this DB's lifetime
        # and a framework now would be speculative scaffolding.
        existing_lobs_cols = {row[1] for row in c.execute("PRAGMA table_info(lobs)")}
        for col, col_type in [("power", "REAL"), ("frequency", "REAL")]:
            if col not in existing_lobs_cols:
                c.execute(f"ALTER TABLE lobs ADD COLUMN {col} {col_type}")

        c.execute('''CREATE INDEX IF NOT EXISTS idx_intersects_aoi_confidence
            ON intersects(aoi_id, confidence DESC)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_intersects_time
            ON intersects(time)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_lobs_station_time
            ON lobs(station_id, time)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_lobs_time
            ON lobs(time)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_interest_areas_uid
            ON interest_areas(uid)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_interest_areas_type
            ON interest_areas(aoi_type)''')
        conn.commit()

        while True:
            command, items, reply_q = self._edit_q.get()
            try:
                if command == "done":
                    conn.commit()
                elif command == "close":
                    conn.commit()
                    conn.close()
                    if reply_q is not None:
                        reply_q.put(True)
                    break
                else:
                    c.executemany(command, items)
            except Exception as ex:
                log.error("Database writer error on '%s': %s: %s",
                          command[:60] if isinstance(command, str) else command,
                          type(ex).__name__, ex)
                if reply_q is not None:
                    reply_q.put(ex)
                continue
            if reply_q is not None:
                reply_q.put(True)

    def invalidate_aoi_cache(self):
        with self._aoi_cache_lock:
            self._aoi_cache = None

    def commit_and_invalidate_aoi_cache(self, wait=True):
        # Reads (fetch_aoi_data) hit a fresh short-lived sqlite connection.
        # If we invalidate before the writer thread has actually committed,
        # the next reader can re-populate the cache from a pre-commit snapshot
        # and pin stale data until the *next* AOI mutation. Wait for the
        # writer to commit, then invalidate.
        self.commit(wait=wait)
        self.invalidate_aoi_cache()

    def fetch_aoi_data(self):
        with self._aoi_cache_lock:
            if self._aoi_cache is not None:
                # Return a shallow copy so iteration order can't be perturbed
                # by a concurrent invalidation, and so a caller that mutates
                # the outer list (append/sort) doesn't corrupt the cache.
                # Inner rows are sqlite tuples, already immutable.
                return list(self._aoi_cache)
            result = self.query('SELECT * FROM interest_areas')
            self._aoi_cache = result
            return list(result)

    def check_aoi(self, lat, lon):
        keep_list = []
        in_aoi = None
        aoi_data = self.fetch_aoi_data()
        n_aoi = sum(1 for x in aoi_data if x[1] == "aoi")
        if n_aoi == 0:
            keep_list.append(True)
            in_aoi = -1
        for x in aoi_data:
            aoi_type = x[1]
            distance = v.haversine(x[2], x[3], lat, lon)
            if aoi_type == "exclusion":
                if distance < x[4]:
                    return False, in_aoi
            elif aoi_type == "aoi":
                if distance < x[4]:
                    keep_list.append(True)
                    in_aoi = x[0]
                else:
                    keep_list.append(False)
        return any(keep_list), in_aoi

    def add_aoi(self, aoi_type, lat, lon, radius):
        prev_uid = self.query_one('SELECT MAX(uid) from interest_areas')[0]
        uid = (prev_uid + 1) if prev_uid is not None else 0
        to_table = [uid, aoi_type, lat, lon, radius]
        command = 'INSERT INTO interest_areas VALUES (?,?,?,?,?)'
        self.execute(command, [to_table], wait=True)
        self.commit_and_invalidate_aoi_cache()

    def purge_database(self, area_type, lat, lon, radius):
        # Only "exclusion" zones have a defined purge semantic (drop every
        # intersection inside the zone). The UI only renders the purge button
        # for exclusions (see static/interest_areas.js), so any other value
        # arriving here means a misrouted call — fail loudly instead of
        # silently iterating to a zero-row delete.
        if area_type != "exclusion":
            raise ValueError(
                f"purge_database only supports area_type='exclusion', got {area_type!r}")
        intersect_list = self.query("SELECT latitude, longitude, id FROM intersects")
        delete_these = []
        for x in intersect_list:
            distance = v.inverse(x[0:2], (lat, lon))[0]
            if distance < radius:
                delete_these.append((x[2],))
        if delete_these:
            self.execute("DELETE FROM intersects WHERE id=?", delete_these, wait=False)
            self.commit()
        log.info("Purged %d intersects.", len(delete_these))

    def run_aoi_rules(self):
        # Re-assign every intersection's aoi_id according to the current AOI
        # rules; delete anything that lands inside an exclusion zone or
        # outside every AOI. Policy preserved from the previous scalar loop:
        #   - any exclusion hit  -> delete
        #   - no AOI matches     -> delete
        #   - otherwise          -> keep, assign uid of the LAST AOI in
        #                           iteration order whose circle contains it
        # The "last match wins" semantic is preserved because that's what
        # was happening before; if you want a smaller-radius-wins or
        # uid-stable policy, that's a behavior change, not a perf change.
        aoi_list = self.fetch_aoi_data()
        intersect_list = self.query('SELECT id, latitude, longitude FROM intersects')
        n_aoi = self.query_one('SELECT COUNT(*) FROM interest_areas WHERE aoi_type="aoi"')[0]
        starttime = time.time()
        del_list = []
        keep_list = []
        sorted_count = 0
        purged = 0

        if n_aoi == 0:
            self.execute("UPDATE intersects SET aoi_id=?", (-1,), wait=True)
            self.commit_and_invalidate_aoi_cache()
            stoptime = time.time()
            log.info("Purged 0 intersections and sorted 0 intersections into 0 AOIs in %.3f seconds.",
                     stoptime - starttime)
            return "OK"

        if intersect_list:
            # Shape arrays once: points are (N,), AOIs are (M,). Distances
            # come out as an (N, M) matrix from a single broadcast haversine.
            points = np.asarray(intersect_list, dtype=np.float64)
            ids = points[:, 0].astype(np.int64)
            p_lat = np.radians(points[:, 1])
            p_lon = np.radians(points[:, 2])

            aoi_arr = np.asarray(
                [(a[0], a[2], a[3], a[4]) for a in aoi_list], dtype=np.float64)
            aoi_uids = aoi_arr[:, 0].astype(np.int64)
            a_lat = np.radians(aoi_arr[:, 1])
            a_lon = np.radians(aoi_arr[:, 2])
            a_radius = aoi_arr[:, 3]
            aoi_types = np.array([a[1] for a in aoi_list])

            # Vectorized haversine, (N, M) — broadcasts points down rows,
            # AOIs across columns. Same formula as vincenty.haversine.
            dlat = a_lat[None, :] - p_lat[:, None]
            dlon = a_lon[None, :] - p_lon[:, None]
            sin_dlat = np.sin(dlat / 2.0)
            sin_dlon = np.sin(dlon / 2.0)
            h = (sin_dlat * sin_dlat +
                 np.cos(p_lat)[:, None] * np.cos(a_lat)[None, :] *
                 sin_dlon * sin_dlon)
            # clip to defend against tiny FP overshoot above 1.0
            distances = 2.0 * _EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(h, 0.0, 1.0)))

            inside = distances < a_radius[None, :]
            is_excl = (aoi_types == "exclusion")
            is_aoi = (aoi_types == "aoi")

            inside_any_exclusion = (inside & is_excl[None, :]).any(axis=1)
            aoi_hits = inside & is_aoi[None, :]
            inside_any_aoi = aoi_hits.any(axis=1)

            keep_mask = inside_any_aoi & ~inside_any_exclusion

            # last-match-wins: pick the largest column index where aoi_hits
            # is True, then map back to that AOI's uid.
            col_indices = np.arange(aoi_hits.shape[1])
            last_hit_col = np.where(
                aoi_hits, col_indices[None, :], -1).max(axis=1)
            last_hit_uid = np.where(last_hit_col >= 0, aoi_uids[last_hit_col.clip(min=0)], -1)

            kept_ids = ids[keep_mask]
            kept_uids = last_hit_uid[keep_mask]
            del_ids = ids[~keep_mask]

            keep_list = list(zip(kept_uids.tolist(), kept_ids.tolist()))
            del_list = [(int(i),) for i in del_ids.tolist()]
            sorted_count = int(aoi_hits.sum())
            purged = int(del_ids.size)

        if del_list:
            self.execute("DELETE from intersects WHERE id=?", del_list, wait=True)
            self.commit()
        if keep_list:
            self.execute("UPDATE intersects SET aoi_id=? WHERE id=?", keep_list, wait=True)
        self.commit_and_invalidate_aoi_cache()
        stoptime = time.time()
        log.info("Purged %d intersections and sorted %d intersections into %d AOIs in %.3f seconds.",
                 purged, sorted_count, n_aoi, stoptime - starttime)
        return "OK"
