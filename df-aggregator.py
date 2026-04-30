#!/usr/bin/env python3

# df-aggregator, networked radio direction finding software.
#     Copyright (C) 2020 Corey Koval
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>.

from dataclasses import dataclass
import gzip
import vincenty as v
import numpy as np
from scipy.spatial.distance import cdist
import math
import time
from datetime import datetime, timezone
import sqlite3
import threading
import signal
import json
import urllib.request
from colorsys import hsv_to_rgb
import argparse
from os import kill, getpid
from lxml import etree
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import minmax_scale
from geojson import MultiPoint, Feature, FeatureCollection
from czml3 import Packet, Document, CZML_VERSION
from czml3.properties import Position, PositionList, Polyline, PolylineMaterial, PolylineOutlineMaterial, PolylineDashMaterial, Color, Clock
from czml3.types import TimeInterval
import queue
from multiprocessing import Process, Queue, set_start_method
from bottle import route, run, request, get, put, response, redirect, template, static_file, app as bottle_app
from bottle.ext.websocket import GeventWebSocketServer, websocket

from sys import version_info
if (version_info.major != 3 or version_info.minor < 6):
    print("Looks like you're running python version " +
          str(version_info.major) + "." +
          str(version_info.minor) + ", which is no longer supported.")
    print("Your python version is out of date, please update to 3.6 or newer.")
    quit()

# Set multiprocessing start method to 'forkserver' to avoid fork() deadlock warnings
# when creating processes in a multi-threaded environment (web server, database writer threads)
# 'forkserver' is safer than 'fork' but more compatible than 'spawn' for this use case
try:
    set_start_method('forkserver')
except RuntimeError:
    # Start method has already been set, which is fine
    pass


###############################################
# Creates a secure XML parser to prevent XXE
# (XML External Entity) attacks.
###############################################
_secure_parser = etree.XMLParser(
    resolve_entities=False,
    remove_comments=True,
    dtd_validation=False,
    load_dtd=False
)


DBSCAN_Q = Queue()
DATABASE_EDIT_Q = queue.Queue()
DATABASE_RETURN = queue.Queue()

dbscan_lock = threading.Lock()

###############################################
# Thread synchronization lock for receiver data
# Prevents race conditions when reading/writing
# receiver state from multiple threads
###############################################
rx_lock = threading.Lock()

_aoi_cache = None
_aoi_cache_lock = threading.Lock()

###############################################
# Application Constants
###############################################

# Distance Constants (meters)
LOB_DRAW_DISTANCE_METERS = 40000          # Draw distance for Lines of Bearing on map
HEADING_DRAW_DISTANCE_METERS = 20000      # Draw distance for heading indicators
MAX_INTERSECTION_DISTANCE_METERS = 100000 # Maximum distance for valid intersections
MIN_SPATIAL_DIVERSITY_METERS = 500        # Minimum movement for single-receiver triangulation

# Time Constants (milliseconds)
MAX_TIME_DIFF_MS = 5000                   # Maximum time difference for intersection matching (5 seconds)
SINGLE_RX_MIN_TIME_DIFF_MS = 10000        # Minimum time between single-receiver samples (10 seconds)
HISTORICAL_LOB_WINDOW_MS = 1200000        # Historical LOB window for single-receiver mode (20 minutes)

# Database Query Constants
MAX_INTERSECTS_PER_AOI = 25000            # Maximum intersections to load per AOI for clustering
AUTOEPS_SAMPLE_SIZE = 2000                # Sample size for automatic epsilon calculation

# Processing Constants
BEARING_CHECK_TOLERANCE_DEG = 5            # Max deviation when validating intersection bearing
AUTOEPS_SLOPE_THRESHOLD = 0.003           # Slope threshold for epsilon auto-calculation
GAUSSIAN_ELLIPSE_SIGMA = 3.0              # Standard deviations for confidence ellipse (3-sigma = 99.7%)


receivers = []


@dataclass
class math_settings:
    eps: str
    min_samp: str
    min_conf: float
    min_power: float
    receiving: bool = True
    plotintersects: bool = False
    lob_history_enabled: bool = True


################################################
# Stores all variables pertaining to a reveiver.
# Also updates receiver variable upon request.
################################################
class receiver:
    def __init__(self, station_url):
        self.station_url = station_url
        self.isAuto = True
        self.isActive = True
        self.flipped = False
        self.inverted = True
        self.update(first_run=True)

    # Updates receiver from the remote URL
    def update(self, first_run=False):
        try:
            # Fetch XML from remote URL, then parse with secure parser to prevent XXE attacks
            with urllib.request.urlopen(self.station_url) as response:
                xml_data = response.read()
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
        except KeyboardInterrupt:
            finish()
        except Exception as ex:
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
            print(ex)
            print(
                f"Problem connecting to {self.station_url}, receiver deactivated. Reactivate in WebUI.")
            # raise IOError

    # Returns receivers properties as a dict, useful for passing data to the WebUI
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

    # Class-level defaults — safe because update() and run_receiver() reassign
    # per-instance before any shared-state read can occur.
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


###############################################
# Converts Lat/Lon to polar coordinates
###############################################
def plot_polar(lat_a, lon_a, lat_a2, lon_a2):
    # Convert points in great circle 1, degrees to radians
    p1_lat1_rad = math.radians(lat_a)
    p1_long1_rad = math.radians(lon_a)
    p1_lat2_rad = math.radians(lat_a2)
    p1_long2_rad = math.radians(lon_a2)

    # Put in polar coordinates
    x1 = math.cos(p1_lat1_rad) * math.cos(p1_long1_rad)
    y1 = math.cos(p1_lat1_rad) * math.sin(p1_long1_rad)
    z1 = math.sin(p1_lat1_rad)
    x2 = math.cos(p1_lat2_rad) * math.cos(p1_long2_rad)
    y2 = math.cos(p1_lat2_rad) * math.sin(p1_long2_rad)
    z2 = math.sin(p1_lat2_rad)

    return ([x1, y1, z1], [x2, y2, z2])


