import pymssql
import math
import heapq
import pyproj
import shapely
from shapely.geometry import Point, LineString
from shapely.wkt import dumps, loads
from pyparsing import commaSeparatedList

conn_read  = pymssql.connect(host='RDSQLDEV\\RDSQLDEV')
cur_read = conn_read.cursor()

def meridian_zone(state_code, county_name, twnshp, twnshp_dir, range_, range_dir):

    # Alabama state
    if state_code == 'AL':
        if county_name in ('PICKENS', 'GREENE', 'TUSCALOOSA', 'BIBB', 'SHELBY', 'CLAY'):
            return 16 if twnshp_dir == 'S' else 25
        elif county_name == 'HOUSTON':
            return 29 if twnshp == 7 and range_ > 8 else 25
        elif county_name == 'GENEVA':
            return 29 if twnshp in (6,7) else 25
        elif county_name == 'COVINGTON':
            return 29 if twnshp == 6 and range_ < 23 else 25

    # Arizona state
    elif state_code == 'AZ':
        if county_name == 'APACHE':
            return 22 if range_dir == 'W' else 14
        if county_name == 'YUMA':
            return 27 if range_dir == 'E' else 14

    #Arkansas state
    elif state_code == 'AK':
        if county_name in ('PHILLIPS', 'DESHA'):
            return 10 if range_dir == 'W' else 5

    # California state
    elif state_code == 'CA':
        if county_name in ('SAN LUIS OBISPO', 'SANTA BARBARA', 'KERN', 'INYO'):
            return 27 if twnshp_dir == 'N' else 21
        elif county_name == 'SAN BERNARDINO':
            return 27 if twnshp_dir == 'N' and twnshp < 4 else 21
        elif county_name =='MENDOCHINO':
            return 21 if twnshp_dir == 'N' else 15
        elif county_name =='TRINITY':
            return 21 if range_dir == 'W' else 15
        elif county_name =='SISKIYOU':
            return 21 if twnshp > 20 else 15
        elif county_name =='IMPERIAL':
            return 27 if range_dir == 'E' else 14

    # Colorado state
    elif state_code == 'CO':
        if county_name in ('COSTILLA', 'ALAMOSA', 'CUSTER', 'FREMONT'):
            return 23 if range_dir == 'E' else 6
        elif county_name == 'SAGUACHE':
            return 23 if range_dir == 'E' and range_ < 72 else 6
        elif county_name in ('CHAFFEE', 'GUNNISON'):
            return 23 if twnshp_dir == 'N' else 6
        elif county_name == 'DELTA':
            return 23 if twnshp_dir == 'N' else 6 if range_dir == 'W' else 31
        elif county_name == 'MESA':
            return 23 if twnshp_dir == 'N' and range_ > 13 else 6 if range_ > 5 else 31

    # Ilinois state
    elif state_code == 'IL':
        if county_name in ('CAMPAIGN', 'COLES', 'DOUGLAS', 'EDWARDS', 'FORD', 'IROQUOIS', 'JASPER', 'KANKAKEE', 'RICHLAND', 'WHITE'):
            return 3 if range_dir == 'E' else 2
        elif county_name in ('LEE', 'OGLE', 'WINNEBAGO', 'MARSHALL', 'PUTNAM'):
            return 3 if range_ <= 3 else 4



    else:
        print 'Unhadled dual meridian zone for county: %s, %s' % (state_code, county_name)


def extend_line (line_string, distance):
    p1,p2 = Point(line_string.coords[0]), Point(line_string.coords[-1])
    p3 = Point(p1.x + (p1.x - p2.x) / line_string.length * distance, p1.y + (p1.y - p2.y) / line_string.length * distance)
    p4 = Point(p2.x + (p2.x - p1.x) / line_string.length * distance, p2.y + (p2.y - p1.y) / line_string.length * distance)
    return LineString([p3, p4])


def transform(epsg_in, epsg_out, point_in):
    # define source and destination coordinate systems based on the ESPG code
    srcProj = pyproj.Proj(init='epsg:%i' % epsg_in, preserve_units=True)
    dstProj = pyproj.Proj(init='epsg:%i' % epsg_out, preserve_units=True)

    # performes transformation
    point_out = Point(pyproj.transform(srcProj, dstProj, point_in.x, point_in.y))
    # print '(%.5f, %.5f) EPSG: %i => (%.5f, %.5f) EPSG: %i' % (x_in, y_in, epsg_in, x_out, y_out, epsg_out)
    return point_out


def ft2m(feet):
    return feet * 0.3048


