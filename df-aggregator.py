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

import vincenty as v
import numpy as np
import math
import time
import sqlite3
import threading
import signal
import json
from colorsys import hsv_to_rgb
from optparse import OptionParser
from os import system, name, kill, getpid
from lxml import etree
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler, minmax_scale
from geojson import MultiPoint, Feature, FeatureCollection
from czml3 import Packet, Document, Preamble
from czml3.properties import Position, Polyline, PolylineMaterial, PolylineOutlineMaterial, PolylineDashMaterial, Color, Material
from multiprocessing import Process, Queue
from bottle import route, run, request, get, put, response, redirect, template, static_file
from bottle.ext.websocket import GeventWebSocketServer, websocket

from sys import version_info
if (version_info.major != 3 or version_info.minor < 6):
    print("Looks like you're running python version " +
          str(version_info.major) + "." +
          str(version_info.minor) + ", which is no longer supported.")
    print("Your python version is out of date, please update to 3.6 or newer.")
    quit()


DBSCAN_Q = Queue()
DBSCAN_WAIT_Q = Queue()
DATABASE_EDIT_Q = Queue()
DATABASE_RETURN = Queue()

d = 40000  # draw distance of LOBs in meters
heading_d = 20000
max_age = 5000
receivers = []


###############################################
# Stores settings realted to intersect capture
# and post-processing.
###############################################
class math_settings:
    def __init__(self, eps, min_samp, conf, power):
        self.eps = eps
        self.min_samp = min_samp
        self.min_conf = conf
        self.min_power = power
    rx_busy = False
    receiving = True
    plotintersects = False


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
            xml_contents = etree.parse(self.station_url)
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
            if self.doa < 0:
                self.doa += 360
            elif self.doa > 359:
                self.doa -= 360
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
            return d

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
    d_2_last_intersection = [d]


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
def plot_intersects(lat_a, lon_a, doa_a, lat_b, lon_b, doa_b, max_distance=100000):
    # plot another point on the lob
    # v.direct(lat_a, lon_a, doa_a, d)
    # returns (lat_a2, lon_a2)

    # Get normal to planes containing great circles
    # np.cross product of vector to each point from the origin
    coord_a2 = v.direct(lat_a, lon_a, doa_a, d)
    coord_b2 = v.direct(lat_b, lon_b, doa_b, d)
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

    if abs(check_bearing - doa_a) < 5:
        km = v.inverse([lat_a, lon_a], [i_lat, i_long])
        if km[0] < max_distance:
            return (i_lat, i_long)
        else:
            return None


#######################################################################
# We start this in it's own process do it doesn't eat all of your RAM.
# This becomes noticable at over 10k intersections.
#######################################################################
def do_dbscan(X, epsilon, minsamp):
    DBSCAN_WAIT_Q.put(True)
    db = DBSCAN(eps=epsilon, min_samples=minsamp).fit(X)
    DBSCAN_Q.put(db.labels_)
    if not DBSCAN_WAIT_Q.empty():
        DBSCAN_WAIT_Q.get()


####################################
# Autocalculate the best eps value.
####################################
def autoeps_calc(X):
    # only use a sample of the data to speed up calculation.
    X = X[:min(2000, len(X)):2]
    min_distances = []
    for x in X:
        distances = []
        for y in X:
            # calculate euclidian distance
            distance = math.sqrt(sum([(a - b) ** 2 for a, b in zip(x, y)]))
            if distance > 0:
                distances.append(distance)
        min_distances.extend(np.sort(distances)[0:3].tolist())

    sorted_distances = np.sort(min_distances).tolist()
    try:
        for x1, y1 in enumerate(sorted_distances):
            x2 = x1 + 1
            y2 = sorted_distances[x2]
            # calculate slope
            m = (y2 - y1) / (x2 - x1)

            # once the slope starts getting steeper, use that as the eps value
            if m > 0.003:
                # print(f"Slope: {round(m, 3)}, eps: {y1}")
                return y1
    except IndexError:
        return 0