#####################################################
# Find line of intersection between two great circles
#####################################################
def plot_intersects(lat_a, lon_a, doa_a, lat_b, lon_b, doa_b, max_distance=MAX_INTERSECTION_DISTANCE_METERS):
    # plot another point on the lob
    # v.direct(lat_a, lon_a, doa_a, d)
    # returns (lat_a2, lon_a2)

    # Get normal to planes containing great circles
    # np.cross product of vector to each point from the origin
    coord_a2 = v.direct(lat_a, lon_a, doa_a, LOB_DRAW_DISTANCE_METERS)
    coord_b2 = v.direct(lat_b, lon_b, doa_b, LOB_DRAW_DISTANCE_METERS)
    plane_a = plot_polar(lat_a, lon_a, *coord_a2)
    plane_b = plot_polar(lat_b, lon_b, *coord_b2)
    N1 = np.cross(plane_a[0], plane_a[1])
    N2 = np.cross(plane_b[0], plane_b[1])

    # Find line of intersection between two planes
    L = np.cross(N1, N2)
    # Find two intersection points
    X1 = L / np.sqrt(L[0]**2 + L[1]**2 + L[2]**2)
    X2 = -X1

    def mag(q):
        return np.sqrt(np.vdot(q, q))
    dist1 = mag(X1 - plane_a[0])
    dist2 = mag(X2 - plane_a[0])
    # return the (lon_lat pair of the closer intersection)
    if dist1 < dist2:
        i_lat = math.asin(X1[2]) * 180. / np.pi
        i_long = math.atan2(X1[1], X1[0]) * 180. / np.pi
    else:
        i_lat = math.asin(X2[2]) * 180. / np.pi
        i_long = math.atan2(X2[1], X2[0]) * 180. / np.pi

    check_bearing = v.get_heading((lat_a, lon_a), (i_lat, i_long))

    if abs(check_bearing - doa_a) < BEARING_CHECK_TOLERANCE_DEG:
        km = v.inverse([lat_a, lon_a], [i_lat, i_long])
        if km[0] < max_distance:
            return (i_lat, i_long)

    return None


#######################################################################
# We start this in it's own process do it doesn't eat all of your RAM.
# This becomes noticable at over 10k intersections.
#######################################################################
def do_dbscan(X, epsilon, minsamp, result_queue):
    db = DBSCAN(eps=epsilon, min_samples=minsamp).fit(X)
    result_queue.put(db.labels_)


####################################
# Autocalculate the best eps value.
####################################
def autoeps_calc(X):
    X = X[:min(AUTOEPS_SAMPLE_SIZE, len(X)):2]
    if len(X) < 2:
        return 0

    dist_matrix = cdist(X, X)
    np.fill_diagonal(dist_matrix, np.inf)
    k = min(3, len(X) - 1)
    nearest_k = np.sort(dist_matrix, axis=1)[:, :k]
    sorted_distances = np.sort(nearest_k.ravel())

    slopes = np.diff(sorted_distances)
    steep = np.where(slopes > AUTOEPS_SLOPE_THRESHOLD)[0]
    if len(steep) > 0:
        return sorted_distances[steep[0]]
    return 0


###############################################
# Computes DBSCAN Alorithm is applicable,
# finds the mean of a cluster of intersections.
###############################################
def process_data(database_name, epsilon, min_samp):
    n_std = GAUSSIAN_ELLIPSE_SIGMA
    intersect_list = []
    likely_location = []
    ellipsedata = []
    # Short-lived read-only connection; opened per-request intentionally to avoid
    # holding a connection across the long-lived web server thread.
    conn = sqlite3.connect(database_name)
    curs = conn.cursor()
    curs.execute('SELECT uid FROM interest_areas WHERE aoi_type="aoi"')
    aoi_list = [item for sublist in curs.fetchall() for item in sublist]
    aoi_list.append(-1)

    for aoi in aoi_list:
        print(f"Checking AOI {aoi}.")
        curs.execute('''SELECT longitude, latitude, time FROM intersects
            WHERE aoi_id=? ORDER BY confidence DESC LIMIT ?''', [aoi, MAX_INTERSECTS_PER_AOI])
        intersect_array = np.array(curs.fetchall())
        if intersect_array.size != 0:
            if epsilon != "0":
                X = StandardScaler().fit_transform(intersect_array[:, 0:2])
                n_points = len(X)

                if isinstance(min_samp, str):
                    if min_samp == "auto":
                        aoi_min_samp = max(3, round(0.05 * n_points))
                    elif min_samp.isnumeric():
                        aoi_min_samp = max(3, int(min_samp))
                    else:
                        continue
                else:
                    aoi_min_samp = max(3, int(min_samp))

                if epsilon == "auto":
                    aoi_eps = autoeps_calc(X)
                    print(f"min_samp: {aoi_min_samp}, eps: {aoi_eps}")
                    if aoi_eps <= 0:
                        print("Could not determine a valid epsilon, skipping clustering for this AOI.")
                        continue
                else:
                    try:
                        aoi_eps = float(epsilon)
                    except (ValueError, TypeError):
                        continue

                print(f"Computing Clusters from {n_points} intersections.")
                with dbscan_lock:
                    while not DBSCAN_Q.empty():
                        try:
                            DBSCAN_Q.get_nowait()
                        except Exception:
                            break
                    starttime = time.time()
                    db = Process(target=do_dbscan, args=(X, aoi_eps, aoi_min_samp, DBSCAN_Q))
                    db.daemon = True
                    db.start()
                    try:
                        labels = DBSCAN_Q.get(timeout=10)
                    except Exception:
                        print("DBSCAN took too long, terminated.")
                        db.terminate()
                        db.join(timeout=5)
                        db.close()
                        return likely_location, intersect_list, ellipsedata
                    db.join(timeout=5)
                    if db.is_alive():
                        db.terminate()
                        db.join(timeout=5)
                    db.close()

                stoptime = time.time()
                print(
                    f"DBSCAN took {stoptime - starttime} seconds to compute the clusters.")

                intersect_array = np.column_stack((intersect_array, labels))

                # Number of clusters in labels, ignoring noise if present.
                n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
                n_noise_ = list(labels).count(-1)
                clear(debugging)
                print('Number of clusters: %d' % n_clusters_)
                print('Outliers Removed: %d' % n_noise_)

                for x in range(n_clusters_):
                    mask = labels == x
                    cluster = intersect_array[mask, 0:3]
                    clustermean = np.mean(cluster[:, 0:2], axis=0)
                    likely_location.append(clustermean.tolist())
                    cov_deg = np.cov(cluster[:, 0], cluster[:, 1])
                    if (cov_deg[0, 0] == 0.0 and cov_deg[1, 1] == 0.0):
                        if debugging:
                            print("Unable to resolve ellipse.")
                        continue

                    center_latlon = clustermean.tolist()[::-1]
                    m_per_deg_lon = v.inverse(center_latlon,
                        (clustermean[1], clustermean[0] + 1))[0]
                    m_per_deg_lat = v.inverse(center_latlon,
                        (clustermean[1] + 1, clustermean[0]))[0]
                    S = np.diag([m_per_deg_lon, m_per_deg_lat])
                    cov_m = S @ cov_deg @ S

                    eigenvalues, eigenvectors = np.linalg.eigh(cov_m)
                    semi_major_m = np.sqrt(eigenvalues[1]) * n_std
                    semi_minor_m = np.sqrt(eigenvalues[0]) * n_std
                    major_vec = eigenvectors[:, 1]
                    rotation = math.atan2(major_vec[1], major_vec[0])

                    ellipsedata.append(
                        [semi_major_m, semi_minor_m, rotation, *clustermean.tolist()])

                for x in likely_location:
                    print(x[::-1])

            for x in intersect_array:
                try:
                    if x[-1] >= 0:
                        intersect_list.append(x[0:3].tolist())
                except IndexError:
                    intersect_list.append(x.tolist())

        else:
            print(f"No Intersections in AOI {aoi}.")
    conn.close()
    return likely_location, intersect_list, ellipsedata


