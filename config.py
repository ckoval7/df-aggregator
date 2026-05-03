from dataclasses import dataclass


@dataclass
class AppConfig:
    database_name: str
    debugging: bool = False
    geofile: str = None
    access_token: str = None
    ip: str = "127.0.0.1"
    port: int = 8080


@dataclass
class MathSettings:
    eps: str
    min_samp: str
    min_conf: float
    min_power: float
    receiving: bool = True
    plotintersects: bool = False
    lob_history_enabled: bool = True


# Distance Constants (meters)
LOB_DRAW_DISTANCE_METERS = 40000
HEADING_DRAW_DISTANCE_METERS = 20000
MAX_INTERSECTION_DISTANCE_METERS = 100000
MIN_SPATIAL_DIVERSITY_METERS = 500

# Time Constants (milliseconds)
MAX_TIME_DIFF_MS = 5000
SINGLE_RX_MIN_TIME_DIFF_MS = 10000
HISTORICAL_LOB_WINDOW_MS = 1200000

# Database Query Constants
MAX_INTERSECTS_PER_AOI = 25000
AUTOEPS_SAMPLE_SIZE = 2000

# Processing Constants
BEARING_CHECK_TOLERANCE_DEG = 5
# Single-receiver mobile mode: only intersect a current LOB with a historical
# one if their bearings differ by at least this many degrees. Bearings closer
# than this are too near-parallel to triangulate meaningfully.
MIN_LOB_PAIR_BEARING_DIFF_DEG = 5
AUTOEPS_SLOPE_THRESHOLD = 0.003
GAUSSIAN_ELLIPSE_SIGMA = 3.0

# Receiver Retry Constants
RECEIVER_MAX_RETRIES_TRANSIENT = 5
RECEIVER_MAX_RETRIES_PERSISTENT = 2
RECEIVER_BACKOFF_BASE_S = 2
RECEIVER_PROBE_INTERVAL_S = 30


def clear(debugging):
    if not debugging:
        print('\033[2J\033[H', end='', flush=True)
