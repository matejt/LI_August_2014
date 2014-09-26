from utils import CornerDetector, queryWKT, calc_point_from_offsets, transform, meridian_zone
from shapely.wkt import dumps, loads


class LegalDescription(object):

    def __init__(self, rec):
        self.rec = rec
        self.locnum = rec.wbd.locnum.strip()
        self.state_code = self.rec.cty.state_code.upper().strip()
        # self.county_id = self.rec.cty.county_id
        # self.state_id = self.rec.cty.state_id
        self.county = self.rec.cty.county_name.upper().strip()
        self.api = rec.wb.api.strip()

        self.point = None
        self.reference_shapes = None
        self.initial_quality_score = 0

    def coordinates(self):
        # ony callsed for classes that have coordinates entered manually or imported
        print 'LegalDescription.coordinates method called.'
        pass

    def get_5d_api(self):
        _api = self.api.split('-')
        _5d_api = _api[0] + _api[1]
        if len(_5d_api) == 5:
            return _5d_api
        else:
            print 'incorrect 5 digit api: %s' % _5d_api
            return '00000'

    def get_point(self):
        return self.point

    def assign_centroid(self):

        if self.reference_shapes:

            # order shapes by area
            l = sorted(self.reference_shapes.iteritems(), key=lambda x: x[1].area, reverse=True)

            # the smallest polygon is the last in the
            centroid_name, polygon = l[-1]

            self.point = polygon.centroid
            
            # assign the location quality score: number of referenced polygons + 5
            self.rec.coo.loc_quality = len(l) + 5
            print '\tCentroid assigned from %s: %s' % (centroid_name, self.point)
            print '\tlocation quality: %s' % self.rec.coo.loc_quality

    def shape_corners(self, where_clause):
        pass

    def location_quality_score(self):

        """
        parameters:
            self : we use self.point and check it against the dictionary of shape_corners
            shapes = {'name1': APIshape, name2: Abstract/Section, name3: qq, ...}
        """

        # if we were unable to calculate a point
        if not self.point:
            return 0

        score  = self.initial_quality_score
        for name, shape in self.reference_shapes.iteritems():
            if shape.intersection(transform(4269, 3857, self.point)): 
                score += 10
                print '\tpoint inside the shape: %s' % name
            else:
                print '\tpoint outside the shape: %s' % name
        # reset score if the point does not fall within any of the related shapes
        if score == self.initial_quality_score:
            score = 0

        return score


class Texas(LegalDescription):

    def coordinates(self):
        # variables
        self.abstract_no = self.rec.geo.abstract_number.strip()

        self.offset_1 = self.rec.geo.offset_1
        self.offset_dir_1 = self.rec.geo.offset_dir_1.upper().strip()
        self.offset_2 = self.rec.geo.offset_2
        self.offset_dir_2 = self.rec.geo.offset_dir_2.upper().strip()
        
        print '\ncalculating coordinates for %s (%s):' % (self.state_code,self.__class__.__name__)
        print '\tloc#: %s, api: %s, state: %s, county: %s, abstract no: %s, offset1: %s, offsetDir1: %s, offset2: %s, offsetDir2: %s' \
                % (self.locnum, self.api, self.state_code, self.county, self.abstract_no, self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2)

        # if data necessary for calculation is missing, return
        if not all([self.county, self.abstract_no, self.offset_1, self.offset_2, self.offset_dir_1, self.offset_dir_2]):
            # self.point is None, assigned in constructor
            return

        where_clause = "COUNTY LIKE '%s' AND ANUM1 LIKE '%s'" % (self.county, self.abstract_no)
        table = 'GISCoreData.dbo.TexasSurveys'
        wkt = queryWKT(table, where_clause)

        # at this point we skip records that have directions specified like FWSEL,...
        # or the polygon was not retreived
        if not wkt or len(self.offset_dir_1) > 4 or len(self.offset_dir_2) > 4: 
            # self.point is None, assigned in constructor
            return
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():
            # print detector
            self.point = calc_point_from_offsets(detector.get_four_corners(), self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2)
            if self.point:
                print '\t%s' % self.point
                self.rec.coo.northing = self.point.y
                self.rec.coo.easting  = self.point.x
                self.rec.coo.epsg_code = 4269  # NAD83
                self.initial_quality_score = 10  # if calcualted from offsets, initial qs = 10

        else:
            print '\tunable to extract four corners from the referenced shape'

    def location_quality(self):
        
        # dictionary that containes pairs rank: Polygon
        _shapes = {}

        # extract API region
        where_clause = "FIPS_API = '%s'" % (self.get_5d_api())
        table = 'GISCoreData.dbo.API_Regions_WM'
        polygon_WKT = queryWKT(table, where_clause)
        if polygon_WKT: 
            poly = loads(polygon_WKT)
            _shapes['Api_region'] = poly

        #exctract Abstract
        where_clause = "COUNTY = '%s' AND ANUM1 = '%s'" % (self.county.upper().strip(), self.abstract_no.strip())
        table = 'GISCoreData.dbo.TexasSurveys'
        polygon_WKT = queryWKT(table, where_clause)
        if polygon_WKT: 
            poly = loads(polygon_WKT)
            _shapes['Abstract'] = poly

        #TODO: add more conditions

        self.reference_shapes = _shapes
        location_quality_score = self.location_quality_score()
        self.rec.coo.loc_quality = location_quality_score
        print '\tlocation quality: %s' % location_quality_score


