import math
from utils import CornerDetector, queryWKT, calc_point_from_offsets, transform, meridian_zone, ensure_polygon, area
from shapely.wkt import dumps, loads
from shapely.ops import cascaded_union
from shapely.geometry import Point


class DirectionException(Exception): pass


class LegalDescription(object):

    def __init__(self, rec):
        self.rec = rec
        self.locnum = rec.wbd.locnum.strip()
        self.legal_desc = self.rec.geo.legal_desc
        self.legal_desc_str = None

        self.orig_point = self.original_point()
        self.point = None
        self.location_quality = 0
        self.centroid_assigned = None
        self.reference_shapes = None
        self.offset_1 = None
        self.offset_2 = None

    def store_calculated_point_and_QA(self):
        if self.point:
            self.rec.coo.northing = self.point.y
            self.rec.coo.easting  = self.point.x
            self.rec.coo.epsg_code = 4269  # NAD83
            self.rec.coo.loc_quality = self.get_location_quality()
        else:
            print 'point was not calculated.'

    def get_original_calculated_distance(self):
        if all([self.point, self.orig_point]):
            return transform(4269, 3857, self.orig_point).distance(transform(4269, 3857, self.point)) * math.cos(self.point.y * math.pi / 180.0)
        else:
            return 'Unable to caclulate: (orig: %s, calc: %s)' % (self.orig_point, self.point)

    def report(self):
        print '\ncalculating coordinates for %s (%s) [%s]:' % (self.state_code,self.__class__.__name__, self.rec.prm.posted_date)
        print '\n%s' % self.legal_desc_str
        print '\tCalculated point: %s' % self.point
        print '\tOriginal - Calculated distance: %.2fm' % self.get_original_calculated_distance()
        print '\tlocation quality : %.3f' % self.get_location_quality()
        print '\tcentroid assigned: %s' % self.centroid_assigned

    def get_centroid_assigned(self):
        return self.centroid_assigned

    def get_location_quality(self):
        return self.location_quality

    def original_point(self):
        try:
            x, y, epsg_in = float(self.rec.coo.easting), float(self.rec.coo.northing), int(self.rec.coo.epsg_code) 
            return transform(epsg_in, 4269, Point(x,y))
        except:
            return Point(0,0)

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

            self.point = transform(3857, 4269, polygon.centroid)
            
            # assign the location quality score: number of referenced polygons + 5
            self.centroid_assigned = centroid_name
            self.location_quality = -5
            # print '\tCentroid assigned from %s: %s' % (centroid_name, self.point)
            # print '\tlocation quality: %s' % self.rec.coo.loc_quality

    def define_location_quality(self):

        """
        parameters:
            self : we use self.point and check it against the dictionary of shape_corners
            shapes = {'name1': APIshape, name2: Abstract/Section, name3: qq, ...}
        """

        # if we were unable to calculate a point
        if not self.point:
            return 0

        score = self.location_quality
        for name, shape in self.reference_shapes.iteritems():
            try:
                shape = ensure_polygon(shape)

                if shape.intersection(transform(4269, 3857, self.point)): 
                    score += math.pow(area(shape, units='square miles'), -1)  # if within a square mile => score = 1
                    # print '\tpoint inside the shape: %s, area: %.3f square miles' % (name, area(shape, units='square miles'))
                else:
                    pass
                    # print '\tpoint outside the shape: %s' % name
            except:
                print '\tinvalid geomtery for %s' % name

        # reset score if the point does not fall within any of the related shapes
        if score == self.location_quality:
            score = -1

        self.location_quality = score


class LegalDescription_USA(LegalDescription):
    
    def __init__(self, rec):
        super( LegalDescription_USA, self ).__init__(rec)
        self.state_code = self.rec.sta.state_code.upper().strip()
        self.county = self.rec.cty.county_name.upper().strip() if self.rec.cty else None
        self.api = rec.wb.api.strip()


class LegalDescription_Canada(LegalDescription):
    
    def __init__(self, rec):
        super( LegalDescription_Canada, self ).__init__(rec)
        self.province_code = self.rec.sta.state_code.upper().strip()
        self.uwi = rec.wb.uwi.strip()


