import math
import time
import threading
from datetime import datetime, timezone
from colorsys import hsv_to_rgb
import multiprocessing as _mp

# Use a private 'forkserver' context (not set_start_method, which mutates the
# global default) to avoid fork() deadlocks when the web server / db-writer
# threads are running in the parent. Scoped here so importing this module
# from a non-DBSCAN code path doesn't perturb anything.
_dbscan_ctx = _mp.get_context('forkserver')

import numpy as np
from scipy.spatial.distance import cdist
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler, minmax_scale
from geojson import MultiPoint, Feature, FeatureCollection
from czml3 import Packet, Document, CZML_VERSION
from czml3.properties import (Position, PositionList, Polyline,
    PolylineMaterial, PolylineOutlineMaterial, PolylineDashMaterial,
    Color, Clock, HeightReference)
from czml3.enums import HeightReferences
from czml3.types import TimeInterval

import vincenty as v
from config import (LOB_DRAW_DISTANCE_METERS, HEADING_DRAW_DISTANCE_METERS,
    MAX_INTERSECTION_DISTANCE_METERS, BEARING_CHECK_TOLERANCE_DEG,
    AUTOEPS_SLOPE_THRESHOLD, AUTOEPS_SAMPLE_SIZE, GAUSSIAN_ELLIPSE_SIGMA,
    MAX_INTERSECTS_PER_AOI, clear)


pipeline_stats_cache = {}
pipeline_stats_lock = threading.Lock()


def plot_polar(lat_a, lon_a, lat_a2, lon_a2):
    p1_lat1_rad = math.radians(lat_a)
    p1_long1_rad = math.radians(lon_a)
    p1_lat2_rad = math.radians(lat_a2)
    p1_long2_rad = math.radians(lon_a2)
    x1 = math.cos(p1_lat1_rad) * math.cos(p1_long1_rad)
    y1 = math.cos(p1_lat1_rad) * math.sin(p1_long1_rad)
    z1 = math.sin(p1_lat1_rad)
    x2 = math.cos(p1_lat2_rad) * math.cos(p1_long2_rad)
    y2 = math.cos(p1_lat2_rad) * math.sin(p1_long2_rad)
    z2 = math.sin(p1_lat2_rad)
    return ([x1, y1, z1], [x2, y2, z2])


def plot_intersects(lat_a, lon_a, doa_a, lat_b, lon_b, doa_b, max_distance=MAX_INTERSECTION_DISTANCE_METERS):
    coord_a2 = v.direct(lat_a, lon_a, doa_a, LOB_DRAW_DISTANCE_METERS)
    coord_b2 = v.direct(lat_b, lon_b, doa_b, LOB_DRAW_DISTANCE_METERS)
    plane_a = plot_polar(lat_a, lon_a, *coord_a2)
    plane_b = plot_polar(lat_b, lon_b, *coord_b2)
    N1 = np.cross(plane_a[0], plane_a[1])
    N2 = np.cross(plane_b[0], plane_b[1])
    L = np.cross(N1, N2)
    # |L| = sin(angle between the two great-circle planes). When the LOBs lie
    # on the same great circle (parallel / colinear / anti-parallel) |L|
    # collapses to machine-precision zero; L/|L| is NaN, which then either
    # (a) propagates through asin/atan2 and gets rejected by the tolerance
    # check below, but emits a RuntimeWarning per call from the polling
    # loop, or (b) in the anti-parallel sub-case slips through with a
    # geometrically meaningless point. Reject before normalizing.
    #
    # Threshold sized empirically: realistic near-parallel KrakenSDR
    # geometries (e.g. 1 km baseline with bearings 89°/90°) have |L| around
    # 1e-7. True degenerate inputs sit at 1e-21 or smaller (machine zero
    # times scale factors). 1e-12 is well below any plausibly-valid input
    # and safely above the degenerate floor — leaves the existing bearing
    # tolerance and max_distance checks in charge of "near-parallel but
    # nominally valid" rejection, where they belong.
    L_mag = np.sqrt(L[0]**2 + L[1]**2 + L[2]**2)
    if L_mag < 1e-12:
        return None
    X1 = L / L_mag
    X2 = -X1

    def mag(q):
        return np.sqrt(np.vdot(q, q))
    dist1 = mag(X1 - plane_a[0])
    dist2 = mag(X2 - plane_a[0])
    if dist1 < dist2:
        i_lat = math.asin(X1[2]) * 180. / np.pi
        i_long = math.atan2(X1[1], X1[0]) * 180. / np.pi
    else:
        i_lat = math.asin(X2[2]) * 180. / np.pi
        i_long = math.atan2(X2[1], X2[0]) * 180. / np.pi
    check_bearing = v.get_heading((lat_a, lon_a), (i_lat, i_long))
    # angular_diff_deg, not abs() — bearings near 0°/360° wrap. Without the
    # wrap-aware compare, a target due north (e.g. doa=359.7°,
    # check_bearing=0.3°) would be rejected as if it differed by 359°.
    if v.angular_diff_deg(check_bearing, doa_a) < BEARING_CHECK_TOLERANCE_DEG:
        km = v.inverse([lat_a, lon_a], [i_lat, i_long])
        if km[0] < max_distance:
            return (i_lat, i_long)
    return None