def rules(dir1, dir2, lines):

    if dir1 in ('FNL', 'FSL', 'FWL', 'FEL') and dir2 in ('FNL', 'FSL', 'FWL', 'FEL'):
        return {'FNL': lines['north'], 'FSL': lines['south'], 'FEL': lines['east'], 'FWL': lines['west']}

    if dir1 in ('FNEL', 'FSEL', 'FNWL', 'FSWL') and dir2 in ('FNEL', 'FSEL', 'FNWL', 'FSWL'):
        return {'FNEL': lines['north'], 'FSWL': lines['south'], 'FSEL': lines['east'], 'FNWL': lines['west']}

    if dir1 in ('FNL', 'FSL', 'FNWL', 'FSEL') and dir2 in ('FNL', 'FSL', 'FNWL', 'FSEL'):
        return {'FNL': lines['north'], 'FSL': lines['south'], 'FSEL': lines['east'], 'FNWL': lines['west']}

    return None


def calc_point_from_offsets(four_corners_wm, ftg1, dir1, ftg2, dir2):
    dir1, dir2 = dir1.upper(), dir2.upper()
    centroid_wm = Point(avg(pnt.x for pnt in four_corners_wm.values()), avg(pnt.y for pnt in four_corners_wm.values()))
    # centroid_wm = four_corners_wm.centroid
    centroid_nad83 = transform(3857, 4269, centroid_wm)

    ftg1, ftg2 = float(ftg1), float(ftg2)

    wm_corr_factor = math.cos(centroid_nad83.y * math.pi / 180.0) # web mercator distance correction factor
    # print 'wm_corr_factor: ', wm_corr_factor
    
    # create four LineStrings
    lines = {
        'north' : LineString([four_corners_wm['NW'], four_corners_wm['NE']]),
        'east'  : LineString([four_corners_wm['NE'], four_corners_wm['SE']]),
        'south' : LineString([four_corners_wm['SE'], four_corners_wm['SW']]),
        'west'  : LineString([four_corners_wm['SW'], four_corners_wm['NW']]),
    }

    # lines = {'FNL': north_line, 'FSL': south_line, 'FEL': east_line, 'FWL': west_line, 'FSEL': east_line, 'FNEL': north_line}
    lines = rules(dir1, dir2, lines)
    if not lines: 
        print '\tcould not resolve offset lines.'
        return None
    # offset_line1 = lines.get(dir1.upper(), None).parallel_offset(ft2m(ftg1) / wm_corr_factor, 'right')
    # offset_line2 = lines.get(dir2.upper(), None).parallel_offset(ft2m(ftg2) / wm_corr_factor, 'right')
    offset_line1 = lines.get(dir1, None).parallel_offset(ft2m(ftg1), 'right')  # without the correction factor
    offset_line2 = lines.get(dir2, None).parallel_offset(ft2m(ftg2), 'right')  # without the correction factor

    # for pnt in offset_line1.coords:
    #     print pnt

    pnt = offset_line1.intersection(offset_line2)
    if not pnt: 
        # extend both lines for 1000m
        print'\tintersection not found, extending lines and re-intersecting...'
        offset_line1 = extend_line(offset_line1, 1000)
        offset_line2 = extend_line(offset_line2, 1000)
        
        pnt = offset_line1.intersection(offset_line2)
        if not pnt:
            print'\tcould not resolve the intersection'
            return None

    return transform(3857, 4269, pnt)


def bearing_deg(pnt1, pnt2):
    return math.atan2(pnt2.x-pnt1.x, pnt2.y-pnt1.y) * 180.0 / math.pi


def queryWKT(table, where_clause, cursor=cur_read ):
    # select_statement = 'SELECT  [geom].STAsText() FROM [GISCoreData].[dbo].[TexasSurveys] WHERE %s' % where_clause
    select_statement = 'SELECT  geom.STAsText() FROM %s WHERE %s' % (table, where_clause)
    # print select_statement
    cursor.execute(select_statement)
    row = cursor.fetchone()
    # print row
    while row:
        # print row[0]
        row1 = cursor.fetchone()
        if row1: 
            print '\tmore than one polygon returned from the statement: %s' % select_statement
            return None
        return row[0]
    print '\tno record returned based on statement: %s' % select_statement
    return None


def avg(values):
    sum1 = 0.0
    n=0
    for v in values:
        n += 1
        sum1 += v
    return sum1 / n