class Texas(LegalDescription_USA):

    def __init__(self, rec):
        super(Texas, self).__init__(rec)

    def coordinates(self):
        # variables
        self.abstract_no = self.rec.geo.abstract_number.strip()
        self.offset_dir_1 = self.rec.geo.offset_dir_1.upper().strip()
        self.offset_dir_2 = self.rec.geo.offset_dir_2.upper().strip()
        try:
            self.offset_1 = float(self.rec.geo.offset_1)
            self.offset_2 = float(self.rec.geo.offset_2)
        except:
            print '\tCould not convert offsets to float: %s, %s' % (self.rec.geo.offset_1, self.rec.geo.offset_2) 

        self.legal_desc_str = '\tloc#: %s, api: %s, state: %s, county: %s, abstract no: %s, offset1: %s, offsetDir1: %s, offset2: %s, offsetDir2: %s' \
                % (self.locnum, self.api, self.state_code, self.county, self.abstract_no, self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2)

        # if data necessary for calculation is missing, return
        if not all([self.county, self.abstract_no, self.offset_1, self.offset_2, self.offset_dir_1, self.offset_dir_2]):
            # self.point is None, assigned in constructor
            print '\tmissing crucial data in legal description to calculate the point location.'
            return

        where_clause = "COUNTY LIKE '%s' AND ANUM1 LIKE '%s'" % (self.county, self.abstract_no)
        table = 'GISCoreData.dbo.TexasSurveys'
        wkt = queryWKT(table, where_clause)

        # at this point we skip records that have directions specified like FWSEL,...
        # or the polygon was not retreived
        if not wkt: 
            # self.point is None, assigned in constructor
            print '\tCould not retrieve the referenced polygon based on query: %s' % where_clause
            return  
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():
            # print detector
            self.point = calc_point_from_offsets(detector.get_four_corners(), self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2, units='feet')

        else:
            print '\tunable to extract four corners from the referenced shape'

    def assign_ref_shapes(self):
        
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
        # location_quality_score = self.location_quality_score()
        # self.rec.coo.loc_quality = location_quality_score
        # print '\tlocation quality: %s' % location_quality_score


class Ohio_Virginia(LegalDescription_USA):

    def __init__(self, rec):
        super(Ohio_Virginia, self).__init__(rec)


    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.sta.state_code,self.__class__.__name__)
        abstract = self.rec


class Kentucky_Tennessee(LegalDescription_USA):

    def __init__(self, rec):
        super(Kentucky_Tennessee, self).__init__(rec)

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.sta.state_code,self.__class__.__name__)
        abstract = self.rec


class NewYork(LegalDescription_USA):

    def __init__(self, rec):
        super(NewYork, self).__init__(rec)

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.sta.state_code,self.__class__.__name__)
        abstract = self.rec


class WV_Pensylvania(LegalDescription_USA):

    def __init__(self, rec):
        super(WV_Pensylvania, self).__init__(rec)

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.sta.state_code,self.__class__.__name__)
        abstract = self.rec