#######################################################################
# Checks interesections stored in the database against a lat/lon/radius
# and removes items inside exclusion areas.
#######################################################################
def purge_database(area_type, lat, lon, radius):
    conn = sqlite3.connect(database_name)
    c = conn.cursor()
    c.execute("SELECT latitude, longitude, id FROM intersects")
    intersect_list = c.fetchall()
    conn.close()
    delete_these = []
    purge_count = 0
    for x in intersect_list:
        if area_type == "exclusion":
            distance = v.inverse(x[0:2], (lat, lon))[0]
            if distance < radius:
                delete_these.append((x[2],))
                purge_count += 1

    command = "DELETE FROM intersects WHERE id=?"
    DATABASE_EDIT_Q.put((command, delete_these, False))
    DATABASE_EDIT_Q.put(("done", None, False))
    print(f"I purged {purge_count} intersects.")


###############################################
# Checks interesections stored in the database
# against a lat/lon/radius and removes items
# that don't match the rules.
###############################################
@get("/run_all_aoi_rules")
def run_aoi_rules():
    purged = 0
    sorted = 0
    aoi_list = fetch_aoi_data()
    conn = sqlite3.connect(database_name)
    c = conn.cursor()
    c.execute('SELECT id, latitude, longitude FROM intersects')
    intersect_list = c.fetchall()
    c.execute('SELECT COUNT(*) FROM interest_areas WHERE aoi_type="aoi"')
    n_aoi = c.fetchone()[0]
    conn.close()
    starttime = time.time()
    del_list = []
    keep_list = []
    if n_aoi == 0:
        command = "UPDATE intersects SET aoi_id=?"
        DATABASE_EDIT_Q.put((command, (-1,), True))
        DATABASE_EDIT_Q.put(("done", None, False))
        DATABASE_RETURN.get(timeout=1)
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
                        sorted += 1
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
    DATABASE_EDIT_Q.put((command, del_list, True))
    DATABASE_RETURN.get()
    DATABASE_EDIT_Q.put(("done", None, False))

    command = "UPDATE intersects SET aoi_id=? WHERE id=?"
    DATABASE_EDIT_Q.put((command, keep_list, True))
    DATABASE_RETURN.get()
    DATABASE_EDIT_Q.put(("done", None, False))

    stoptime = time.time()
    print(f"Purged {purged} intersections and sorted {sorted} intersections into {n_aoi} AOIs in {stoptime - starttime} seconds.")
    return "OK"


###############################################
# Writes a geojson file upon request.
###############################################
def write_geojson(best_point, all_the_points):
    all_pt_style = {"name": "Various Intersections", "marker-color": "#FF0000"}
    best_pt_style = {"name": "Most Likely TX Location",
                     "marker-color": "#00FF00"}
    if all_the_points is not None:
        all_the_points = Feature(
            properties=all_pt_style, geometry=MultiPoint(tuple(all_the_points)))
        with open(geofile, "w") as file1:
            if best_point is not None:
                best_point = Feature(properties=best_pt_style, geometry=MultiPoint(
                    tuple(best_point)))
                file1.write(str(FeatureCollection(
                    [best_point, all_the_points])))
            else:
                file1.write(str(FeatureCollection([all_the_points])))
        print(f"Wrote file {geofile}")