class Ohio_Virginia(LegalDescription):

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec


class Kentucky_Tennessee(LegalDescription):

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec


class NewYork(LegalDescription):

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec


class WV_Pensylvania(LegalDescription):

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec


class PLS(LegalDescription):

    def coordinates(self):
        # variables
        self.mcode1 = self.rec.cty.mcode1
        self.mcode2 = self.rec.cty.mcode2
        self.mcode3 = self.rec.cty.mcode3

        self.twnshp = self.rec.geo.twnshp.strip().zfill(3)
        self.twnshp_dir = self.rec.geo.twnshp_dir.upper().strip()
        self.range_  = self.rec.geo.range_.strip().zfill(3)
        self.range_dir = self.rec.geo.range_dir.upper().strip()

        self.section = self.rec.geo.section.strip().zfill(3)
        self.qsection = self.rec.geo.qsection.strip() if self.rec.geo.qsection else None
        self.qqsection = self.rec.geo.qqsection.strip() if self.rec.geo.qqsection else None

        self.offset_1 = self.rec.geo.offset_1
        self.offset_dir_1 = self.rec.geo.offset_dir_1.upper().strip()
        self.offset_2 = self.rec.geo.offset_2
        self.offset_dir_2 = self.rec.geo.offset_dir_2.upper().strip()

        # define the meridian zone
        if any([self.mcode2, self.mcode3]):
            self.mcode = meridian_zone(self.state_code, self.county, self.twnshp, self.twnshp_dir, self.range_, self.range_dir)
        else:
            self.mcode = self.mcode1


        print 'calculating coordinates for %s (%s)' % (self.state_code,self.__class__.__name__)
        print '\tloc#: %s, api: %s, state: %s, county: %s, mcode: %i, twnshp: %s, twnshp_dir: %s, range: %s, range_dir: %s, section: %s, qsection: %s, qqsection: %s, offset1: %s, offsetDir1: %s, offset2: %s, offsetDir2: %s' \
        % (self.locnum, self.api, self.state_code, self.county, self.mcode,
            self.twnshp, self.twnshp_dir, self.range_, self.range_dir, self.section, self.qsection, self.qqsection,
            self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2)

        if not all([self.state_code, self.county, self.twnshp, self.twnshp_dir, self.range_, self.range_dir, self.section, self.offset_1, self.offset_2, self.offset_dir_1, self.offset_dir_2]):
            # self.point is None, assigned in constructor
            return

        where_clause = "StateCode LIKE '%s' AND TWN LIKE '%s' AND TWNDIR LIKE '%s' AND RNG LIKE '%s' AND RNGDIR LIKE '%s'AND SECTION LIKE '%s'" % (self.state_code, self.twnshp, self.twnshp_dir, self.range_, self.range_dir, self.section)
        table = 'GISCoreData.dbo.PLSS_SEC_%i' % self.mcode
        wkt = queryWKT(table, where_clause)

        if not wkt or len(self.offset_dir_1) > 3 or len(self.offset_dir_2) > 3: 
            # self.point is None, assigned in constructor
            return
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():
            # print detector
            self.point = calc_point_from_offsets(detector.get_four_corners(), self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2)
            if self.point:
                print '\t%s' % self.point
                self.rec.coo.northing = self.point.y
                self.rec.coo.easting  = self.point.x
                self.rec.coo.epsg_code = 4269  # NAD83
                self.initial_quality_score = 10  # if calcualted from offsets, initial qs = 10

        else:
            print '\tunable to extract four corners from the referenced shape'

    def location_quality(self):
        print '\tdefining location quality...'
        pass


class Canada_dls(LegalDescription):

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec


class Canada_ts(LegalDescription):

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec
