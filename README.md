# DF Aggregator

## Dependencies:
- Python >= 3.6
- [numpy](https://numpy.org/install/)
- [scikit-learn](https://scikit-learn.org/stable/install.html)
- [python-geojson](https://python-geojson.readthedocs.io/en/latest/)
- [czml3](https://github.com/poliastro/czml3)
    - As of this writing, the version from pip does not support ellipses. Please use the version from GitHub.
- [geojson](https://pypi.org/project/geojson/)

## Other things you'll need:
- [Cesium Ion Token](https://cesium.com/docs/tutorials/quick-start/)
    - Create a single line file named ```accesstoken.txt```
- [Extended XML KerberosSDR Software](https://github.com/ckoval7/kerberossdr)

## Usage: df-aggregator.py [options]

### Required inputs:
-  -r FILE, --receivers=FILE
    - List of receiver URLs
    - Do not include quotes. Each receiver should be on a new line.

-  -d FILE, --database=FILE
    - Name of new or existing database to store intersect information.
    - If a database doesn't exist one is created.
    - Post processing math is done against the entire database.

### Optional Inputs:
-  -g FILE, --geofile=FILE
    - GeoJSON Output File
    - Conventional file extension: .geojson

-  -e Number, --epsilon=Number
    - Max Clustering Distance, Default 0.2.
    - 0 to disable clustering.
    - Point spread across a larger geographical area should require a smaller value.
    - Clustering should be disabled for moving targets.

-  -c Number, --confidence=Number
    - Minimum confidence value, default 10
    - Do not compute intersects for LOBs less than this value.

-  -p Number, --power=Number
    - Minimum power value, default 10
    - Do not compute intersects for LOBs less than this value.

-  -m Number, --min-samples=Number
    - Minimum samples per cluster. Default 20
    - A higher value can yield more accurate results, but requires more data.

-  --plot_intersects     
    - Plots all the intersect points in a cluster.
    - Only applies when clustering is turned on.
    - This creates larger CZML files.

-  -o, --offline
    - Starts program with receiver turned off.
    - Useful for looking at stored data when you can't connect to receivers.

-  --ip=IP ADDRESS
    - IP Address to serve from. Default 127.0.0.1

-  --port=NUMBER
    - Port number to serve from. Default 8080

-  --debug
    - Does not clear the screen. Useful for seeing errors and warnings.

Once the program is running, browse to 127.0.0.1:8080 or whatever IP/Port Number you specified.

  ![Screenshot](https://i.ibb.co/Ch1sFZH/Screenshot-from-2020-11-09-20-21-03.png)