###############################################
# Writes output.czml used by the WebUI
###############################################
def write_czml(best_point, all_the_points, ellipsedata, plotallintersects, eps):
    point_properties = {
        "pixelSize": 5.0,
        "heightReference": {"heightReference": "CLAMP_TO_GROUND"}
    }
    best_point_properties = {
        "pixelSize": 12.0,
        "heightReference": {"heightReference": "CLAMP_TO_GROUND"},
        "color": {
            "rgba": [0, 255, 0, 255],
        }
    }

    ellipse_properties = {
        "granularity": 0.008722222,
        "zIndex": 5,
        "material": {
            "solidColor": {
                "color": {
                    "rgba": [255, 0, 0, 90]
                }
            }
        }
    }

    top = Packet(id="document", name="Geolocation Data", version=CZML_VERSION)
    all_point_packets = []
    best_point_packets = []
    ellipse_packets = []

    if len(all_the_points) > 0 and (plotallintersects or eps == "0"):
        all_the_points = np.array(all_the_points)
        scaled_time = minmax_scale(all_the_points[:, -1])
        all_the_points = np.column_stack((all_the_points, scaled_time))
        for x in all_the_points:
            rgb = map(lambda x: int(x * 255), hsv_to_rgb(x[-1] / 3, 0.9, 0.9))
            color_property = {"color": {"rgba": [*rgb, 255]}}
            all_point_packets.append(Packet(id=str(x[1]) + ", " + str(x[0]),
                                            point={**point_properties,
                                                   **color_property},
                                            position={
                "cartographicDegrees": [x[0], x[1], 0]},
            ))

    if len(best_point) > 0:
        for x in best_point:
            gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={x[1]},+{x[0]}&travelmode=driving"
            best_point_packets.append(Packet(id=str(x[1]) + ", " + str(x[0]),
                                             point=best_point_properties,
                                             description=f"<a href='{gmaps_url}' target='_blank'>Google Maps Directions</a>",
                                             position={"cartographicDegrees": [x[0], x[1], 0]}))

    if len(ellipsedata) > 0:
        for x in ellipsedata:
            ellipse_info = {"semiMajorAxis": x[0],
                            "semiMinorAxis": x[1], "rotation": x[2]}
            ellipse_packets.append(Packet(id=str(x[4]) + ", " + str(x[3]),
                                          ellipse={
                                              **ellipse_properties, **ellipse_info},
                                          position={"cartographicDegrees": [x[3], x[4], 0]}))

    return Document(packets=[top] + best_point_packets + all_point_packets + ellipse_packets).dumps()