###############################################
# Computes DBSCAN Alorithm is applicable,
# finds the mean of a cluster of intersections.
###############################################
def process_data(database_name, epsilon, min_samp):
    n_std = 3.0
    intersect_list = []
    likely_location = []
    ellipsedata = []
    # weighted_location = []
    conn = sqlite3.connect(database_name)
    curs = conn.cursor()
    curs.execute("SELECT DISTINCT aoi_id FROM intersects")
    curs.execute('SELECT uid FROM interest_areas WHERE aoi_type="aoi"')
    aoi_list = [item for sublist in curs.fetchall() for item in sublist]
    # aoi_list = [-1] if len(aoi_list) == 0 else aoi_list
    aoi_list.append(-1)

    for aoi in aoi_list:
        print(f"Checking AOI {aoi}.")
        curs.execute('''SELECT longitude, latitude, time FROM intersects
            WHERE aoi_id=? ORDER BY confidence DESC LIMIT 25000''', [aoi])
        intersect_array = np.array(curs.fetchall())
        if intersect_array.size != 0:
            if epsilon != "0":
                X = StandardScaler().fit_transform(intersect_array[:, 0:2])
                n_points = len(X)

                if min_samp == "auto":
                    min_samp = round(0.05 * n_points)
                elif not min_samp.isnumeric():
                    break

                min_samp = max(3, min_samp)
                min_samp = int(min_samp)

                if epsilon == "auto":
                    epsilon = autoeps_calc(X)
                    print(f"min_samp: {min_samp}, eps: {epsilon}")
                else:
                    try:
                        epsilon = float(epsilon)
                    except ValueError:
                        break

                # size_x = sys.getsizeof(X)/1024
                # print(f"The dataset is {size_x} kilobytes")
                print(f"Computing Clusters from {n_points} intersections.")
                while not DBSCAN_WAIT_Q.empty():
                    print("Waiting for my turn...")
                    time.sleep(1)
                starttime = time.time()
                db = Process(target=do_dbscan, args=(X, epsilon, min_samp))
                db.daemon = True
                db.start()
                try:
                    labels = DBSCAN_Q.get(timeout=10)
                    db.join()
                except:
                    print("DBSCAN took took long, terminated.")
                    if not DBSCAN_WAIT_Q.empty():
                        DBSCAN_WAIT_Q.get()
                    db.terminate()
                    return likely_location, intersect_list, ellipsedata

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
                    cluster = np.array([]).reshape(0, 3)
                    for y in range(len(intersect_array)):
                        if intersect_array[y][-1] == x:
                            cluster = np.concatenate(
                                (cluster, [intersect_array[y][0:-1]]), axis=0)
                    # weighted_location.append(np.average(cluster[:,0:2], weights=cluster[:,2], axis=0).tolist())
                    clustermean = np.mean(cluster[:, 0:2], axis=0)
                    likely_location.append(clustermean.tolist())
                    cov = np.cov(cluster[:, 0], cluster[:, 1])
                    a = cov[0, 0]
                    b = cov[0, 1]
                    c = cov[1, 1]
                    if (a == 0.0 or b == 0.0 or c == 0.0):
                        if debugging:
                            print(f"A: {a} B: {b} C: {c}")
                            print("Unable to resolve ellipse.")
                        break
                    lam1 = a + c / 2 + np.sqrt((a - c / 2)**2 + b**2)
                    # lam2 = a+c/2 - np.sqrt((a-c/2)**2 + b**2)
                    # print([lam1, lam2, a, c])
                    pearson = b / np.sqrt(a * c)
                    if (1 + pearson < 0.0 or 1 - pearson < 0.0):
                        if debugging:
                            print(f"Pearson Value: {pearson}")
                            print("Unable to resolve ellipse.")
                        break
                    print(f"A: {a} B: {b} C: {c} pearson: {pearson}")
                    ell_radius_x = np.sqrt(1 + pearson) * np.sqrt(a) * n_std
                    ell_radius_y = np.sqrt(1 - pearson) * np.sqrt(c) * n_std
                    axis_x = v.inverse(clustermean.tolist()[
                        ::-1], (ell_radius_x + clustermean[1], clustermean[0]))[0]
                    axis_y = v.inverse(clustermean.tolist()[
                        ::-1], (clustermean[1], ell_radius_y + clustermean[0]))[0]
                    if b == 0 and a >= c:
                        rotation = 0
                    elif b == 0 and a < c:
                        rotation = np.pi / 2
                    else:
                        rotation = math.atan2(lam1 - a, b)

                    ellipsedata.append(
                        [axis_x, axis_y, rotation, *clustermean.tolist()])

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
def purge_database(type, lat, lon, radius):
    conn = sqlite3.connect(database_name)
    c = conn.cursor()
    c.execute("SELECT latitude, longitude, id FROM intersects")
    intersect_list = c.fetchall()
    conn.close()
    delete_these = []
    purge_count = 0
    for x in intersect_list:
        if type == "exclusion":
            distance = v.inverse(x[0:2], (lat, lon))[0]
            if distance < radius:
                delete_these.append((x[2],))
                purge_count += 1

    command = "DELETE FROM intersects WHERE id=?"
    DATABASE_EDIT_Q.put((command, delete_these, False))
    # DATABASE_RETURN.get(timeout=1)
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
    in_aoi = None
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
            id, lat, lon = point
            for x in aoi_list:
                # aoi = {
                # 'uid': x[0],
                # 'aoi_type': x[1],
                # 'latitude': x[2],
                # 'longitude': x[3],
                # 'radius': x[4]
                # }
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
                        # del_list.append(id)

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
                reversed_best_point = []
                for x in best_point:
                    reversed_best_point.append(x)
                best_point = Feature(properties=best_pt_style, geometry=MultiPoint(
                    tuple(reversed_best_point)))
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
        "heightReference": "CLAMP_TO_GROUND",
        "zIndex": 3
    }
    best_point_properties = {
        "pixelSize": 12.0,
        "zIndex": 10,
        "heightReference": "CLAMP_TO_GROUND",
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

    top = Preamble(name="Geolocation Data")
    all_point_packets = []
    best_point_packets = []
    ellipse_packets = []

    if len(all_the_points) > 0 and (plotallintersects or eps == "0"):
        all_the_points = np.array(all_the_points)
        scaled_time = minmax_scale(all_the_points[:, -1])
        all_the_points = np.column_stack((all_the_points, scaled_time))
        for x in all_the_points:
            # rgb = hsvtorgb(x[-1]/3, 0.9, 0.9)
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
            # rotation = 2 * np.pi - x[2]
            if x[0] >= x[1]:
                # rotation = x[2]
                semiMajorAxis = x[0]
                semiMinorAxis = x[1]
                rotation = 2 * np.pi - x[2]
                rotation += np.pi / 2
                # print(f"{x[2]} Inverted to: {rotation}")
                # print(f"SemiMajor: {semiMajorAxis}, Semiminor: {semiMinorAxis}")
                # print(f"{x[4], x[3]} is inveted")
            else:
                rotation = x[2]
                semiMajorAxis = x[1]
                semiMinorAxis = x[0]
                # print(f"Not inverted: {rotation}")
                # print(f"SemiMajor: {semiMajorAxis}, Semiminor: {semiMinorAxis}")
                # print(f"{x[4], x[3]} is NOT inveted")

            ellipse_info = {"semiMajorAxis": semiMajorAxis,
                            "semiMinorAxis": semiMinorAxis, "rotation": rotation}
            ellipse_packets.append(Packet(id=str(x[4]) + ", " + str(x[3]),
                                          ellipse={
                                              **ellipse_properties, **ellipse_info},
                                          position={"cartographicDegrees": [x[3], x[4], 0]}))

    return Document([top] + best_point_packets + all_point_packets + ellipse_packets).dumps(separators=(',', ':'))


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
    top = Preamble(name="Receivers")

    rx_properties = {
        "verticalOrigin": "BOTTOM",
        "zIndex": 9,
        "scale": 0.75,
        "heightReference": "CLAMP_TO_GROUND",
        "height": 48,
        "width": 48,
    }
    while not ms.rx_busy:
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
                                              material=Material(polylineOutline=PolylineOutlineMaterial(
                                                  color=Color(
                                                      rgba=lob_color),
                                                  outlineColor=Color(
                                                      rgba=[0, 0, 0, 255]),
                                                  outlineWidth=2
                                              )),
                                              clampToGround=True,
                                              width=5,
                                              positions=Position(cartographicDegrees=[
                                                  lob_start_lon, lob_start_lat, height, lob_stop_lon, lob_stop_lat, height])
                                          )))
                heading_start_lat = x.latitude
                heading_start_lon = x.longitude
                heading_stop_lat, heading_stop_lon = v.direct(
                    heading_start_lat, heading_start_lon, x.heading, heading_d)
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
                                              positions=Position(cartographicDegrees=[
                                                  heading_start_lon, heading_start_lat, height, heading_stop_lon, heading_stop_lat, height])
                                          )))
            else:
                lob_packets = []

            if x.isMobile is True:
                rx_icon = {"image": {"uri": "/static/flipped_car.svg"}}
                # if x.heading > 0 or x.heading < 180:
                #     rx_icon = {"image":{"uri":"/static/flipped_car.svg"}, "rotation":math.radians(360 - x.heading + 90)}
                # elif x.heading < 0 or x.heading > 180:
                #     rx_icon = {"image":{"uri":"/static/car.svg"}, "rotation":math.radians(360 - x.heading - 90)}
            else:
                rx_icon = {"image": {"uri": "/static/tower.svg"}}
            receiver_point_packets.append(Packet(id=f"{x.station_id}-{index}",
                                                 billboard={
                                                     **rx_properties, **rx_icon},
                                                 position={"cartographicDegrees": [x.longitude, x.latitude, 15]}))

        return Document([top] + receiver_point_packets + lob_packets).dumps(separators=(',', ':'))


