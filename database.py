import sqlite3
import threading
import queue

import vincenty as v
from config import AppConfig


class Database:
    def __init__(self, config):
        self.config = config
        self._edit_q = queue.Queue()
        self._return_q = queue.Queue()
        self._aoi_cache = None
        self._aoi_cache_lock = threading.Lock()

    def execute(self, command, items, wait=False):
        self._edit_q.put((command, items, wait))
        if wait:
            return self._return_q.get(timeout=1)

    def commit(self, wait=False):
        self._edit_q.put(("done", None, wait))
        if wait:
            return self._return_q.get(timeout=1)

    def close(self):
        self._edit_q.put(("close", None, True))
        self._return_q.get(timeout=1)

    def query(self, sql, params=None):
        conn = sqlite3.connect(self.config.database_name)
        c = conn.cursor()
        c.execute(sql, params or [])
        result = c.fetchall()
        conn.close()
        return result

    def query_one(self, sql, params=None):
        conn = sqlite3.connect(self.config.database_name)
        c = conn.cursor()
        c.execute(sql, params or [])
        result = c.fetchone()
        conn.close()
        return result

    def writer_loop(self):
        conn = sqlite3.connect(self.config.database_name)
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

        for col, col_type in [("power", "REAL"), ("frequency", "REAL")]:
            try:
                c.execute(f"ALTER TABLE lobs ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass

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
            command, items, reply = self._edit_q.get()
            if command == "done":
                conn.commit()
                if reply:
                    self._return_q.put(True)
            elif command == "close":
                conn.commit()
                conn.close()
                if reply:
                    self._return_q.put(True)
                break
            else:
                c.executemany(command, items)
                if reply:
                    self._return_q.put(True)

    def invalidate_aoi_cache(self):
        with self._aoi_cache_lock:
            self._aoi_cache = None

    def fetch_aoi_data(self):
        with self._aoi_cache_lock:
            if self._aoi_cache is not None:
                return self._aoi_cache
            result = self.query('SELECT * FROM interest_areas')
            self._aoi_cache = result
            return result

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
        self.commit()
        self.invalidate_aoi_cache()

    def purge_database(self, area_type, lat, lon, radius):
        intersect_list = self.query("SELECT latitude, longitude, id FROM intersects")
        delete_these = []
        purge_count = 0
        for x in intersect_list:
            if area_type == "exclusion":
                distance = v.inverse(x[0:2], (lat, lon))[0]
                if distance < radius:
                    delete_these.append((x[2],))
                    purge_count += 1
        command = "DELETE FROM intersects WHERE id=?"
        self.execute(command, delete_these, wait=False)
        self.commit()
        print(f"I purged {purge_count} intersects.")

    def run_aoi_rules(self):
        purged = 0
        sorted_count = 0
        aoi_list = self.fetch_aoi_data()
        intersect_list = self.query('SELECT id, latitude, longitude FROM intersects')
        n_aoi = self.query_one('SELECT COUNT(*) FROM interest_areas WHERE aoi_type="aoi"')[0]
        starttime = __import__('time').time()
        del_list = []
        keep_list = []
        if n_aoi == 0:
            command = "UPDATE intersects SET aoi_id=?"
            self.execute(command, (-1,), wait=True)
            self.commit(wait=True)
        else:
            for point in intersect_list:
                keep_me = []
                in_aoi = None
                id, lat, lon = point
                for x in aoi_list:
                    distance = v.haversine(x[2], x[3], lat, lon)
                    if x[1] == "exclusion":
                        if distance < x[4]:
                            keep_me = [False]
                            break
                    elif x[1] == "aoi":
                        if distance < x[4]:
                            sorted_count += 1
                            keep_me.append(True)
                            in_aoi = x[0]
                        else:
                            keep_me.append(False)
                if not any(keep_me):
                    del_list.append((id,))
                    purged += 1
                else:
                    keep_list.append((in_aoi, id))

        command = "DELETE from intersects WHERE id=?"
        self.execute(command, del_list, wait=True)
        self.commit()

        command = "UPDATE intersects SET aoi_id=? WHERE id=?"
        self.execute(command, keep_list, wait=True)
        self.commit()

        self.invalidate_aoi_cache()
        stoptime = __import__('time').time()
        print(f"Purged {purged} intersections and sorted {sorted_count} intersections into {n_aoi} AOIs in {stoptime - starttime} seconds.")
        return "OK"
