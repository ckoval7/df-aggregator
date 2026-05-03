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

from sys import version_info

if version_info.major != 3 or version_info.minor < 6:
    print(
        "Looks like you're running python version "
        + str(version_info.major)
        + "."
        + str(version_info.minor)
        + ", which is no longer supported."
    )
    print("Your python version is out of date, please update to 3.6 or newer.")
    quit()

import argparse
import logging
import re
import signal
import threading
import time
from os import kill, getpid

from config import AppConfig, MathSettings
from database import Database
from receivers import ReceiverManager
import geo
import web

log = logging.getLogger(__name__)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DF Aggregator — networked radio direction finding"
    )
    parser.add_argument(
        "-d",
        "--database",
        dest="database_name",
        help="Database file",
        metavar="FILE",
        required=True,
    )
    parser.add_argument(
        "-r",
        "--receivers",
        dest="rx_file",
        help="List of receiver URLs",
        metavar="FILE",
    )
    parser.add_argument(
        "-g", "--geofile", dest="geofile", help="GeoJSON output file", metavar="FILE"
    )
    parser.add_argument(
        "-e",
        "--epsilon",
        dest="eps",
        help="Max clustering distance (default: auto)",
        metavar="NUMBER",
        default="auto",
    )
    parser.add_argument(
        "-c",
        "--confidence",
        dest="conf",
        help="Minimum confidence value (default: 10)",
        metavar="NUMBER",
        type=int,
        default=10,
    )
    parser.add_argument(
        "-p",
        "--power",
        dest="pwr",
        help="Minimum power value (default: 10)",
        metavar="NUMBER",
        type=int,
        default=10,
    )
    parser.add_argument(
        "-m",
        "--min-samples",
        dest="minsamp",
        help="Minimum samples per cluster (default: auto)",
        metavar="NUMBER",
        default="auto",
    )
    parser.add_argument(
        "--plot_intersects",
        dest="plotintersects",
        help="Plot all intersect points in clusters",
        action="store_true",
    )
    parser.add_argument(
        "-o",
        "--offline",
        dest="disable",
        help="Start with receiver turned off",
        action="store_false",
        default=True,
    )
    parser.add_argument(
        "--access_token",
        dest="token_file",
        help="Cesium access token file",
        metavar="FILE",
    )
    parser.add_argument(
        "--ip",
        dest="ipaddr",
        help="IP address to serve from (default: 127.0.0.1)",
        metavar="IP_ADDRESS",
        type=str,
        default="127.0.0.1",
    )
    parser.add_argument(
        "--port",
        dest="port",
        help="Port number to serve from (default: 8080)",
        metavar="NUMBER",
        type=int,
        default=8080,
    )
    parser.add_argument(
        "--debug",
        dest="debugging",
        help="Enable DEBUG-level logging and Bottle debug mode",
        action="store_true",
    )
    parser.add_argument(
        "--log-file",
        dest="log_file",
        help="Also write logs to this file",
        metavar="PATH",
    )
    parser.add_argument(
        "--no-lob-history",
        dest="no_lob_history",
        help="Disable LOB history recording",
        action="store_true",
    )
    options = parser.parse_args()

    root_level = logging.DEBUG if options.debugging else logging.INFO
    handlers = [logging.StreamHandler()]
    if options.log_file:
        handlers.append(logging.FileHandler(options.log_file))
    for h in handlers:
        h.setLevel(root_level)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )

    # gevent's WSGI handler logs every request at INFO, including the 2.5s UI
    # polls — too chatty. Demote successful (2xx/3xx) responses to DEBUG;
    # keep 4xx/5xx visible at INFO so error responses still show up.
    _access_log_re = re.compile(r'" (\d{3}) ')

    def _demote_successful_access(record):
        msg = record.getMessage()
        m = _access_log_re.search(msg)
        if m and m.group(1)[0] in ("2", "3"):
            record.levelno = logging.DEBUG
            record.levelname = "DEBUG"
        return True

    logging.getLogger("geventwebsocket.handler").addFilter(_demote_successful_access)

    access_token = None
    if options.token_file:
        with open(options.token_file, "r") as token:
            access_token = token.read().replace("\n", "")

    app_config = AppConfig(
        database_name=options.database_name,
        debugging=options.debugging,
        geofile=options.geofile,
        access_token=access_token,
        ip=options.ipaddr,
        port=options.port,
    )

    ms = MathSettings(options.eps, options.minsamp, options.conf, options.pwr)
    ms.receiving = options.disable
    ms.plotintersects = options.plotintersects
    ms.lob_history_enabled = not options.no_lob_history

    db = Database(app_config)
    rx_mgr = ReceiverManager(db)

    def finish():
        log.info("Processing, please wait.")
        ms.receiving = False
        rx_mgr.save_to_db()
        db.close()
        if app_config.geofile is not None:
            geo.write_geojson(
                *geo.process_data(db, ms.eps, ms.min_samp)[:2], app_config.geofile
            )
        kill(getpid(), signal.SIGTERM)

    dbwriter = threading.Thread(target=db.writer_loop)
    dbwriter.daemon = True
    dbwriter.start()

    web_app = web.create_routes(app_config, ms, db, rx_mgr)
    web_thread = threading.Thread(target=web.start_server, args=(app_config, web_app))
    web_thread.daemon = True
    web_thread.start()

    try:
        rx_mgr.read_from_db()
        if options.rx_file:
            with open(options.rx_file, "r") as file2:
                receiver_list = file2.readlines()
                for x in receiver_list:
                    receiver_url = x.replace("\n", "")
                    rx_mgr.add(receiver_url)

        prev_receiving = None
        while True:
            if ms.receiving != prev_receiving:
                log.info("Receiver running" if ms.receiving else "Receiver paused")
                prev_receiving = ms.receiving
            if ms.receiving:
                rx_mgr.run_loop(ms)
            time.sleep(1)

    except KeyboardInterrupt:
        finish()