###############################################
# Writes aoi.czml used by the WebUI
###############################################
@get("/aoi.czml")
def wr_aoi_czml():
    response.set_header(
        'Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0')
    aoi_packets = []
    top = Preamble(name="AOIs")
    area_of_interest_properties = {
        "granularity": 0.008722222,
        "height": 0,
        # "zIndex": 1,
        "material": {
            "solidColor": {
                "color": {
                    "rgba": [0, 0, 255, 25]
                }
            }
        },
        "outline": True,
        "outlineWidth": 2,
        "outlineColor": {"rgba": [53, 184, 240, 255], },
    },

    exclusion_area_properties = {
        "granularity": 0.008722222,
        "height": 0,
        # "zIndex": 0,
        "material": {
            "solidColor": {
                "color": {
                    "rgba": [242, 10, 0, 25]
                }
            }
        },
        "outline": True,
        "outlineWidth": 2,
        "outlineColor": {"rgba": [224, 142, 0, 255], },
    },

    for x in fetch_aoi_data():
        aoi = {
            'uid': x[0],
            'aoi_type': x[1],
            'latitude': x[2],
            'longitude': x[3],
            'radius': x[4]
        }
        if aoi['aoi_type'] == "aoi":
            aoi_properties = area_of_interest_properties[0]
        elif aoi['aoi_type'] == "exclusion":
            aoi_properties = exclusion_area_properties[0]
        aoi_info = {"semiMajorAxis": aoi['radius'],
                    "semiMinorAxis": aoi['radius'], "rotation": 0}
        aoi_packets.append(Packet(id=aoi['aoi_type'] + str(aoi['uid']),
                                  ellipse={**aoi_properties, **aoi_info},
                                  position={"cartographicDegrees": [aoi['longitude'], aoi['latitude'], 0]}))

    return Document([top] + aoi_packets).dumps(separators=(',', ':'))


