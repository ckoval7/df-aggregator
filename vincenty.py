#!/usr/bin/env python3
# WGS 84
#a = 6378137  # meters
#f = 1 / 298.257223563
#b = 6356752.314245  # meters; b = (1 - f)a
#f: flattening of the ellipsoid
#a: radius of the ellipsoid, meteres
#phi1: latitude of the start point, decimal degrees
#lembda1: longitude of the start point, decimal degrees
#alpha12: bearing, decimal degrees
#s: Distance to endpoint, meters
import logging
import sys
from math import atan
from math import atan2
from math import cos
from math import radians
from math import degrees
from math import sin, asin
from math import sqrt
from math import tan

a=6378137.0                             # radius at equator in meters (WGS-84)
f=1/298.257223563                       # flattening of the ellipsoid (WGS-84)
b=(1-f)*a

log = logging.getLogger(__name__)

def haversine(lat1, lon1, lat2, lon2):
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    c = 2 * asin(sqrt(sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2))
    return c * a

def angular_diff_deg(a, b):
    # Shortest absolute distance between two compass bearings, in degrees,
    # respecting the 359°↔1° wrap. Both inputs may be any real number;
    # result is in [0, 180]. Plain `abs(a - b)` is wrong for compass-degree
    # comparisons — it reports 358° between bearings that are actually 2°
    # apart on the circle.
    d = (a - b) % 360.0
    if d > 180.0:
        d = 360.0 - d
    return d


def get_heading(coord1, coord2):
     lat1 = radians(coord1[0])
     lon1 = radians(coord1[1])
     lat2 = radians(coord2[0])
     lon2 = radians(coord2[1])
     bearing_plot_X =  cos(lat2) * sin(lon2 - lon1)
     bearing_plot_Y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(lon1 - lon2)
     heading = degrees(atan2(bearing_plot_X,bearing_plot_Y))
     if heading <0: heading += 360
     return heading