###############################################
# Writes receivers.czml used by the WebUI
###############################################
@get('/receivers.czml')
def write_rx_czml():
    response.set_header(
        'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
    height = 50
    min_conf = ms.min_conf
    min_power = ms.min_power
    green = [0, 255, 0, 255]
    orange = [255, 140, 0, 255]
    red = [255, 0, 0, 255]
    gray = [128, 128, 128, 255]
    receiver_point_packets = []
    lob_packets = []
    top = Packet(id="document", name="Receivers", version=CZML_VERSION)

    rx_properties = {
        "verticalOrigin": "BOTTOM",
        "scale": 0.75,
        "heightReference": {"heightReference": "CLAMP_TO_GROUND"},
        "height": 48,
        "width": 48,
    }
    # Use lock to ensure thread-safe access to receiver data
    with rx_lock:
        for index, x in enumerate(receivers):
            if x.isActive and ms.receiving:
                if (x.confidence > min_conf and x.power > min_power):
                    lob_color = green
                elif (x.confidence <= min_conf and x.power > min_power):
                    lob_color = orange
                else:
                    lob_color = red
                lob_start_lat = x.latitude
                lob_start_lon = x.longitude
                lob_stop_lat, lob_stop_lon = v.direct(
                    lob_start_lat, lob_start_lon, x.doa, x.lob_length())
                lob_packets.append(Packet(id=f"LOB-{x.station_id}-{index}",
                                          polyline=Polyline(
                                              material=PolylineMaterial(polylineOutline=PolylineOutlineMaterial(
                                                  color=Color(
                                                      rgba=lob_color),
                                                  outlineColor=Color(
                                                      rgba=[0, 0, 0, 255]),
                                                  outlineWidth=2
                                              )),
                                              clampToGround=True,
                                              width=5,
                                              positions=PositionList(cartographicDegrees=[
                                                  lob_start_lon, lob_start_lat, height, lob_stop_lon, lob_stop_lat, height])
                                          )))
                heading_start_lat = x.latitude
                heading_start_lon = x.longitude
                heading_stop_lat, heading_stop_lon = v.direct(
                    heading_start_lat, heading_start_lon, x.heading, HEADING_DRAW_DISTANCE_METERS)
                lob_packets.append(Packet(id=f"HEADING-{x.station_id}-{index}",
                                          polyline=Polyline(
                                              material=PolylineMaterial(
                                                  polylineDash = PolylineDashMaterial(color=Color(
                                                      rgba=gray),
                                                  gapColor=Color(
                                                      rgba=[0, 0, 0, 0])
                                              )),
                                              clampToGround=True,
                                              width=2,
                                              positions=PositionList(cartographicDegrees=[
                                                  heading_start_lon, heading_start_lat, height, heading_stop_lon, heading_stop_lat, height])
                                          )))

            if x.isMobile is True:
                rx_icon = {"image": {"uri": "/static/flipped_car.svg"}}
            else:
                rx_icon = {"image": {"uri": "/static/tower.svg"}}
            receiver_point_packets.append(Packet(id=f"{x.station_id}-{index}",
                                                 billboard={
                                                     **rx_properties, **rx_icon},
                                                 position={"cartographicDegrees": [x.longitude, x.latitude, 15]}))

    return Document(packets=[top] + receiver_point_packets + lob_packets).dumps()


def _epoch_ms_to_iso(epoch_ms):
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{dt.microsecond // 1000:03d}Z'


@get("/lob_history.czml")
def lob_history_czml():
    response.set_header(
        'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')

    now_ms = time.time() * 1000
    start = int(request.query.start or (now_ms - 3600000))
    end = int(request.query.end or now_ms)
    min_conf = int(request.query.min_conf or ms.min_conf)
    min_power = int(request.query.min_power or ms.min_power)
    mode = request.query.mode or "flash"
    freq = request.query.frequency

    conn = sqlite3.connect(database_name)
    c = conn.cursor()

    if freq:
        c.execute('''SELECT time, station_id, latitude, longitude, confidence, power, frequency, lob
            FROM lobs
            WHERE time BETWEEN ? AND ?
              AND confidence >= ?
              AND power >= ?
              AND frequency = ?
            ORDER BY time''', [start, end, min_conf, min_power, float(freq)])
    else:
        c.execute('''SELECT time, station_id, latitude, longitude, confidence, power, frequency, lob
            FROM lobs
            WHERE time BETWEEN ? AND ?
              AND confidence >= ?
              AND power >= ?
            ORDER BY time''', [start, end, min_conf, min_power])

    rows = c.fetchall()
    conn.close()

    start_iso = _epoch_ms_to_iso(start)
    end_iso = _epoch_ms_to_iso(end)

    top = Packet(
        id="document",
        name="LOB History",
        version=CZML_VERSION,
        clock=Clock(
            interval=TimeInterval(start=start_iso, end=end_iso),
            currentTime=start_iso,
            multiplier=1.0
        )
    )

    green = [0, 255, 0, 153]
    orange = [255, 140, 0, 153]
    red = [255, 0, 0, 153]
    outline_color = [0, 0, 0, 153]
    height = 50

    lob_packets = []
    for row in rows:
        lob_time, station_id, lat, lon, conf, pwr, freq_val, doa = row

        if conf > min_conf and pwr > min_power:
            lob_color = green
        elif conf <= min_conf and pwr > min_power:
            lob_color = orange
        else:
            lob_color = red

        lob_stop_lat, lob_stop_lon = v.direct(lat, lon, doa, LOB_DRAW_DISTANCE_METERS)

        if mode == "accumulate":
            avail_start_iso = _epoch_ms_to_iso(lob_time)
            avail_end_iso = end_iso
        else:
            avail_start_iso = _epoch_ms_to_iso(lob_time - 2500)
            avail_end_iso = _epoch_ms_to_iso(lob_time + 2500)

        avail = TimeInterval(start=avail_start_iso, end=avail_end_iso)

        lob_packets.append(Packet(
            id=f"LOB-HIST-{station_id}-{lob_time}",
            availability=avail,
            polyline=Polyline(
                material=PolylineMaterial(polylineOutline=PolylineOutlineMaterial(
                    color=Color(rgba=lob_color),
                    outlineColor=Color(rgba=outline_color),
                    outlineWidth=1
                )),
                clampToGround=True,
                width=4,
                positions=PositionList(cartographicDegrees=[
                    lon, lat, height, lob_stop_lon, lob_stop_lat, height])
            )
        ))

    return Document(packets=[top] + lob_packets).dumps()


###############################################
# Writes aoi.czml used by the WebUI
###############################################
@get("/aoi.czml")
def wr_aoi_czml():
    response.set_header(
        'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
    aoi_packets = []
    top = Packet(id="document", name="AOIs", version=CZML_VERSION)
    area_of_interest_properties = {
        "granularity": 0.008722222,
        "height": 0,
        "material": {
            "solidColor": {
                "color": {
                    "rgba": [0, 0, 255, 25]
                }
            }
        },
        "outline": True,
        "outlineWidth": 2,
        "outlineColor": {"rgba": [53, 184, 240, 255]},
    }

    exclusion_area_properties = {
        "granularity": 0.008722222,
        "height": 0,
        "material": {
            "solidColor": {
                "color": {
                    "rgba": [242, 10, 0, 25]
                }
            }
        },
        "outline": True,
        "outlineWidth": 2,
        "outlineColor": {"rgba": [224, 142, 0, 255]},
    }

    for x in fetch_aoi_data():
        aoi = {
            'uid': x[0],
            'aoi_type': x[1],
            'latitude': x[2],
            'longitude': x[3],
            'radius': x[4]
        }
        if aoi['aoi_type'] == "aoi":
            aoi_properties = area_of_interest_properties
        elif aoi['aoi_type'] == "exclusion":
            aoi_properties = exclusion_area_properties
        aoi_info = {"semiMajorAxis": aoi['radius'],
                    "semiMinorAxis": aoi['radius'], "rotation": 0}
        aoi_packets.append(Packet(id=aoi['aoi_type'] + str(aoi['uid']),
                                  ellipse={**aoi_properties, **aoi_info},
                                  position={"cartographicDegrees": [aoi['longitude'], aoi['latitude'], 0]}))

    return Document(packets=[top] + aoi_packets).dumps()


###############################################
# Clears the screen if debugging is off.
###############################################
def clear(debugging):
    if not debugging:
        print('\033[2J\033[H', end='', flush=True)


###############################################
# Serves static files such as CSS and JS to the
# WebUI
###############################################
@route('/static/<filepath:path>', name='static')
def server_static(filepath):
    response = static_file(filepath, root='./static')
    response.set_header(
        'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
    return response


###############################################
# Loads the main page of the WebUI
# http://[ip]:[port]/
###############################################
@get('/')
@get('/index')
@get('/cesium')
def cesium():
    response.set_header(
        'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
    return template('cesium.tpl',
                    {'access_token': access_token,
                     'epsilon': ms.eps,
                     'minpower': ms.min_power,
                     'minconf': ms.min_conf,
                     'minpoints': ms.min_samp,
                     'rx_state': "checked" if ms.receiving is True else "",
                     'intersect_state': "checked" if ms.plotintersects is True else "",
                     'lob_history_state': "checked" if ms.lob_history_enabled is True else "",
                     'receivers': receivers})


###############################################
# GET Request to update parameters from the
# UI sliders. Not meant to be user facing.
###############################################
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


###############################################
# Returns a JSON file to the WebUI with
# information to fill in the RX cards.
###############################################
@get('/rx_params')
def rx_params():

    # No rx.update() here — run_receiver() already polls every ~1s.
    # This endpoint just returns cached state for the UI cards.
    all_rx = {'receivers': {}}
    rx_properties = []
    for index, x in enumerate(receivers):
        rx = x.receiver_dict()
        rx['uid'] = index
        rx_properties.append(rx)
    all_rx['receivers'] = rx_properties
    response.headers['Content-Type'] = 'application/json'
    return json.dumps(all_rx)


###############################################
# Returns a CZML file that contains intersect
# and ellipse information for Cesium.
###############################################
@get('/output.czml')
def tx_czml_out():
    eps = request.query.eps if request.query.eps else str(ms.eps)
    min_samp = request.query.minpts if request.query.minpts else str(
        ms.min_samp)
    if request.query.plotpts == "true":
        plotallintersects = True
    elif request.query.plotpts == "false":
        plotallintersects = False
    else:
        plotallintersects = ms.plotintersects
    response.set_header(
        'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
    output = write_czml(*process_data(database_name, eps,
                                      min_samp), plotallintersects, eps)
    return str(output)


###############################################
# PUT request to update receiver variables
# from the WebUI
###############################################
@put('/rx_params/<action>')
def update_rx(action):
    data = json.load(request.body)
    if action == "new":
        receiver_url = data['station_url'].replace('\n', '')
        add_receiver(receiver_url)
    elif action == "del":
        index = int(data['uid'])
        command = "DELETE FROM receivers WHERE station_id=?"
        DATABASE_EDIT_Q.put(
            (command, [(receivers[index].station_id,), ], True))
        DATABASE_RETURN.get(timeout=1)
        DATABASE_EDIT_Q.put(("done", None, False))
        del receivers[index]
    elif action == "activate":
        index = int(data['uid'])
        receivers[index].isActive = data['state']
    else:
        action = int(action)
        try:
            receivers[action].isMobile = data['mobile']
            receivers[action].inverted = data['inverted']
            receivers[action].isSingle = data['single']
            receivers[action].update()
            update_rx_table()
        except IndexError:
            print("I got some bad data. Doing nothing out of spite.")
    return redirect('/rx_params')


###############################################
# Returns a JSON file to the WebUI with
# information to fill in the AOI cards.
###############################################
@get('/interest_areas')
def load_interest_areas():
    all_aoi = {'aois': {}}
    aoi_properties = []
    for x in fetch_aoi_data():
        aoi = {
            'uid': x[0],
            'aoi_type': x[1],
            'latitude': x[2],
            'longitude': x[3],
            'radius': x[4]
        }
        aoi_properties.append(aoi)
    all_aoi['aois'] = aoi_properties
    response.headers['Content-Type'] = 'application/json'
    return json.dumps(all_aoi)


##########################################
# PUT request to add new AOI to DB
##########################################
@put('/interest_areas/<action>')
def handle_interest_areas(action):
    data = json.load(request.body)
    if action == "new" and not "" in data.values():
        aoi_type = data['aoi_type']
        lat = data['latitude']
        lon = data['longitude']
        radius = data['radius']
        add_aoi(aoi_type, lat, lon, radius)
    elif action == "del":
        command = "UPDATE intersects SET aoi_id=? WHERE aoi_id=?"
        DATABASE_EDIT_Q.put((command, [(-1, data['uid']), ], True))
        DATABASE_RETURN.get(timeout=1)
        to_table = (str(data['uid']),)
        command = "DELETE FROM interest_areas WHERE uid=?"
        DATABASE_EDIT_Q.put((command, [to_table, ], True))
        DATABASE_RETURN.get(timeout=1)
        DATABASE_EDIT_Q.put(("done", None, False))
        invalidate_aoi_cache()
    elif action == "purge":
        conn = sqlite3.connect(database_name)
        c = conn.cursor()
        c.execute("SELECT aoi_type, latitude, longitude, radius FROM interest_areas WHERE uid=?", [
                  data['uid']])
        properties = c.fetchone()
        conn.close()
        purge_database(*properties)


###############################################
# Gzip compression WSGI middleware
###############################################
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

        compressed = gzip.compress(body, compresslevel=6)

        new_headers = [
            (name, value) for name, value in headers
            if name.lower() not in ('content-length', 'content-encoding', 'vary')
        ]
        new_headers.append(('Content-Encoding', 'gzip'))
        new_headers.append(('Content-Length', str(len(compressed))))
        new_headers.append(('Vary', 'Accept-Encoding'))

        start_response(status, new_headers)
        return [compressed]


###############################################
# Starts the Bottle webserver.
###############################################
def start_server(ipaddr="127.0.0.1", port=8080):
    try:
        run(app=GzipMiddleware(bottle_app()), host=ipaddr, port=port, quiet=True,
            server=GeventWebSocketServer, debug=True)
    except OSError:
        print(f"Port {port} seems to be in use. Please select another port or " +
              "check if another instance of DFA is already running.")
        debugging = True
        finish()


###############################################
# Captures DOA data and computes intersections
# if the receiver is enabled. Writes the
# intersections to the database.
###############################################
def run_receiver():
    clear(debugging)
    dots = 0

    # Read-only connection for LOB queries in single-receiver mode below.
    # Writes go through DATABASE_EDIT_Q; this conn just reads committed data.
    conn = sqlite3.connect(database_name)
    c = conn.cursor()

    while ms.receiving:
        if not debugging:
            print("Receiving" + dots * '.')
            print("Press Control+C to process data and exit.")

        # Poll receivers outside the lock (network I/O)
        for rx in receivers:
            try:
                if rx.isActive:
                    rx.update()
            except IOError:
                print("Problem connecting to receiver.")

        # Snapshot receiver state under lock, then release for processing
        with rx_lock:
            for rx in receivers:
                rx.d_2_last_intersection = []
            rx_snapshot = [(i, rx) for i, rx in enumerate(receivers)]

        # Record LOBs for history replay (and single-receiver triangulation)
        for rx in receivers:
            is_single_rx = rx.isSingle and rx.isMobile
            if rx.isActive and rx.doa_time > rx.previous_doa_time and (ms.lob_history_enabled or is_single_rx):
                to_lobs = [rx.doa_time, rx.station_id, rx.latitude,
                           rx.longitude, rx.confidence, rx.power,
                           rx.frequency, rx.doa]
                command = '''INSERT INTO lobs
                    (time, station_id, latitude, longitude, confidence, power, frequency, lob)
                    VALUES (?,?,?,?,?,?,?,?)'''
                DATABASE_EDIT_Q.put((command, (to_lobs,), True))
                DATABASE_RETURN.get(timeout=1)
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

        with rx_lock:
            for i, rx in rx_snapshot:
                rx.d_2_last_intersection = d2_accum[i]

        if intersect_list:
            intersect_array = np.array(intersect_list)
            avg_coord = np.average(
                intersect_array[:, 0:3], weights=intersect_array[:, 2], axis=0)
            keep, in_aoi = check_aoi(*avg_coord[0:2])
            if keep:
                to_table = [latest_doa_time, round(avg_coord[0], 6), round(avg_coord[1], 6),
                            len(intersect_list), avg_coord[2], in_aoi]
                command = '''INSERT INTO intersects
                (time, latitude, longitude, num_parents, confidence, aoi_id)
                VALUES (?,?,?,?,?,?)'''
                DATABASE_EDIT_Q.put((command, (to_table,), True))
                DATABASE_RETURN.get(timeout=1)

        # Single-receiver triangulation
        for rx in receivers:
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
                                keep, in_aoi = check_aoi(*intersection[0:2])
                                if keep:
                                    keep_count += 1
                                    to_table = [current_time, round(intersection[0], 5), round(intersection[1], 5),
                                                1, intersection[2], in_aoi]
                                    command = '''INSERT INTO intersects
                                    (time, latitude, longitude, num_parents, confidence, aoi_id)
                                    VALUES (?,?,?,?,?,?)'''
                                    DATABASE_EDIT_Q.put(
                                        (command, (to_table,), True))
                                    DATABASE_RETURN.get(timeout=1)
                print(f"Computed and kept {keep_count} intersections.")

        DATABASE_EDIT_Q.put(("done", None, False))
        time.sleep(1)
        if dots > 5:
            dots = 1
        else:
            dots += 1
        clear(debugging)

    conn.close()


###############################################
# Checks if intersection should be kept or not
###############################################
def check_aoi(lat, lon):
    keep_list = []
    in_aoi = None
    aoi_data = fetch_aoi_data()
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


###############################################
# Adds a new receiver to the program, saves it
# in the database.
###############################################
def add_receiver(receiver_url):
    try:
        if any(x.station_url == receiver_url for x in receivers):
            print("Duplicate receiver, ignoring.")
        else:
            receivers.append(receiver(receiver_url))
            new_rx = receivers[-1].receiver_dict()
            to_table = [new_rx['station_id'], new_rx['station_url'], new_rx['auto'],
                        new_rx['mobile'], new_rx['single'], new_rx['latitude'], new_rx['longitude']]

            command = "INSERT OR IGNORE INTO receivers VALUES (?,?,?,?,?,?,?)"
            DATABASE_EDIT_Q.put((command, [to_table, ], True))
            DATABASE_RETURN.get(timeout=1)
            DATABASE_EDIT_Q.put(("done", None, True))
            DATABASE_RETURN.get(timeout=1)
            conn = sqlite3.connect(database_name)
            c = conn.cursor()
            mobile = c.execute("SELECT isMobile FROM receivers WHERE station_id = ?",
                               [new_rx['station_id']]).fetchone()[0]
            single = c.execute("SELECT isSingle FROM receivers WHERE station_id = ?",
                               [new_rx['station_id']]).fetchone()[0]
            conn.close()
            receivers[-1].isMobile = bool(mobile)
            receivers[-1].isSingle = bool(single)
            print("Created new DF Station at " + receiver_url)
    except AttributeError:
        pass


###############################################
# Reads receivers from the database into the
# program.
###############################################
def read_rx_table():
    conn = sqlite3.connect(database_name)
    c = conn.cursor()
    try:
        c.execute("SELECT station_url FROM receivers")
        rx_list = c.fetchall()
        for x in rx_list:
            receiver_url = x[0].replace('\n', '')
            add_receiver(receiver_url)
    except sqlite3.OperationalError:
        rx_list = []
    conn.close()


###############################################
# Updates the database with any changes made to
# the receivers.
###############################################
def update_rx_table():
    for item in receivers:
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
        DATABASE_EDIT_Q.put((command, [to_table, ], True))
        # try:
        DATABASE_RETURN.get(timeout=1)
        # except:
        #     pass
    DATABASE_EDIT_Q.put(("done", None, False))


###############################################
# Updates the database with new interest areas.
###############################################
def add_aoi(aoi_type, lat, lon, radius):
    conn = sqlite3.connect(database_name)
    c = conn.cursor()

    prev_uid = c.execute('SELECT MAX(uid) from interest_areas').fetchone()[0]
    conn.close()
    uid = (prev_uid + 1) if prev_uid is not None else 0
    to_table = [uid, aoi_type, lat, lon, radius]
    command = 'INSERT INTO interest_areas VALUES (?,?,?,?,?)'
    DATABASE_EDIT_Q.put((command, [to_table, ], True))
    DATABASE_RETURN.get(timeout=1)
    DATABASE_EDIT_Q.put(("done", None, False))
    invalidate_aoi_cache()


#########################################
# Read all the AOIs from the DB
#########################################
def invalidate_aoi_cache():
    global _aoi_cache
    with _aoi_cache_lock:
        _aoi_cache = None


def fetch_aoi_data():
    global _aoi_cache
    with _aoi_cache_lock:
        if _aoi_cache is not None:
            return _aoi_cache
        conn = sqlite3.connect(database_name)
        c = conn.cursor()
        c.execute('SELECT * FROM interest_areas')
        aoi_list = c.fetchall()
        conn.close()
        _aoi_cache = aoi_list
        return aoi_list


###############################################
# One thread responsible for all database write
# operations.
###############################################
def database_writer():
    conn = sqlite3.connect(database_name)
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

    # Create indexes for performance optimization
    # Index on intersects table for filtering by AOI and sorting by confidence
    c.execute('''CREATE INDEX IF NOT EXISTS idx_intersects_aoi_confidence
        ON intersects(aoi_id, confidence DESC)''')

    # Index on intersects table for time-based queries
    c.execute('''CREATE INDEX IF NOT EXISTS idx_intersects_time
        ON intersects(time)''')

    # Index on lobs table for single-receiver mode queries
    c.execute('''CREATE INDEX IF NOT EXISTS idx_lobs_station_time
        ON lobs(station_id, time)''')

    c.execute('''CREATE INDEX IF NOT EXISTS idx_lobs_time
        ON lobs(time)''')

    # Index on interest_areas table for UID lookups
    c.execute('''CREATE INDEX IF NOT EXISTS idx_interest_areas_uid
        ON interest_areas(uid)''')

    # Index on interest_areas table for type filtering
    c.execute('''CREATE INDEX IF NOT EXISTS idx_interest_areas_type
        ON interest_areas(aoi_type)''')

    conn.commit()
    while True:
        # items should be list of lists
        command, items, reply = DATABASE_EDIT_Q.get()
        if command == "done":
            conn.commit()
            if reply:
                DATABASE_RETURN.put(True)
        elif command == "close":
            conn.commit()
            conn.close()
            if reply:
                DATABASE_RETURN.put(True)
            break
        else:
            c.executemany(command, items)
            if reply:
                DATABASE_RETURN.put(True)


###############################################
# Thangs to do before closing the program.
###############################################
def finish():
    clear(debugging)
    print("Processing, please wait.")
    ms.receiving = False
    update_rx_table()
    DATABASE_EDIT_Q.put(("close", None, True))
    DATABASE_RETURN.get(timeout=1)
    if geofile is not None:
        write_geojson(*process_data(database_name, ms.eps, ms.min_samp)[:2])
    kill(getpid(), signal.SIGTERM)


if __name__ == '__main__':
    ###############################################
    # Help info printed when calling the program
    ###############################################
    parser = argparse.ArgumentParser(
        description="DF Aggregator — networked radio direction finding")
    parser.add_argument("-d", "--database", dest="database_name",
                        help="Database file", metavar="FILE", required=True)
    parser.add_argument("-r", "--receivers", dest="rx_file",
                        help="List of receiver URLs", metavar="FILE")
    parser.add_argument("-g", "--geofile", dest="geofile",
                        help="GeoJSON output file", metavar="FILE")
    parser.add_argument("-e", "--epsilon", dest="eps",
                        help="Max clustering distance (default: auto)",
                        metavar="NUMBER", default="auto")
    parser.add_argument("-c", "--confidence", dest="conf",
                        help="Minimum confidence value (default: 10)",
                        metavar="NUMBER", type=int, default=10)
    parser.add_argument("-p", "--power", dest="pwr",
                        help="Minimum power value (default: 10)",
                        metavar="NUMBER", type=int, default=10)
    parser.add_argument("-m", "--min-samples", dest="minsamp",
                        help="Minimum samples per cluster (default: auto)",
                        metavar="NUMBER", default="auto")
    parser.add_argument("--plot_intersects", dest="plotintersects",
                        help="Plot all intersect points in clusters",
                        action="store_true")
    parser.add_argument("-o", "--offline", dest="disable",
                        help="Start with receiver turned off",
                        action="store_false", default=True)
    parser.add_argument("--access_token", dest="token_file",
                        help="Cesium access token file", metavar="FILE")
    parser.add_argument("--ip", dest="ipaddr",
                        help="IP address to serve from (default: 127.0.0.1)",
                        metavar="IP_ADDRESS", type=str, default="127.0.0.1")
    parser.add_argument("--port", dest="port",
                        help="Port number to serve from (default: 8080)",
                        metavar="NUMBER", type=int, default=8080)
    parser.add_argument("--debug", dest="debugging",
                        help="Don't clear screen; show errors and warnings",
                        action="store_true")
    parser.add_argument("--no-lob-history", dest="no_lob_history",
                        help="Disable LOB history recording",
                        action="store_true")
    options = parser.parse_args()

    ms = math_settings(options.eps, options.minsamp, options.conf, options.pwr)

    geofile = options.geofile
    rx_file = options.rx_file
    database_name = options.database_name
    debugging = options.debugging
    ms.receiving = options.disable
    ms.plotintersects = options.plotintersects
    ms.lob_history_enabled = not options.no_lob_history

    if options.token_file:
        tokenfile = options.token_file
        with open(tokenfile, "r") as token:
            access_token = token.read().replace('\n', '')
        # print(access_token)
    else:
        access_token = None

    web = threading.Thread(target=start_server,
                           args=(options.ipaddr, options.port))
    web.daemon = True
    web.start()

    dbwriter = threading.Thread(target=database_writer)
    dbwriter.daemon = True
    dbwriter.start()

    try:
        ###############################################
        # Reds receivers from the database first, then
        # loads receivers in from a user provided list.
        ###############################################
        read_rx_table()
        if rx_file:
            with open(rx_file, "r") as file2:
                receiver_list = file2.readlines()
                for x in receiver_list:
                    receiver_url = x.replace('\n', '')
                    add_receiver(receiver_url)

        ###############################################
        # Run the main loop!
        ###############################################
        while True:
            if ms.receiving:
                run_receiver()
            clear(debugging)
            if not debugging:
                print("Receiver Paused")
            time.sleep(1)

    except KeyboardInterrupt:
        finish()
