#!/usr/bin/env python3

import vincenty as v
import numpy as np
import math
import time
import sqlite3
import threading
import signal
from colorsys import hsv_to_rgb
from optparse import OptionParser
from os import system, name, kill, getpid
from lxml import etree
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler, minmax_scale
from geojson import Point, MultiPoint, Feature, FeatureCollection
from czml3 import Packet, Document, Preamble

from bottle import route, run, request, get, post, redirect, template, static_file

d = 40000 #meters

class math_settings:
    def __init__(self, eps, min_samp, conf, power):
        self.eps = eps
        self.min_samp = min_samp
        self.min_conf = conf
        self.min_power = power
    receiving = True
    plotintersects = False

class receiver:
    def __init__(self, station_url):
        self.station_url = station_url
        try:
            self.update()
        except:
            raise IOError

    def update(self):
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
            self.doa = self.heading + (360 - self.raw_doa)
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
        except:
            raise IOError

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
    isActive = True

def plot_polar(lat_a, lon_a, lat_a2, lon_a2):
    # Convert points in great circle 1, degrees to radians
    p1_lat1_rad = math.radians(lat_a)
    p1_long1_rad =  math.radians(lon_a)
    p1_lat2_rad =  math.radians(lat_a2)
    p1_long2_rad =  math.radians(lon_a2)

    # Put in polar coordinates
    x1 = math.cos(p1_lat1_rad) * math.cos(p1_long1_rad)
    y1 = math.cos(p1_lat1_rad) * math.sin(p1_long1_rad)
    z1 = math.sin(p1_lat1_rad)
    x2 = math.cos(p1_lat2_rad) * math.cos(p1_long2_rad)
    y2 = math.cos(p1_lat2_rad) * math.sin(p1_long2_rad)
    z2 = math.sin(p1_lat2_rad)

    return ([x1, y1, z1], [x2, y2, z2])

# Find line of intersection between two planes
# L = np.cross(N1, N2)
def plot_intersects(lat_a, lon_a, doa_a, lat_b, lon_b, doa_b, max_distance = 50000):
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
    mag = lambda q: np.sqrt(np.vdot(q, q))
    dist1 = mag(X1-plane_a[0])
    dist2 = mag(X2-plane_a[0])
    #return the (lon_lat pair of the closer intersection)
    if dist1 < dist2:
        i_lat = math.asin(X1[2]) * 180./np.pi
        i_long = math.atan2(X1[1], X1[0]) * 180./np.pi
    else:
        i_lat = math.asin(X2[2]) * 180./np.pi
        i_long = math.atan2(X2[1], X2[0]) * 180./np.pi

    check_bearing = v.get_heading((lat_a, lon_a), (i_lat, i_long))

    if abs(check_bearing - doa_a) < 5:
        km = v.inverse([lat_a, lon_a], [i_lat, i_long])
        if km[0] < max_distance:
            return (i_lat, i_long)
        else:
            return None