# Run DBSCAN in its own process so the OS reclaims its RAM on exit — sklearn's
# pairwise-distance allocations get expensive past ~10k intersections, and
# leaving them in the long-lived web process would balloon RSS over time.
def do_dbscan_batch(jobs, result_queue):
    out = {}
    for aoi_id, X, eps, minsamp in jobs:
        out[aoi_id] = DBSCAN(eps=eps, min_samples=minsamp).fit(X).labels_
    result_queue.put(out)


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


def process_data(db, epsilon, min_samp):
    global pipeline_stats_cache
    n_std = GAUSSIAN_ELLIPSE_SIGMA
    intersect_list = []
    likely_location = []
    ellipsedata = []
    per_aoi_stats = []
    total_db_intersections = 0
    total_dbscan_ms = 0.0
    resolved_epsilon = None
    resolved_min_samples = None
    clustering_enabled = (epsilon != "0")

    aoi_rows = db.query('SELECT uid FROM interest_areas WHERE aoi_type="aoi"')
    aoi_list = [item for sublist in aoi_rows for item in sublist]
    aoi_list.append(-1)

    stats_by_aoi = {}
    cluster_jobs = []
    postprocess_queue = []

    for aoi in aoi_list:
        print(f"Checking AOI {aoi}.")
        rows = db.query('''SELECT longitude, latitude, time FROM intersects
            WHERE aoi_id=? ORDER BY confidence DESC LIMIT ?''', [aoi, MAX_INTERSECTS_PER_AOI])
        intersect_array = np.array(rows)
        if intersect_array.size == 0:
            print(f"No Intersections in AOI {aoi}.")
            stats_by_aoi[aoi] = {"aoi_id": aoi, "input": 0, "in_cluster": 0, "clusters": 0, "outliers": 0}
            continue

        n_input = len(intersect_array)
        total_db_intersections += n_input

        if epsilon == "0":
            stats_by_aoi[aoi] = {"aoi_id": aoi, "input": n_input, "in_cluster": None, "clusters": None, "outliers": None}
            for x in intersect_array:
                intersect_list.append(x.tolist())
            continue

        X = StandardScaler().fit_transform(intersect_array[:, 0:2])
        n_points = len(X)

        if isinstance(min_samp, str):
            if min_samp == "auto":
                aoi_min_samp = max(3, round(0.05 * n_points))
            elif min_samp.isnumeric():
                aoi_min_samp = max(3, int(min_samp))
            else:
                stats_by_aoi[aoi] = {"aoi_id": aoi, "input": n_input, "in_cluster": 0, "clusters": 0, "outliers": n_input}
                continue
        else:
            aoi_min_samp = max(3, int(min_samp))

        if epsilon == "auto":
            aoi_eps = autoeps_calc(X)
            print(f"min_samp: {aoi_min_samp}, eps: {aoi_eps}")
            if aoi_eps <= 0:
                print("Could not determine a valid epsilon, skipping clustering for this AOI.")
                stats_by_aoi[aoi] = {"aoi_id": aoi, "input": n_input, "in_cluster": 0, "clusters": 0, "outliers": n_input}
                continue
        else:
            try:
                aoi_eps = float(epsilon)
            except (ValueError, TypeError):
                stats_by_aoi[aoi] = {"aoi_id": aoi, "input": n_input, "in_cluster": 0, "clusters": 0, "outliers": n_input}
                continue

        resolved_epsilon = aoi_eps
        resolved_min_samples = aoi_min_samp

        cluster_jobs.append((aoi, X, aoi_eps, aoi_min_samp))
        postprocess_queue.append((aoi, intersect_array, n_input, n_points))

    labels_by_aoi = {}
    dbscan_failed = False
    if cluster_jobs:
        print(f"Computing Clusters for {len(cluster_jobs)} AOIs.")
        result_q = _dbscan_ctx.Queue()
        starttime = time.time()
        dbproc = _dbscan_ctx.Process(target=do_dbscan_batch, args=(cluster_jobs, result_q))
        dbproc.daemon = True
        dbproc.start()
        timeout_s = 10 * max(1, len(cluster_jobs))
        try:
            labels_by_aoi = result_q.get(timeout=timeout_s)
        except Exception:
            print("DBSCAN took too long, terminated.")
            dbproc.terminate()
            dbproc.join(timeout=5)
            dbproc.close()
            dbscan_failed = True
        else:
            dbproc.join(timeout=5)
            if dbproc.is_alive():
                dbproc.terminate()
                dbproc.join(timeout=5)
            dbproc.close()
            total_dbscan_ms = (time.time() - starttime) * 1000
            print(f"DBSCAN took {total_dbscan_ms / 1000:.3f} seconds for all AOIs.")

    for aoi, intersect_array, n_input, n_points in postprocess_queue:
        labels = labels_by_aoi.get(aoi) if not dbscan_failed else None
        if labels is None:
            stats_by_aoi[aoi] = {"aoi_id": aoi, "input": n_input, "in_cluster": 0, "clusters": 0, "outliers": n_input}
            continue

        intersect_array = np.column_stack((intersect_array, labels))
        n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise_ = list(labels).count(-1)
        n_in_cluster = n_points - n_noise_
        print('Number of clusters: %d' % n_clusters_)
        print('Outliers Removed: %d' % n_noise_)

        stats_by_aoi[aoi] = {"aoi_id": aoi, "input": n_input, "in_cluster": n_in_cluster, "clusters": n_clusters_, "outliers": n_noise_}

        for x in range(n_clusters_):
            mask = labels == x
            cluster = intersect_array[mask, 0:3]
            clustermean = np.mean(cluster[:, 0:2], axis=0)
            likely_location.append(clustermean.tolist())
            cov_deg = np.cov(cluster[:, 0], cluster[:, 1])
            if (cov_deg[0, 0] == 0.0 and cov_deg[1, 1] == 0.0):
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
            if x[-1] >= 0:
                intersect_list.append(x[0:3].tolist())

    per_aoi_stats = [stats_by_aoi[aoi] for aoi in aoi_list if aoi in stats_by_aoi]
    _update_pipeline_stats(total_db_intersections, clustering_enabled, per_aoi_stats, total_dbscan_ms, resolved_epsilon, resolved_min_samples)
    return likely_location, intersect_list, ellipsedata