###############################################
# Clears the screen if debugging is off.
###############################################
def clear(debugging):
    if not debugging:
        # for windows
        if name == 'nt':
            _ = system('cls')
        # for mac and linux(here, os.name is 'posix')
        else:
            _ = system('clear')


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
                     'receivers': receivers})


###############################################
# GET Request to update parameters from the
# UI sliders. Not meant to be user facing.
###############################################
@get('/update')
def update_cesium():
    # eps = float(request.query.eps) if request.query.eps else ms.eps
    # min_samp = float(request.query.minpts) if request.query.minpts else ms.min_samp
    ms.min_conf = float(
        request.query.minconf) if request.query.minconf else ms.min_conf
    ms.min_power = float(
        request.query.minpower) if request.query.minpower else ms.min_power

    if request.query.rx == "true":
        ms.receiving = True
    elif request.query.rx == "false":
        ms.receiving = False

    # if request.query.plotpts == "true":
    #     ms.plotintersects = True
    # elif request.query.plotpts == "false":
    #     ms.plotintersects = False

    return "OK"


###############################################
# Returns a JSON file to the WebUI with
# information to fill in the RX cards.
###############################################
@get('/rx_params')
def rx_params():

    all_rx = {'receivers': {}}
    rx_properties = []
    for index, x in enumerate(receivers):
        x.update()
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
        # del_receiver(receivers[index].station_id)
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
            # receivers[action].station_url = data['station_url']
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
    elif action == "purge":
        conn = sqlite3.connect(database_name)
        c = conn.cursor()
        c.execute("SELECT aoi_type, latitude, longitude, radius FROM interest_areas WHERE uid=?", [
                  data['uid']])
        properties = c.fetchone()
        conn.close()
        purge_database(*properties)