class CornerDetector():
    def __init__(self, polygon_WKT):
        self.polygon_WKT = polygon_WKT
        self.poly = None
        self.points = None
        self.four_corners = None
        self.calc_four_corners()

    def parseWKT(self):
        # example of self.polygonWKT:
        # "POLYGON ((-10626837.21794926 3757110.4207815621, -10626540.482634166 3757112.4199904846, -10626540.670118278 3757600.8320014365, -10628182.246195693 3757573.3814624925, -10628174.337145651 3757112.1032040166, -10626837.21794926 3757110.4207815621))"
        poly = loads(self.polygon_WKT)

        #create a convex hull in order to take care of irregular shapes
        self.poly = poly.convex_hull

        self.set_points([Point(pnt) for pnt in self.poly.exterior.coords])

    def remove_duplicate_points(self):
        unique_points = [self.points[0]]

        for pnt in self.points:
            unique = True
            for uni_pnt in unique_points:
                if pnt.x == uni_pnt.x and pnt.y == uni_pnt.y:
                    unique = False
            if unique:
                unique_points.append(pnt)
        #print '#points: %i, #no dups: %i' % (len(self.points), len(unique_points))
        self.points = unique_points

    def get_points(self):
        return self.points

    def set_points(self, points):
        self.points = points

    def internal_angle(self, currPoint, prevPoint, nextPoint):
        try:
            slope_currPoint_prevPoint = (prevPoint.y - currPoint.y)/(prevPoint.x - currPoint.x)
        except ZeroDivisionError:
            slope_currPoint_prevPoint = 99999
        try:
            slope_currPoint_nextPoint = (nextPoint.y - currPoint.y)/(nextPoint.x - currPoint.x)
        except ZeroDivisionError:
            slope_currPoint_nextPoint = 99999

        acuteAngle = math.atan(abs((slope_currPoint_nextPoint - slope_currPoint_prevPoint)/(1 + slope_currPoint_nextPoint * slope_currPoint_prevPoint)))
        #print 'Angle: %f' % acuteAngle
        return acuteAngle

    def calc_four_corners(self):
        self.parseWKT()
        self.remove_duplicate_points()

        ## degugging
        #print ' points:'
        #for pnt in self.get_points():
        #    print 'x:%.8f, y: %.8f' % (pnt.X, pnt.Y)

        _angles = []
        _points = self.get_points()
        for pnt in _points:
            curr_point = pnt
            try:
                prev_point = _points[_points.index(pnt) - 1]
            except:
                prev_point = _points[-1] # get the last point in the list

            try:
                next_point = _points[_points.index(pnt) + 1]
            except:
                next_point = _points[0] # get the first point in the list

            _angle = self.internal_angle(pnt, prev_point, next_point)
            #print 'angle: ', _angle
            _angles.append(_angle)

        # get the four largest internal angles
        four_largest_angles = heapq.nlargest(4, enumerate(_angles), key=lambda x: x[1])
        indices_of_four_largest_angles = [i[0] for i in four_largest_angles]
        four_points = [_points[i] for i in indices_of_four_largest_angles]
        # for pnt in four_points: print pnt
        # define NE, SE, SW and NW corner
        # pnt_centroid = Point(avg(pnt.x for pnt in four_points), avg(pnt.y for pnt in four_points))
        pnt_centroid = self.poly.centroid
        # print 'pnt_centroid: %s' % pnt_centroid

        north_points = [pnt for pnt in four_points if pnt.y >= pnt_centroid.y]
        north_min_x = min(pnt.x for pnt in north_points)
        north_max_x = max(pnt.x for x in north_points)
        south_points = [pnt for pnt in four_points if pnt.y < pnt_centroid.y]
        south_min_x = min(pnt.x for pnt in south_points)
        south_max_x = max(pnt.x for pnt in south_points)
        points = {}
        # print 'north_points:', north_points
        # print 'south_points:', south_points
        try:
            points['NE'] = north_points[0] if north_points[0].x > north_points[1].x else north_points[1] # north-east point
            points['NW'] = north_points[0] if north_points[0].x < north_points[1].x else north_points[1] # north-west point
            points['SE'] = south_points[0] if south_points[0].x > south_points[1].x else south_points[1] # south-east point
            points['SW'] = south_points[0] if south_points[0].x < south_points[1].x else south_points[1] # south-west point
        except:
            self.four_corners = None
            return
        # print 'points:', points

        # check if bearing NW -> NE is within the limits: 45 < x < 135
        nw_ne_bearing = bearing_deg( points['NW'], points['NE'])
        if not 45 < nw_ne_bearing < 135:
            print 'corners switched.'
            points['NE'], points['NW'], points['SW'], points['SE'] = points['NW'], points['SW'], points['SE'], points['NE']

        self.four_corners = points

    def get_four_corners(self):
        return self.four_corners

    def __str__(self):
        _four_corners = self.four_corners
        _str = ''
        for key, pnt in _four_corners.items():
            _str += '\n\t%s: (%.2f, %.2f)' % (key, pnt.x, pnt.y)
        return _str