def _update_pipeline_stats(db_intersections, clustering_enabled, per_aoi, dbscan_ms, epsilon, min_samples):
    global pipeline_stats_cache
    total_in_cluster = 0
    total_clusters = 0
    total_outliers = 0
    for aoi in per_aoi:
        if aoi["in_cluster"] is not None:
            total_in_cluster += aoi["in_cluster"]
            total_clusters += aoi["clusters"]
            total_outliers += aoi["outliers"]
    stats = {
        "db_intersections": db_intersections,
        "clustering_enabled": clustering_enabled,
        "per_aoi": per_aoi,
        "totals": {
            "in_cluster": total_in_cluster,
            "clusters": total_clusters,
            "outliers_removed": total_outliers,
        },
        "dbscan_ms": round(dbscan_ms),
        "auto_params": {
            "epsilon": epsilon,
            "min_samples": min_samples,
        },
    }
    with pipeline_stats_lock:
        pipeline_stats_cache = stats


def get_pipeline_stats():
    with pipeline_stats_lock:
        if pipeline_stats_cache:
            return pipeline_stats_cache
        return {
            "db_intersections": 0,
            "clustering_enabled": False,
            "per_aoi": [],
            "totals": {"in_cluster": 0, "clusters": 0, "outliers_removed": 0},
            "dbscan_ms": 0,
            "auto_params": {"epsilon": None, "min_samples": None},
        }


def write_geojson(best_point, all_the_points, geofile):
    all_pt_style = {"name": "Various Intersections", "marker-color": "#FF0000"}
    best_pt_style = {"name": "Most Likely TX Location", "marker-color": "#00FF00"}
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


def write_czml(best_point, all_the_points, ellipsedata, plotallintersects, eps):
    clamp = HeightReference(heightReference=HeightReferences.CLAMP_TO_GROUND)
    no_depth = 1e12
    point_properties = {
        "pixelSize": 5.0,
        "heightReference": clamp,
        "disableDepthTestDistance": no_depth,
    }
    best_point_properties = {
        "pixelSize": 12.0,
        "heightReference": clamp,
        "disableDepthTestDistance": no_depth,
        "color": {"rgba": [0, 255, 0, 255]}
    }
    ellipse_properties = {
        "heightReference": clamp,
        "granularity": 0.008722222,
        "zIndex": 5,
        "material": {
            "solidColor": {"color": {"rgba": [255, 0, 0, 90]}}
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
                                            point={**point_properties, **color_property},
                                            position={"cartographicDegrees": [x[0], x[1], 0]}))

    if len(best_point) > 0:
        for x in best_point:
            gmaps_url = f"https://www.google.com/maps/dir/?api=1&destination={x[1]},+{x[0]}&travelmode=driving"
            best_point_packets.append(Packet(id=str(x[1]) + ", " + str(x[0]),
                                             point=best_point_properties,
                                             description=f"<a href='{gmaps_url}' target='_blank'>Google Maps Directions</a>",
                                             position={"cartographicDegrees": [x[0], x[1], 0]}))

    if len(ellipsedata) > 0:
        for x in ellipsedata:
            ellipse_info = {"semiMajorAxis": x[0], "semiMinorAxis": x[1], "rotation": x[2]}
            ellipse_packets.append(Packet(id=str(x[4]) + ", " + str(x[3]),
                                          ellipse={**ellipse_properties, **ellipse_info},
                                          position={"cartographicDegrees": [x[3], x[4], 0]}))

    return Document(packets=[top] + best_point_packets + all_point_packets + ellipse_packets).dumps()


def write_rx_czml(receiver_manager, ms):
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
        "heightReference": HeightReference(heightReference=HeightReferences.CLAMP_TO_GROUND),
        "disableDepthTestDistance": 1e12,
        "height": 48,
        "width": 48,
    }

    # Hold the lock while reading receiver state — the polling loop mutates
    # these fields concurrently and we need a consistent snapshot per packet.
    with receiver_manager.lock():
        for index, x in enumerate(receiver_manager.receivers):
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
                                                  color=Color(rgba=lob_color),
                                                  outlineColor=Color(rgba=[0, 0, 0, 255]),
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
                                                  polylineDash=PolylineDashMaterial(color=Color(
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
                                                 billboard={**rx_properties, **rx_icon},
                                                 position={"cartographicDegrees": [x.longitude, x.latitude, 15]}))

    return Document(packets=[top] + receiver_point_packets + lob_packets).dumps()


def _epoch_ms_to_iso(epoch_ms):
    dt = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%S.') + f'{dt.microsecond // 1000:03d}Z'


def lob_history_czml(db, ms, request_params):
    now_ms = time.time() * 1000
    start = int(request_params.get('start') or (now_ms - 3600000))
    end = int(request_params.get('end') or now_ms)
    min_conf = int(request_params.get('min_conf') or ms.min_conf)
    min_power = int(request_params.get('min_power') or ms.min_power)
    mode = request_params.get('mode') or "flash"
    freq = request_params.get('frequency')

    if freq:
        rows = db.query('''SELECT time, station_id, latitude, longitude, confidence, power, frequency, lob
            FROM lobs
            WHERE time BETWEEN ? AND ?
              AND confidence >= ?
              AND power >= ?
              AND frequency = ?
            ORDER BY time''', [start, end, min_conf, min_power, float(freq)])
    else:
        rows = db.query('''SELECT time, station_id, latitude, longitude, confidence, power, frequency, lob
            FROM lobs
            WHERE time BETWEEN ? AND ?
              AND confidence >= ?
              AND power >= ?
            ORDER BY time''', [start, end, min_conf, min_power])

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


def wr_aoi_czml(db):
    aoi_packets = []
    top = Packet(id="document", name="AOIs", version=CZML_VERSION)
    area_of_interest_properties = {
        "granularity": 0.008722222,
        "height": 0,
        "material": {"solidColor": {"color": {"rgba": [0, 0, 255, 25]}}},
        "outline": True,
        "outlineWidth": 2,
        "outlineColor": {"rgba": [53, 184, 240, 255]},
    }
    exclusion_area_properties = {
        "granularity": 0.008722222,
        "height": 0,
        "material": {"solidColor": {"color": {"rgba": [242, 10, 0, 25]}}},
        "outline": True,
        "outlineWidth": 2,
        "outlineColor": {"rgba": [224, 142, 0, 255]},
    }
    for x in db.fetch_aoi_data():
        aoi = {
            'uid': x[0], 'aoi_type': x[1],
            'latitude': x[2], 'longitude': x[3], 'radius': x[4]
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
