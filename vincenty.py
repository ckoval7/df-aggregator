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
import sys
from math import atan
from math import atan2
from math import cos
from math import radians
from math import degrees
from math import sin, asin
from math import sqrt
from math import tan
from math import pow

a=6378137.0                             # radius at equator in meters (WGS-84)
f=1/298.257223563                       # flattening of the ellipsoid (WGS-84)
b=(1-f)*a

def haversine(lat1, lon1, lat2, lon2):
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    c = 2 * asin(sqrt(sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2))
    return c * a

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

def inverse(coord1,coord2,maxIter=200,tol=10**-12):
    global a
    global f
    global b

    phi_1,L_1,=coord1
    phi_2,L_2,=coord2

    u_1=atan((1-f)*tan(radians(phi_1)))
    u_2=atan((1-f)*tan(radians(phi_2)))

    L=radians(L_2-L_1)

    Lambda=L                                # set initial value of lambda to L

    sin_u1=sin(u_1)
    cos_u1=cos(u_1)
    sin_u2=sin(u_2)
    cos_u2=cos(u_2)

    try:
        iters=0
        for i in range(0,maxIter):
            iters+=1

            cos_lambda=cos(Lambda)
            sin_lambda=sin(Lambda)
            sin_sigma=sqrt((cos_u2*sin(Lambda))**2+(cos_u1*sin_u2-sin_u1*cos_u2*cos_lambda)**2)
            cos_sigma=sin_u1*sin_u2+cos_u1*cos_u2*cos_lambda
            sigma=atan2(sin_sigma,cos_sigma)
            sin_alpha=(cos_u1*cos_u2*sin_lambda)/sin_sigma
            cos_sq_alpha=1-sin_alpha**2
            cos2_sigma_m=cos_sigma-((2*sin_u1*sin_u2)/cos_sq_alpha)
            C=(f/16)*cos_sq_alpha*(4+f*(4-3*cos_sq_alpha))
            Lambda_prev=Lambda
            Lambda=L+(1-C)*f*sin_alpha*(sigma+C*sin_sigma*(cos2_sigma_m+C*cos_sigma*(-1+2*cos2_sigma_m**2)))

            # successful convergence
            diff=abs(Lambda_prev-Lambda)
            if diff<=tol:
                break

        u_sq=cos_sq_alpha*((a**2-b**2)/b**2)
        A=1+(u_sq/16384)*(4096+u_sq*(-768+u_sq*(320-175*u_sq)))
        B=(u_sq/1024)*(256+u_sq*(-128+u_sq*(74-47*u_sq)))
        delta_sig=B*sin_sigma*(cos2_sigma_m+0.25*B*(cos_sigma*(-1+2*cos2_sigma_m**2)-(1/6)*B*cos2_sigma_m*(-3+4*sin_sigma**2)*(-3+4*cos2_sigma_m**2)))

        alpha12 = get_heading(coord1, coord2)
        m=(b*A*(sigma-delta_sig))#/1000                # output distance in m
        return (m,alpha12)
    except ZeroDivisionError:
        return (0,0)


def direct(phi1, lembda1, alpha12, s): #lat, lon, bearing, distance
    global a
    global f
    global b

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
    while ( abs( (last_sigma - sigma) / sigma) > 1.0e-9 ):
        two_sigma_m = 2 * sigma1 + sigma
        delta_sigma = B * sin(sigma) * ( cos(two_sigma_m) \
                + (B/4) * (cos(sigma) * \
                (-1 + 2 * pow( cos(two_sigma_m), 2 ) -  \
                (B/6) * cos(two_sigma_m) * \
                (-3 + 4 * pow(sin(sigma), 2 )) *  \
                (-3 + 4 * pow( cos (two_sigma_m), 2 )))))
        last_sigma = sigma
        sigma = (s / (b * A)) + delta_sigma
    phi2 = atan2 ( (sin(U1) * cos(sigma) +\
        cos(U1) * sin(sigma) * cos(alpha12) ), \
        ((1-f) * sqrt( pow(Sinalpha, 2) +  \
        pow(sin(U1) * sin(sigma) - cos(U1) * \
        cos(sigma) * cos(alpha12), 2))))
    lembda = atan2( (sin(sigma) * sin(alpha12 )),\
        (cos(U1) * cos(sigma) -  \
        sin(U1) *  sin(sigma) * cos(alpha12)))
    C = (f/16) * cosalpha_sq * (4 + f * (4 - 3 * cosalpha_sq ))
    omega = lembda - (1-C) * f * Sinalpha *  \
        (sigma + C * sin(sigma) * (cos(two_sigma_m) + \
        C * cos(sigma) * (-1 + 2 *\
        pow(cos(two_sigma_m), 2) )))
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
    except:
        print(help)