def process_data(database_name, outfile):
    conn = sqlite3.connect(database_name)
    c = conn.cursor()

    intersect_list = []

    c.execute("SELECT COUNT(*) FROM intersects")
    n_intersects = int(c.fetchone()[0])
    c.execute("SELECT longitude, latitude, time FROM intersects")
    intersect_array = np.array(c.fetchall())
    likely_location = []
    weighted_location = []
    ellipsedata = []

    n_std=3.0

    if intersect_array.size != 0:
        if ms.eps > 0:
            X = StandardScaler().fit_transform(intersect_array[:,0:2])

            # Compute DBSCAN
            db = DBSCAN(eps=ms.eps, min_samples=ms.min_samp).fit(X)
            core_samples_mask = np.zeros_like(db.labels_, dtype=bool)
            core_samples_mask[db.core_sample_indices_] = True
            labels = db.labels_

            intersect_array = np.column_stack((intersect_array, labels))

            # Number of clusters in labels, ignoring noise if present.
            n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise_ = list(labels).count(-1)
            clear(debugging)
            print('Number of clusters: %d' % n_clusters_)
            print('Outliers Removed: %d' % n_noise_)

            for x in range(n_clusters_):
                cluster = np.array([]).reshape(0,3)
                for y in range(len(intersect_array)):
                    if intersect_array[y][-1] == x:
                        cluster = np.concatenate((cluster, [intersect_array[y][0:-1]]), axis = 0)
                # weighted_location.append(np.average(cluster[:,0:2], weights=cluster[:,2], axis=0).tolist())
                clustermean = np.mean(cluster[:,0:2], axis=0)
                likely_location.append(clustermean.tolist())
                cov = np.cov(cluster[:,0], cluster[:,1])
                a = cov[0,0]
                b = cov[0,1]
                c = cov[1,1]
                lam1 = a+c/2 + np.sqrt((a-c/2)**2 + b**2)
                lam2 = a+c/2 - np.sqrt((a-c/2)**2 + b**2)
                pearson = b/np.sqrt(a * c)
                ell_radius_x = np.sqrt(1 + pearson) * np.sqrt(a) * n_std
                ell_radius_y = np.sqrt(1 - pearson) * np.sqrt(c) * n_std
                axis_x = v.inverse(Reverse(clustermean.tolist()), (ell_radius_x + clustermean[1], clustermean[0]))[0]
                axis_y = v.inverse(Reverse(clustermean.tolist()), (clustermean[1], ell_radius_y + clustermean[0]))[0]

                if b == 0 and a >= c:
                    rotation = 0
                elif b == 0 and a < c:
                    rotation = np.pi/2
                else:
                    rotation = math.atan2(lam1 - a, b)

                ellipsedata.append([axis_x, axis_y, rotation, *clustermean.tolist()])

            for x in likely_location:
                print(Reverse(x))
        else:
            likely_location = None

        for x in intersect_array:
            try:
                if x[-1] >= 0:
                    intersect_list.append(x[0:3].tolist())
            except IndexError:
                intersect_list.append(x.tolist())

        return likely_location, intersect_list, ellipsedata

    else:
        print("No Intersections.")
        return None

def write_geojson(best_point, all_the_points):
    all_pt_style = {"name": "Various Points", "marker-color": "#FF0000"}
    best_pt_style = {"name": "Most Likely TX Location", "marker-color": "#00FF00"}
    if all_the_points != None:
        all_the_points = Feature(properties = all_pt_style, geometry = MultiPoint(tuple(all_the_points)))
        with open(geofile, "w") as file1:
            if best_point != None:
                reversed_best_point = []
                for x in best_point:
                    reversed_best_point.append(Reverse(x))
                best_point = Feature(properties = best_pt_style, geometry = MultiPoint(tuple(reversed_best_point)))
                file1.write(str(FeatureCollection([best_point, all_the_points])))
            else:
                file1.write(str(FeatureCollection([all_the_points])))
        print(f"Wrote file {geofile}")