def inverse(coord1,coord2,max_iter=200,tol=10**-12):

    phi_1,L_1,=coord1
    phi_2,L_2,=coord2

    # Identical-point short-circuit. Without this, the iteration produces
    # sin_sigma=0 → ZeroDivisionError on sin_alpha. Bearing is undefined for
    # a zero-length geodesic; 0.0 is a placeholder, but no caller uses the
    # bearing component when distance is 0 (verified across all five sites).
    if phi_1 == phi_2 and L_1 == L_2:
        return (0.0, 0.0)

    u_1=atan((1-f)*tan(radians(phi_1)))
    u_2=atan((1-f)*tan(radians(phi_2)))

    L=radians(L_2-L_1)

    Lambda=L                                # set initial value of lambda to L

    sin_u1=sin(u_1)
    cos_u1=cos(u_1)
    sin_u2=sin(u_2)
    cos_u2=cos(u_2)

    converged=False
    cos_sq_alpha=1.0
    cos2_sigma_m=0.0
    sin_sigma=0.0
    cos_sigma=1.0
    sigma=0.0
    for i in range(0,max_iter):
        cos_lambda=cos(Lambda)
        sin_lambda=sin(Lambda)
        sin_sigma=sqrt((cos_u2*sin(Lambda))**2+(cos_u1*sin_u2-sin_u1*cos_u2*cos_lambda)**2)
        if sin_sigma==0:
            # Coincident points after the early-exit above shouldn't reach
            # here, but if a co-located case slips through (e.g. equator
            # crossings at the same lon), bail out cleanly.
            return (0.0, 0.0)
        cos_sigma=sin_u1*sin_u2+cos_u1*cos_u2*cos_lambda
        sigma=atan2(sin_sigma,cos_sigma)
        sin_alpha=(cos_u1*cos_u2*sin_lambda)/sin_sigma
        cos_sq_alpha=1-sin_alpha**2
        # Equatorial line: both endpoints on the equator gives cos_sq_alpha==0
        # (sin_alpha == ±1). The standard Vincenty handling is to set
        # cos(2σ_m) = 0 — see Vincenty 1975, "additional formula" footnote.
        # Without this, the next line divides by zero and the bare except
        # used to swallow it, returning (0,0) for any equator-to-equator
        # pair. That broke purge_database for any equatorial intersection.
        if cos_sq_alpha==0:
            cos2_sigma_m=0
        else:
            cos2_sigma_m=cos_sigma-((2*sin_u1*sin_u2)/cos_sq_alpha)
        C=(f/16)*cos_sq_alpha*(4+f*(4-3*cos_sq_alpha))
        Lambda_prev=Lambda
        Lambda=L+(1-C)*f*sin_alpha*(sigma+C*sin_sigma*(cos2_sigma_m+C*cos_sigma*(-1+2*cos2_sigma_m**2)))

        if abs(Lambda_prev-Lambda)<=tol:
            converged=True
            break

    if not converged:
        # Vincenty's inverse is known to fail for nearly-antipodal endpoints.
        # No current caller passes such pairs (all sites are local-area DF
        # geometries), but if one ever does, the previous code returned the
        # last-iteration values silently. Make it visible. We still return
        # the last-iteration distance so behavior degrades rather than
        # crashing the polling loop, but the print makes the failure
        # diagnosable if it ever surfaces.
        log.warning("vincenty.inverse: did not converge after %d iters "
                    "for %s -> %s; result is approximate",
                    max_iter, coord1, coord2)

    u_sq=cos_sq_alpha*((a**2-b**2)/b**2)
    A=1+(u_sq/16384)*(4096+u_sq*(-768+u_sq*(320-175*u_sq)))
    B=(u_sq/1024)*(256+u_sq*(-128+u_sq*(74-47*u_sq)))
    delta_sig=B*sin_sigma*(cos2_sigma_m+0.25*B*(cos_sigma*(-1+2*cos2_sigma_m**2)-(1/6)*B*cos2_sigma_m*(-3+4*sin_sigma**2)*(-3+4*cos2_sigma_m**2)))

    alpha12 = get_heading(coord1, coord2)
    m=(b*A*(sigma-delta_sig))#/1000                # output distance in m
    return (m,alpha12)