###############################################
# Starts the Bottle webserver.
###############################################
def start_server(ipaddr="127.0.0.1", port=8080):
    try:
        run(host=ipaddr, port=port, quiet=True,
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
def run_receiver(receivers):
    clear(debugging)
    dots = 0

    conn = sqlite3.connect(database_name)
    c = conn.cursor()

    while ms.receiving:
        if not debugging:
            print("Receiving" + dots * '.')
            print("Press Control+C to process data and exit.")

        # Main loop to compute intersections between multiple receivers
        intersect_list = np.array([]).reshape(0, 3)
        ms.rx_busy = True

        for rx in receivers:
            try:
                if rx.isActive:
                    rx.update()
            except IOError:
                print("Problem connecting to receiver.")
            rx.d_2_last_intersection = []

        for x in range(len(receivers)):
            for y in range(x):
                if x != y:
                    if (receivers[x].confidence >= ms.min_conf and
                        receivers[y].confidence >= ms.min_conf and
                        receivers[x].power >= ms.min_power and
                        receivers[y].power >= ms.min_power and
                        abs(receivers[x].doa_time - receivers[y].doa_time) <= max_age and
                            receivers[x].frequency == receivers[y].frequency):
                        intersection = plot_intersects(receivers[x].latitude, receivers[x].longitude,
                                                       receivers[x].doa, receivers[y].latitude, receivers[y].longitude, receivers[y].doa)
                        if intersection:
                            print(intersection)
                            receivers[x].d_2_last_intersection.append(v.haversine(
                                receivers[x].latitude, receivers[x].longitude, *intersection))
                            receivers[y].d_2_last_intersection.append(v.haversine(
                                receivers[y].latitude, receivers[y].longitude, *intersection))
                            intersection = list(intersection)
                            avg_conf = np.mean(
                                [receivers[x].confidence, receivers[y].confidence])
                            intersection.append(avg_conf)
                            intersection = np.array([intersection])
                            if intersection.any() is not None:
                                intersect_list = np.concatenate(
                                    (intersect_list, intersection), axis=0)

        if intersect_list.size != 0:
            avg_coord = np.average(
                intersect_list[:, 0:3], weights=intersect_list[:, 2], axis=0)
            keep, in_aoi = check_aoi(*avg_coord[0:2])
            if keep:
                to_table = [receivers[x].doa_time, round(avg_coord[0], 6), round(avg_coord[1], 6),
                            len(intersect_list), avg_coord[2], in_aoi]
                command = '''INSERT INTO intersects
                (time, latitude, longitude, num_parents, confidence, aoi_id)
                VALUES (?,?,?,?,?,?)'''
                DATABASE_EDIT_Q.put((command, (to_table,), True))
                DATABASE_RETURN.get(timeout=1)

        # Loop to compute intersections for a single receiver and update all receivers
        for rx in receivers:
            if (rx.isSingle and rx.isMobile and rx.isActive and
                rx.confidence >= ms.min_conf and
                rx.power >= ms.min_power and
                    rx.doa_time >= rx.previous_doa_time + 10000):
                current_doa = [rx.doa_time, rx.station_id, rx.latitude,
                               rx.longitude, rx.confidence, rx.doa]
                min_time = rx.doa_time - 1200000  # 15 Minutes
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
                        min_diversity = 500
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

                command = "INSERT INTO lobs VALUES (?,?,?,?,?,?)"
                DATABASE_EDIT_Q.put((command, [current_doa, ], True))
                DATABASE_RETURN.get(timeout=1)

            DATABASE_EDIT_Q.put(("done", None, False))
            # try:
            #     if rx.isActive: rx.update()
            # except IOError:
            #     print("Problem connecting to receiver.")

        ms.rx_busy = False
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
    conn = sqlite3.connect(database_name)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM interest_areas WHERE aoi_type="aoi"')
    n_aoi = c.fetchone()[0]
    conn.close()
    if n_aoi == 0:
        keep_list.append(True)
        in_aoi = -1
    for x in fetch_aoi_data():
        aoi = {
            'uid': x[0],
            'aoi_type': x[1],
            'latitude': x[2],
            'longitude': x[3],
            'radius': x[4]
        }
        distance = v.haversine(aoi['latitude'], aoi['longitude'], lat, lon)
        if aoi['aoi_type'] == "exclusion":
            if distance < aoi['radius']:
                keep = False
                return keep, in_aoi
        elif aoi['aoi_type'] == "aoi":
            if distance < aoi['radius']:
                keep_list.append(True)
                in_aoi = aoi['uid']
            else:
                keep_list.append(False)

    keep = any(keep_list)
    return keep, in_aoi


###############################################
# Adds a new receiver to the program, saves it
# in the database.
###############################################
def add_receiver(receiver_url):
    conn = sqlite3.connect(database_name)
    c = conn.cursor()
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
            DATABASE_EDIT_Q.put(("done", None, False))
            mobile = c.execute("SELECT isMobile FROM receivers WHERE station_id = ?",
                               [new_rx['station_id']]).fetchone()[0]
            single = c.execute("SELECT isSingle FROM receivers WHERE station_id = ?",
                               [new_rx['station_id']]).fetchone()[0]
            receivers[-1].isMobile = bool(mobile)
            receivers[-1].isSingle = bool(single)
            print("Created new DF Station at " + receiver_url)
    except AttributeError:
        pass

    conn.close()


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


#########################################
# Read all the AOIs from the DB
#########################################
def fetch_aoi_data():
    conn = sqlite3.connect(database_name)
    c = conn.cursor()
    c.execute('SELECT * FROM interest_areas')
    aoi_list = c.fetchall()
    conn.close()
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
    c.execute('''CREATE TABLE IF NOT EXISTS lobs (time INTEGER,
        station_id TEXT,
        latitude REAL,
        longitude REAL,
        confidence INTEGER,
        lob REAL)''')
    conn.commit()
    while True:
        # items should be list of lists
        command, items, reply = DATABASE_EDIT_Q.get()
        if command == "done":
            conn.commit()
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
        write_geojson(*process_data(database_name)[:2])
    kill(getpid(), signal.SIGTERM)


if __name__ == '__main__':
    ###############################################
    # Help info printed when calling the program
    ###############################################
    usage = "usage: %prog -d FILE [options]"
    parser = OptionParser(usage=usage)
    parser.add_option("-d", "--database", dest="database_name",
                      help="REQUIRED Database File", metavar="FILE")
    parser.add_option("-r", "--receivers", dest="rx_file",
                      help="List of receiver URLs", metavar="FILE")
    parser.add_option("-g", "--geofile", dest="geofile",
                      help="GeoJSON Output File", metavar="FILE")
    parser.add_option("-e", "--epsilon", dest="eps", help="Max Clustering Distance, Default \"auto\".",
                      metavar="NUMBER or \"auto\"", default="auto")
    parser.add_option("-c", "--confidence", dest="conf", help="Minimum confidence value, default 10",
                      metavar="NUMBER", type="int", default=10)
    parser.add_option("-p", "--power", dest="pwr", help="Minimum power value, default 10",
                      metavar="NUMBER", type="int", default=10)
    parser.add_option("-m", "--min-samples", dest="minsamp", help="Minimum samples per cluster. Default: \"auto\"",
                      metavar="NUMBER or \"auto\"", default="auto")
    parser.add_option("--plot_intersects", dest="plotintersects", help="""Plots all the intersect points in a cluster.
     Only applies when clustering is turned on. This creates larger CZML files.""", action="store_true")
    parser.add_option("-o", "--offline", dest="disable", help="Starts program with receiver turned off.",
                      action="store_false", default=True)
    parser.add_option("--access_token", dest="token_file",
                      help="Cesium Access Token File", metavar="FILE")
    parser.add_option("--ip", dest="ipaddr", help="IP Address to serve from. Default 127.0.0.1",
                      metavar="IP ADDRESS", type="str", default="127.0.0.1")
    parser.add_option("--port", dest="port", help="Port number to serve from. Default 8080",
                      metavar="NUMBER", type="int", default=8080)
    parser.add_option("--debug", dest="debugging", help="Does not clear the screen. Useful for seeing errors and warnings.",
                      action="store_true")
    (options, args) = parser.parse_args()

    mandatories = ['database_name']
    for m in mandatories:
        if options.__dict__[m] is None:
            print("You forgot an arguement")
            parser.print_help()
            exit(-1)

    ms = math_settings(options.eps, options.minsamp, options.conf, options.pwr)

    geofile = options.geofile
    rx_file = options.rx_file
    database_name = options.database_name
    debugging = False if not options.debugging else True
    ms.receiving = options.disable
    ms.plotintersects = options.plotintersects

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
                run_receiver(receivers)
            clear(debugging)
            if not debugging:
                print("Receiver Paused")
            time.sleep(1)

    except KeyboardInterrupt:
        finish()