def write_czml(best_point, all_the_points, ellipsedata):
    point_properties = {
        "pixelSize":5.0,
        "heightReference":"RELATIVE_TO_GROUND",
      #   "color": {
      #       "rgba": [255, 0, 0, 255],
      # }
    }
    best_point_properties = {
        "pixelSize":12.0,
        "heightReference":"RELATIVE_TO_GROUND",
        "color": {
            "rgba": [0, 255, 0, 255],
      }
    }
    rx_properties = {
        "image":
            {
                "uri": "/static/tower.svg"
            },
        # "rotation": "Cesium.Math.PI_OVER_FOUR",
        "verticalOrigin": "BOTTOM",
        "scale": 0.75,
        "heightReference":"RELATIVE_TO_GROUND",
        "height": 48,
        "width": 48
        }

    ellipse_properties = {
        "granularity": 0.008722222,
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
    receiver_point_packets = []
    ellipse_packets = []

    if all_the_points != None and (ms.plotintersects or ms.eps == 0):
        all_the_points = np.array(all_the_points)
        scaled_time = minmax_scale(all_the_points[:,-1])
        all_the_points = np.column_stack((all_the_points, scaled_time))
        for x in all_the_points:
            rgb = hsvtorgb(x[-1]/3, 0.8, 0.8)
            color_property = {"color":{"rgba": [*rgb, 255]}}
            all_point_packets.append(Packet(id=str(x[1]) + ", " + str(x[0]),
            point={**point_properties, **color_property},
            position={"cartographicDegrees": [ x[0], x[1], 10 ]},
            ))

    if best_point != None:
        for x in best_point:
            best_point_packets.append(Packet(id=str(x[0]) + ", " + str(x[1]),
            point=best_point_properties,
            position={"cartographicDegrees": [ x[1], x[0], 15 ]}))

    if ellipsedata != None:
        for x in ellipsedata:
            # rotation = 2 * np.pi - x[2]
            if x[0] >= x[1]:
                semiMajorAxis = x[0]
                semiMinorAxis = x[1]
                rotation = 2 * np.pi - x[2]
                rotation += np.pi/2
                # print(f"{x[4], x[3]} is inveted")
            else:
                rotation = x[2]
                semiMajorAxis = x[1]
                semiMinorAxis = x[0]
                # print(f"{x[4], x[3]} is NOT inveted")

            ellipse_info = {"semiMajorAxis": semiMajorAxis, "semiMinorAxis": semiMinorAxis, "rotation": rotation}
            ellipse_packets.append(Packet(id=str(x[4]) + ", " + str(x[3]),
            ellipse={**ellipse_properties, **ellipse_info},
            position={"cartographicDegrees": [ x[3], x[4], 15 ]}))

    for x in receivers:
        receiver_point_packets.append(Packet(id=x.station_id,
        billboard=rx_properties,
        position={"cartographicDegrees": [ x.longitude, x.latitude, 15 ]}))

    with open("static/output.czml", "w") as file1:
        file1.write(str(Document([top] + best_point_packets + all_point_packets + receiver_point_packets + ellipse_packets)))

def hsvtorgb(h, s, v):
    rgb_out = []
    rgb = hsv_to_rgb(h, s, v)
    for x in rgb:
        rgb_out.append(int(x * 255))
    return rgb_out

def finish():
    clear(debugging)
    print("Processing, please wait.")
    ms.receiving = False
    if geofile != None:
        write_geojson(*process_data(database_name, geofile)[:2])
    kill(getpid(), signal.SIGTERM)

def Reverse(lst):
    lst.reverse()
    return lst

def clear(debugging):
    if not debugging:
      # for windows
        if name == 'nt':
            _ = system('cls')
        # for mac and linux(here, os.name is 'posix')
        else:
            _ = system('clear')

with open('accesstoken.txt', "r") as tokenfile:
    access_token = tokenfile.read().replace('\n', '')

@route('/static/<filepath:path>', name='static')
def server_static(filepath):
    return static_file(filepath, root='./static')

@get('/')
@get('/index')
@get('/cesium')
def cesium():
    write_czml(*process_data(database_name, geofile))
    return template('cesium.tpl',
    {'access_token':access_token,
    'epsilon':ms.eps,
    'minpower':ms.min_power,
    'minconf':ms.min_conf,
    'minpoints':ms.min_samp,
    'rx_state':"checked" if ms.receiving == True else "",
    'intersect_state':"checked" if ms.plotintersects == True else "",
    'receivers':receivers})

@get('/update')
def update_cesium():
    ms.eps = float(request.query.eps) if request.query.eps else ms.eps
    ms.min_conf = float(request.query.minconf) if request.query.minconf else ms.min_conf
    ms.min_power = float(request.query.minpower) if request.query.minpower else ms.min_power
    ms.min_samp = float(request.query.minpts) if request.query.minpts else ms.min_samp

    if request.query.rx == "true":
        ms.receiving = True
    elif request.query.rx == "false":
        ms.receiving = False
    if request.query.plotpts == "true":
        ms.plotintersects = True
    elif request.query.plotpts == "false":
        ms.plotintersects = False

    write_czml(*process_data(database_name, geofile))
    return "OK"

def start_server(ipaddr = "127.0.0.1", port=8080):
    run(host=ipaddr, port=port, quiet=True, server="paste", debug=True)

def run_receiver(receivers):
    clear(debugging)
    dots = 0

    conn = sqlite3.connect(database_name)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS intersects (time INTEGER, latitude REAL, longitude REAL, num_parents INTEGER)")

    while ms.receiving:
        if not debugging:
            print("Receiving" + dots*'.')
            print("Press Control+C to process data and exit.")

        intersect_list = np.array([]).reshape(0,3)
        for x in range(len(receivers)):
            for y in range(x):
                if x != y:
                    try:
                        if (receivers[x].confidence >= ms.min_conf and
                        receivers[y].confidence >= ms.min_conf and
                        receivers[x].power >= ms.min_power and
                        receivers[y].power >= ms.min_power and
                        abs(receivers[x].doa_time - receivers[y].doa_time) <= max_age and
                        receivers[x].frequency == receivers[y].frequency):
                            intersection = list(plot_intersects(receivers[x].latitude, receivers[x].longitude,
                            receivers[x].doa, receivers[y].latitude, receivers[y].longitude, receivers[y].doa))
                            print(intersection)
                            avg_conf = np.mean([receivers[x].confidence, receivers[y].confidence])
                            intersection.append(avg_conf)
                            intersection = np.array([intersection])
                            if intersection.any() != None:
                                intersect_list = np.concatenate((intersect_list, intersection), axis=0)

                    except TypeError: # I can't figure out what's causing me to need this here
                        pass

        if intersect_list.size != 0:
            avg_coord = np.average(intersect_list[:,0:2], weights=intersect_list[:,-1], axis = 0)
            to_table = [receivers[x].doa_time, avg_coord[0], avg_coord[1], len(intersect_list)]
            c.execute("INSERT INTO intersects VALUES (?,?,?,?)", to_table)
            conn.commit()

        for rx in receivers:
            try:
                rx.update()
            except IOError:
                print("Problem connecting to receiver.")
                ms.receiving = False

        time.sleep(1)
        if dots > 5:
            dots = 1
        else:
            dots += 1
        clear(debugging)

    conn.close()

if __name__ == '__main__':
    usage = "usage: %prog -r FILE -d FILE [options]"
    parser = OptionParser(usage=usage)
    parser.add_option("-r", "--receivers", dest="rx_file", help="REQUIRED List of receiver URLs", metavar="FILE")
    parser.add_option("-d", "--database", dest="database_name", help="REQUIRED Database File", metavar="FILE")
    parser.add_option("-g", "--geofile", dest="geofile", help="GeoJSON Output File", metavar="FILE")
    parser.add_option("-e", "--epsilon", dest="eps", help="Max Clustering Distance, Default 0.2. 0 to disable clustering.",
    metavar="NUMBER", type="float", default=0.2)
    parser.add_option("-c", "--confidence", dest="conf", help="Minimum confidence value, default 10",
    metavar="NUMBER", type="int", default=10)
    parser.add_option("-p", "--power", dest="pwr", help="Minimum power value, default 10",
    metavar="NUMBER", type="int", default=10)
    parser.add_option("-m", "--min-samples", dest="minsamp", help="Minimum samples per cluster. Default 20",
    metavar="NUMBER", type="int", default=20)
    parser.add_option("--plot_intersects", dest="plotintersects", help="""Plots all the intersect points in a cluster.
     Only applies when clustering is turned on. This creates larger CZML files.""",action="store_true")
    parser.add_option("-o", "--offline", dest="disable", help="Starts program with receiver turned off.",
    action="store_false", default=True)
    parser.add_option("--ip", dest="ipaddr", help="IP Address to serve from. Default 127.0.0.1",
    metavar="IP ADDRESS", type="str", default="127.0.0.1")
    parser.add_option("--port", dest="port", help="Port number to serve from. Default 8080",
    metavar="NUMBER", type="int", default=8080)
    parser.add_option("--debug", dest="debugging", help="Does not clear the screen. Useful for seeing errors and warnings.",
    action="store_true")
    (options, args) = parser.parse_args()

    mandatories = ['rx_file', 'database_name']
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

    max_age = 5

    web = threading.Thread(target=start_server,args=(options.ipaddr, options.port))
    web.daemon = True
    web.start()

    try:

        receivers = []
        with open(rx_file, "r") as file2:
            receiver_list = file2.readlines()
            for x in receiver_list:
                try:
                    receivers.append(receiver(x.replace('\n', '')))
                except IOError:
                    ms.receiving = False

        while True:
            if ms.receiving:
                run_receiver(receivers)
            clear(debugging)
            if not debugging:
                print("Receiver Paused")
            time.sleep(1)

    except KeyboardInterrupt:
        finish()