class PLS(LegalDescription_USA):

    def __init__(self, rec):
        super(PLS, self).__init__(rec)

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

        self.offset_dir_1 = self.rec.geo.offset_dir_1.upper().strip()
        self.offset_dir_2 = self.rec.geo.offset_dir_2.upper().strip()

        try:
            self.offset_1 = float(self.rec.geo.offset_1)
            self.offset_2 = float(self.rec.geo.offset_2)
        except:
            print '\tCould not convert offsets to float: %s, %s' % (self.rec.geo.offset_1, self.rec.geo.offset_2) 


        # define the meridian zone
        if any([self.mcode2, self.mcode3]):
            self.mcode = meridian_zone(self.state_code, self.county, self.twnshp, self.twnshp_dir, self.range_, self.range_dir)
        else:
            self.mcode = self.mcode1

        self.legal_desc_str = '\tloc#: %s, api: %s, state: %s, county: %s, mcode: %i, leg_desc: %s, twnshp: %s, twnshp_dir: %s, range: %s, range_dir: %s, section: %s, qsection: %s, qqsection: %s, offset1: %s, offsetDir1: %s, offset2: %s, offsetDir2: %s' \
                        % (self.locnum, self.api, self.state_code, self.county, self.mcode, self.legal_desc,
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
            self.point = calc_point_from_offsets(detector.get_four_corners(), self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2, units='feet')

        else:
            print '\tunable to extract four corners from the referenced shape'

    def assign_ref_shapes(self):

        # dictionary that containes pairs rank: Polygon
        _shapes = {}

        # extract API region
        where_clause = "FIPS_API = '%s'" % (self.get_5d_api())
        table = 'GISCoreData.dbo.API_Regions_WM'
        polygon_WKT = queryWKT(table, where_clause)
        if polygon_WKT: 
            poly = loads(polygon_WKT)
            _shapes['Api_region'] = poly

        #exctract section
        where_clause = "StateCode LIKE '%s' AND TWN LIKE '%s' AND TWNDIR LIKE '%s' AND RNG LIKE '%s' AND RNGDIR LIKE '%s'AND SECTION LIKE '%s'" % (self.state_code, self.twnshp, self.twnshp_dir, self.range_, self.range_dir, self.section)
        table = 'GISCoreData.dbo.PLSS_SEC_%i' % self.mcode
        polygon_WKT = queryWKT(table, where_clause)
        if polygon_WKT: 
            poly = loads(polygon_WKT)
            _shapes['Section'] = poly

        # qqsection if exists
        if self.qqsection:
            where_clause = "TWN LIKE '%s' AND TWNDIR LIKE '%s' AND RNG LIKE '%s' AND RNGDIR LIKE '%s'AND SECTION LIKE '%s' AND qqsection like '%s%s'" % (self.twnshp, self.twnshp_dir, self.range_, self.range_dir, self.section, self.qsection, self.qqsection)
            table = 'GISCoreData.dbo.PLSS_QQ_%i' % self.mcode
            polygon_WKT = queryWKT(table, where_clause)
            if polygon_WKT: 
                poly = loads(polygon_WKT)
                _shapes['qqSection'] = poly

        #TODO: add more conditions

        self.reference_shapes = _shapes


class British_Columbia_dls(LegalDescription_Canada):

    def __init__(self, rec):
        super(British_Columbia_dls, self).__init__(rec)

    def coordinates(self):

        # variables

        self.twnshp = self.rec.geo.twnshp.strip()
        self.range_  = self.rec.geo.range_.strip()

        self.meridian = self.rec.geo.meridian.strip()
        self.section = self.rec.geo.section.strip()
        self.lsd = self.rec.geo.legal_subdivision.strip() if self.rec.geo.legal_subdivision else None
        self.qsection = self.rec.geo.qsection.strip() if self.rec.geo.qsection else None
        self.qqsection = self.rec.geo.qqsection.strip() if self.rec.geo.qqsection else None

        # self.offset_dir_1 = self.rec.geo.offset_dir_1.upper().strip()
        # self.offset_dir_2 = self.rec.geo.offset_dir_2.upper().strip()
        try:
            self.offset_1 = float(self.rec.geo.offset_1)
            self.offset_2 = float(self.rec.geo.offset_2)
        except:
            print '\tCould not convert offsets to float: %s, %s' % (self.rec.geo.offset_1, self.rec.geo.offset_2) 

        self.legal_desc_str = '\tloc#: %s, uwi: %s, province: %s, meridian: %s, twn: %s, rng: %s, section: %s, lsd: %s, offset1: %s, offset2: %s' \
                % (self.locnum, self.uwi, self.province_code, self.meridian, self.twnshp, self.range_, self.section, self.lsd, self.offset_1, self.offset_2)

        if not all([self.province_code, self.meridian, self.twnshp, self.range_, self.section, self.offset_1, self.offset_2]):
            # self.point is None, assigned in constructor
            return

        where_clause = "MER = '%s' AND TWN = %i AND RNG = %i AND SEC = %i" % (self.meridian, int(self.twnshp), int(self.range_), int(self.section))
        table = 'GISCoreData.dbo.DLS_%s_SEC' % self.province_code
        wkt = queryWKT(table, where_clause)

        if not wkt: 
            # self.point is None, assigned in constructor
            return
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():

            # directions are determined from the offset values.
            offset_dir_1 = 'FSL' if self.offset_1 > 0 else 'FNL'
            offset_dir_2 = 'FWL' if self.offset_2 > 0 else 'FEL'

            # print detector
            self.point = calc_point_from_offsets(detector.get_four_corners(), abs(self.offset_1), offset_dir_1, abs(self.offset_2), offset_dir_2, units='meters')

        else:
            print '\tunable to extract four corners from the referenced shape'

    def assign_ref_shapes(self):

        print '\tassigning reference shapes...'


class British_Columbia_ts(LegalDescription_Canada):

    def __init__(self, rec):

        super(British_Columbia_ts, self).__init__(rec)

    def coordinates(self):

        # variables
        self.map_sheet = self.rec.geo.map_sheet.strip()
        self.unit = self.rec.geo.unit.strip()
        self.quarter_unit = self.rec.geo.quarter_unit.strip()
        self.block = self.rec.geo.block.strip()

        # offset direction values are ignored
        # they are determined below from the negative or positive offset values 
        try:
            self.offset_1 = float(self.rec.geo.offset_1)
            self.offset_2 = float(self.rec.geo.offset_2)
        except:
            print '\tCould not convert offsets to float: %s, %s' % (self.rec.geo.offset_1, self.rec.geo.offset_2) 

        self.legal_desc_str = '\tloc#: %s, uwi: %s, province: %s, mapsheet: %s, block: %s, unit: %s, qunit: %s, offset_NS: %s, offset_EW: %s' \
                % (self.locnum, self.uwi, self.province_code, self.map_sheet, self.block, self.unit, self.quarter_unit, self.offset_1, self.offset_2)

        if not all([self.province_code, self.map_sheet, self.block, self.unit, self.quarter_unit, self.offset_1, self.offset_2]):
            # self.point is None, assigned in constructor
            return

        where_clause = "MAPSHEET = '%s' AND BLOCK = '%s' AND UNIT = %i" % (self.map_sheet, self.block, int(self.unit))
        table = 'GISCoreData.dbo.TS_%s_UNITS' % self.province_code
        wkt = queryWKT(table, where_clause)

        if not wkt: 
            # self.point is None, assigned in constructor
            return
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():

            # directions are determined from the offset values.
            offset_dir_1 = 'FSL' if self.offset_1 > 0 else 'FNL'
            offset_dir_2 = 'FWL' if self.offset_2 > 0 else 'FEL'

            # the offset values are passed as positive values to the calc_point_from_offset funcion
            self.point = calc_point_from_offsets(detector.get_four_corners(), abs(self.offset_1), offset_dir_1, abs(self.offset_2), offset_dir_2, units='meters')

        else:
            print '\tunable to extract four corners from the referenced shape'

    def assign_ref_shapes(self):
        pass


class Alberta_ts(LegalDescription_Canada):

    def __init__(self, rec):

        super(Alberta_ts, self).__init__(rec)

    def coordinates(self):

        # variables
        self.map_sheet = self.rec.geo.map_sheet.strip()
        self.unit = self.rec.geo.unit.strip()
        self.quarter_unit = self.rec.geo.quarter_unit.strip()
        self.block = self.rec.geo.block.strip()

        self.offset_dir_1 = self.rec.geo.offset_dir_1.upper().strip()
        self.offset_dir_2 = self.rec.geo.offset_dir_2.upper().strip()
        try:
            self.offset_1 = float(self.rec.geo.offset_1)
            self.offset_2 = float(self.rec.geo.offset_2)
        except:
            print '\tCould not convert offsets to float: %s, %s' % (self.rec.geo.offset_1, self.rec.geo.offset_2) 

        self.legal_desc_str = '\tloc#: %s, uwi: %s, province: %s, mapsheet: %s, block: %s, unit: %s, qunit: %s, offset_1: %s, offset_dir_1: %s, offset_2: %s, offset_dir_2: %s' \
                % (self.locnum, self.uwi, self.province_code, self.map_sheet, self.block, self.unit, self.quarter_unit, self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2)

        if not all([self.province_code, self.map_sheet, self.block, self.unit, self.quarter_unit, self.offset_1, self.offset_2]):
            # self.point is None, assigned in constructor
            return

        where_clause = "MAPSHEET = '%s' AND BLOCK = '%s' AND UNIT = %i" % (self.map_sheet, self.block, int(self.unit))
        table = 'GISCoreData.dbo.TS_%s_UNITS' % self.province_code
        wkt = queryWKT(table, where_clause)

        if not wkt: 
            # self.point is None, assigned in constructor
            return
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():

            # the offset values are passed as positive values to the calc_point_from_offset funcion
            self.point = calc_point_from_offsets(detector.get_four_corners(), abs(self.offset_1), offset_dir_1, abs(self.offset_2), offset_dir_2, units='meters')

        else:
            print '\tunable to extract four corners from the referenced shape'

    def assign_ref_shapes(self):
        pass


class Alberta_Saskatchewan_dls(LegalDescription_Canada):

    flip_directions = {'FEL': 'FWL', 'FSL': 'FNL', 'FWL': 'FEL', 'FNL': 'FSL'}

    def __init__(self, rec):
        super(Alberta_Saskatchewan_dls, self).__init__(rec)

    def coordinates(self):

        # variables

        self.twnshp = self.rec.geo.twnshp.strip()
        self.range_  = self.rec.geo.range_.strip()

        self.meridian = self.rec.geo.meridian.strip()
        self.section = self.rec.geo.section.strip()
        self.lsd = self.rec.geo.legal_subdivision.strip() if self.rec.geo.legal_subdivision else None
        self.qsection = self.rec.geo.qsection.strip() if self.rec.geo.qsection else None
        self.qqsection = self.rec.geo.qqsection.strip() if self.rec.geo.qqsection else None

        self.offset_dir_1 = self.rec.geo.offset_dir_1.upper().strip()
        self.offset_dir_2 = self.rec.geo.offset_dir_2.upper().strip()
        try:
            self.offset_1 = float(self.rec.geo.offset_1)
            self.offset_2 = float(self.rec.geo.offset_2)
        except:
            print '\tCould not convert offsets to float: %s, %s' % (self.rec.geo.offset_1, self.rec.geo.offset_2) 

        # flip directions: because the source directions for Canada (SK, AB and MB)are just entered the opposite what they should have been
        self.offset_dir_1 = Alberta_Saskatchewan_dls.flip_directions.get(self.offset_dir_1)
        self.offset_dir_2 = Alberta_Saskatchewan_dls.flip_directions.get(self.offset_dir_2)

        if not all([self.offset_dir_1, self.offset_dir_2]):
            raise DirectionException("Wrong direction values: (%s, %s)" % (self.rec.geo.offset_dir_1.upper().strip(), self.rec.geo.offset_dir_2.upper().strip()))

        self.legal_desc_str = '\tloc#: %s, uwi: %s, province: %s, meridian: %s, twn: %s, rng: %s, section: %s, lsd: %s, offset1: %.2f, offset_dir1: %s, offset2: %.2f, offset_dir2: %s' \
                % (self.locnum, self.uwi, self.province_code, self.meridian, self.twnshp, self.range_, self.section, self.lsd, self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2)

        if not all([self.province_code, self.meridian, self.twnshp, self.range_, self.section, self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2]):
            # self.point is None, assigned in constructor
            return

        where_clause = "MER = '%s' AND TWN = '%s' AND RNG = '%s' AND SEC = '%s'" % (self.meridian, self.twnshp, self.range_, self.section)
        table = 'GISCoreData.dbo.DLS_%s_SEC' % self.province_code
        wkt = queryWKT(table, where_clause)

        if not wkt: 
            # self.point is None, assigned in constructor
            return
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():

            # print detector
            self.point = calc_point_from_offsets(detector.get_four_corners(), self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2, units='meters')

        else:
            print '\tunable to extract four corners from the referenced shape'

    def assign_ref_shapes(self):
        pass


class Manitoba_dls(LegalDescription_Canada):

    def __init__(self, rec):
        super(Manitoba_dls, self).__init__(rec)

    def coordinates(self):

        # variables

        self.twnshp = self.rec.geo.twnshp.strip()
        self.range_  = self.rec.geo.range_.strip()

        self.meridian = self.rec.geo.meridian.strip()
        self.section = self.rec.geo.section.strip()
        self.lsd = self.rec.geo.legal_subdivision.strip() if self.rec.geo.legal_subdivision else None
        self.qsection = self.rec.geo.qsection.strip() if self.rec.geo.qsection else None
        self.qqsection = self.rec.geo.qqsection.strip() if self.rec.geo.qqsection else None

        self.offset_dir_1 = self.rec.geo.offset_dir_1.upper().strip()
        self.offset_dir_2 = self.rec.geo.offset_dir_2.upper().strip()
        try:
            self.offset_1 = float(self.rec.geo.offset_1)
            self.offset_2 = float(self.rec.geo.offset_2)
        except:
            print '\tCould not convert offsets to float: %s, %s' % (self.rec.geo.offset_1, self.rec.geo.offset_2) 

        if not all([self.offset_dir_1, self.offset_dir_2]):
            raise DirectionException("Wrong direction values: (%s, %s)" % (self.rec.geo.offset_dir_1.upper().strip(), self.rec.geo.offset_dir_2.upper().strip()))

        self.legal_desc_str = '\tloc#: %s, uwi: %s, province: %s, meridian: %s, twn: %s, rng: %s, section: %s, lsd: %s, offset1: %.2f, offset_dir1: %s, offset2: %.2f, offset_dir2: %s' \
                % (self.locnum, self.uwi, self.province_code, self.meridian, self.twnshp, self.range_, self.section, self.lsd, self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2)

        if not all([self.province_code, self.meridian, self.twnshp, self.range_, self.section, self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2]):
            # self.point is None, assigned in constructor
            return

        where_clause = "MER = '%s' AND TWN = '%s' AND RNG = '%s' AND SEC = '%s'" % (self.meridian, self.twnshp, self.range_, self.section)
        table = 'GISCoreData.dbo.DLS_%s_SEC' % self.province_code
        wkt = queryWKT(table, where_clause)

        if not wkt: 
            # self.point is None, assigned in constructor
            return
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():

            # print detector
            self.point = calc_point_from_offsets(detector.get_four_corners(), self.offset_1, self.offset_dir_1, self.offset_2, self.offset_dir_2, units='meters')

        else:
            print '\tunable to extract four corners from the referenced shape'

    def assign_ref_shapes(self):
        pass

