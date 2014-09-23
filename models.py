from utils import CornerDetector, queryWKT, calc_point_from_offsets, transform

class LegalDescription(object):

    def __init__(self, rec):
        self.rec = rec
        self.locnum = rec.wbd.locnum
    def shape_corners(self, where_clause):
        pass


class Texas(LegalDescription):

    def coordinates(self):
        # variables
        state = self.rec.cty.state_code
        county = self.rec.cty.county_name.strip()
        abstract_no = self.rec.geo.abstract_number

        offset_1 = self.rec.geo.offset_1
        offset_dir_1 = self.rec.geo.offset_dir_1
        offset_2 = self.rec.geo.offset_2
        offset_dir_2 = self.rec.geo.offset_dir_2
        
        offset_dir_1, offset_dir_2 = offset_dir_1.upper().strip(), offset_dir_2.upper().strip()
        
        print 'calculating coordinates for %s (%s):' % (state,self.__class__.__name__)
        print '\tloc#: %s, state: %s, county: %s, abstract no: %s, offset1: %s, offsetDir1: %s, offset2: %s, offsetDir2: %s' \
                % (self.locnum, state, county, abstract_no, offset_1, offset_dir_1, offset_2, offset_dir_2)

        where_clause = "COUNTY = '%s' AND ANUM1 = '%s'" % (county.upper().strip(), abstract_no.strip())
        table = 'GISCoreData.dbo.TexasSurveys'
        wkt = queryWKT(table, where_clause)

        # at this point we skip records that have directions specified like FWSEL,...
        # or the polygon was not retreived
        if not wkt or len(offset_dir_1) > 4 or len(offset_dir_2) > 4: 
            # assign the api region centroid
            return
            
        # print wkt
        detector = CornerDetector(wkt)
        if detector.get_four_corners():
            # print detector
            point = calc_point_from_offsets(detector.get_four_corners(), offset_1, offset_dir_1, offset_2, offset_dir_2)
            if point:
                print '\t%s\n' % point
                self.rec.coo.northing = point.y
                self.rec.coo.easting  = point.x
                self.rec.coo.epsg_code = 4269
                self.rec.coo.loc_quality = 3

        else:
            print '\tunable to extract four corners from the referenced shape\n'


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
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec


class Canada_dls(LegalDescription):

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec


class Canada_ts(LegalDescription):

    def coordinates(self):
        print 'calculating coordinates for %s (%s)' % (self.rec.cty.state_code,self.__class__.__name__)
        abstract = self.rec