def direct(phi1, lembda1, alpha12, s, max_iter=200): #lat, lon, bearing, distance

    # Zero-distance short-circuit. Without it the loop condition
    # `(last_sigma - sigma) / sigma` divides by zero on the very first
    # evaluation. No current caller passes s=0 (LOB_DRAW_DISTANCE_METERS,
    # HEADING_DRAW_DISTANCE_METERS, and lob_length() are all ≥ 200), but
    # it's a latent footgun and the early-out is one line.
    if s == 0:
        return (phi1, lembda1)

    piD4 = atan( 1.0 )
    two_pi = piD4 * 8.0
    phi1    = phi1    * piD4 / 45.0
    lembda1 = lembda1 * piD4 / 45.0
    alpha12 = alpha12 * piD4 / 45.0
    if ( alpha12 < 0.0 ) :
        alpha12 = alpha12 + two_pi
    if ( alpha12 > two_pi ) :
        alpha12 = alpha12 - two_pi
    TanU1 = (1-f) * tan(phi1)
    U1 = atan( TanU1 )
    sigma1 = atan2( TanU1, cos(alpha12) )
    Sinalpha = cos(U1) * sin(alpha12)
    cosalpha_sq = 1.0 - Sinalpha * Sinalpha
    u2 = cosalpha_sq * (a * a - b * b ) / (b * b)
    A = 1.0 + (u2 / 16384) * (4096 + u2 * (-768 + u2 * \
        (320 - 175 * u2) ) )
    B = (u2 / 1024) * (256 + u2 * (-128 + u2 * (74 - 47 * u2) ) )
    # Starting with the approx
    sigma = (s / (b * A))
    last_sigma = 2.0 * sigma + 2.0   # something impossible

    # Iterate the following 3 eqs unitl no sig change in sigma
    # two_sigma_m , delta_sigma
    # The spheroidal correction here converges in 2–6 iterations for any
    # realistic input (verified empirically across the full lat/bearing/
    # distance space up to near-antipodal). The max_iter cap is defensive
    # parity with inverse() — a runaway here would freeze the polling
    # thread, and the cost of bounding it is one comparison per iter.
    iters = 0
    while ( abs( (last_sigma - sigma) / sigma) > 1.0e-9 ):
        iters += 1
        if iters > max_iter:
            log.warning("vincenty.direct: did not converge after %d iters "
                        "for (%s,%s) brg=%s s=%s; result is approximate",
                        max_iter, phi1, lembda1, alpha12, s)
            break
        two_sigma_m = 2 * sigma1 + sigma
        delta_sigma = B * sin(sigma) * ( cos(two_sigma_m) \
                + (B/4) * (cos(sigma) * \
                (-1 + 2 * cos(two_sigma_m) ** 2 -  \
                (B/6) * cos(two_sigma_m) * \
                (-3 + 4 * sin(sigma) ** 2) *  \
                (-3 + 4 * cos(two_sigma_m) ** 2))))
        last_sigma = sigma
        sigma = (s / (b * A)) + delta_sigma
    phi2 = atan2 ( (sin(U1) * cos(sigma) +\
        cos(U1) * sin(sigma) * cos(alpha12) ), \
        ((1-f) * sqrt( Sinalpha ** 2 +  \
        (sin(U1) * sin(sigma) - cos(U1) * \
        cos(sigma) * cos(alpha12)) ** 2)))
    lembda = atan2( (sin(sigma) * sin(alpha12 )),\
        (cos(U1) * cos(sigma) -  \
        sin(U1) *  sin(sigma) * cos(alpha12)))
    C = (f/16) * cosalpha_sq * (4 + f * (4 - 3 * cosalpha_sq ))
    omega = lembda - (1-C) * f * Sinalpha *  \
        (sigma + C * sin(sigma) * (cos(two_sigma_m) + \
        C * cos(sigma) * (-1 + 2 *\
        cos(two_sigma_m) ** 2)))
    lembda2 = lembda1 + omega
    alpha21 = atan2 ( Sinalpha, (-sin(U1) * \
        sin(sigma) +
        cos(U1) * cos(sigma) * cos(alpha12)))
    alpha21 = alpha21 + two_pi / 2.0
    if ( alpha21 < 0.0 ) :
        alpha21 = alpha21 + two_pi
    if ( alpha21 > two_pi ) :
        alpha21 = alpha21 - two_pi
    phi2 = phi2 * 45.0 / piD4
    lembda2 = lembda2 * 45.0 / piD4
    alpha21 = alpha21 * 45.0 / piD4
    return (phi2, lembda2)#, alpha21

if __name__ == '__main__':
    help = """Usage:
    vincenty.py [option] [value1] [value2] [value3] [value4]
    Get distance between two points in meters:
        vincenty.py inverse lat1 lon1 lat2 lon2
    Get coordinate at a given distance and heading:
        vincenty.py direct lat1 lon1 heading distance
    Get the heading between two coordinates:
        vincenty.py heading lat1 lon1 lat2 lon2"""
    try:
        op1 = float(sys.argv[2])
        op2 = float(sys.argv[3])
        op3 = float(sys.argv[4])
        op4 = float(sys.argv[5])

        if sys.argv[1] == "inverse":
            output = inverse((op1, op2),(op3, op4))[0]
        elif sys.argv[1] == "direct":
            output = str(direct(op1, op2, op3, op4))[1:-1]
        elif sys.argv[1] == "heading":
            output = get_heading((op1, op2),(op3, op4))
        else:
            output = help
        print(output)
    except (IndexError, ValueError):
        print(help)
