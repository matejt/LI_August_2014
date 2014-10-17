import datetime
from sqlalchemy import Table, MetaData, Column, Integer, Numeric, String, Date, create_engine, ForeignKey
from sqlalchemy.orm import sessionmaker, mapper, relationship, backref
from sqlalchemy.ext.declarative import declarative_base

from models import Texas, Ohio_Virginia, Kentucky_Tennessee, NewYork, WV_Pensylvania, PLS, British_Columbia_dls, British_Columbia_ts, Alberta_ts, Alberta_Saskatchewan_dls, Manitoba_dls

Base = declarative_base()

engine_RigData21 = create_engine('mssql+pyodbc://%s/%s' % ('RDSQLDEV\RDSQLDEV', 'RigData21'))
engine_GIScore = create_engine('mssql+pyodbc://%s/%s' % ('RDSQLSTAGE01\Prime', 'GISCoreData'))

meta_rigdata21 = MetaData()

rigdata21_session_maker = sessionmaker(bind=engine_RigData21)


# ORM definition
class State(Base):
    __tablename__ = 'refState'

    id  = Column('refStateID', Integer, primary_key=True)
    state_code = Column('StateCode', String)
    state_name = Column('StateName', String)

    geo = relationship('Geography', backref='refState')


class County(Base):
    __tablename__ = 'refCounty'

    id  = Column('refCountyID', Integer, primary_key=True)
    # state_code = Column('stateCode', String)
    county_name = Column('LongCountyName', String)
    mcode1 = Column('Mcode1', Integer)
    mcode2 = Column('Mcode2', Integer)
    mcode3 = Column('Mcode3', Integer)

    geo = relationship('Geography', backref='refCounty')


class Geography(Base): 
    __tablename__ = 'Geography'

    id = Column('GeographyID', Integer, primary_key=True)
    county_id  = Column('refCountyID', Integer, ForeignKey(County.id))
    state_id   = Column('refStateID', Integer, ForeignKey(State.id))
    legal_desc = Column('LegalDescription', String)

    # Texas
    abstract_number = Column('AbstractNumber', String)

    # PLS
    twnshp = Column('Township', String)
    twnshp_dir = Column('TownshipDirection', String)
    range_ = Column('Range', String)
    range_dir = Column('RangeDirection', String)
    section = Column('Section', String)
    qsection = Column('QuarterSection', String)
    qqsection = Column('QuarterQuarterSection', String)
    sourceLat = Column('SourceLat', Numeric)
    sourceLon = Column('SourceLong', Numeric)

    # Canada topographic survey
    map_sheet = Column('Quadrangle', String)
    unit = Column('Unit', String)
    quarter_unit = Column('QuarterUnit', String)
    block = Column('BlockNumber', String)

    # Canada dominion land survey
    meridian = Column('Meridian', String)
    legal_subdivision = Column('LegalSubdivision', String)

    offset_1 = Column('Ftg', Numeric)
    offset_dir_1 = Column('FtgDirection', String)
    offset_2 = Column('Ftg2', Numeric)
    offset_dir_2 = Column('Ftg2Direction', String)

    wellboreDetail = relationship('WellBoreDetail', backref='Geography')


class Coordinates(Base):
    __tablename__ = 'CoordinateData'

    id  = Column('CoordinateID', Integer, primary_key=True)
    geo_id = Column('GeographyID', Integer, ForeignKey(Geography.id), nullable=False)
    northing = Column('Northing', Numeric)
    easting = Column('Easting', Numeric)
    epsg_code = Column('EPSGCode', Integer)
    loc_quality = Column('LocQuality', Integer)

    geo = relationship('Geography', backref=backref('CoordinateData', uselist=False))


class WellBore(Base):
    __tablename__ = 'WellBore'

    id  = Column('WellBoreID', Integer, primary_key=True)
    well_no = Column('WellNumber', String)
    api = Column('API', String)
    uwi = Column('UWI', String)

    wellboredetail = relationship('WellBoreDetail', backref='WellBore')


class WellBoreDetail(Base):
    __tablename__ = 'WellBoreDetail'

    id                 = Column('WellBoreDetailID', Integer, primary_key=True)
    wellbore_id        = Column('WellBoreID', Integer, ForeignKey(WellBore.id))
    wellpoint_type_id  = Column('WellPointTypeID', Integer)
    geo_id             = Column('GeographyID', Integer, ForeignKey(Geography.id))
    locnum             = Column('Locnum', String)


class Permit(Base):
    __tablename__ = 'Permit'

    id  = Column('PermitID', Integer, primary_key=True)
    wellbore_id = Column('WellBoreID', Integer, ForeignKey(WellBore.id))
    posted_date = Column('PermitPostedDate', Date)


class Region(object):
    """
    defining regions where different coordinate calculation logic applies

    """
    def __init__(self, name, criteria, model):
        self.name = name
        self.criteria = criteria
        self.model = model

    def get_name(self):
        return self.name

    def get_criteria(self):
        return self.criteria

    def get_model(self):
        return self.model


class Rec(object):
    def __init__(self, coo, geo, cty, wbd, wb, sta, prm):
        self.coo = coo
        self.geo = geo
        self.cty = cty
        self.wbd = wbd
        self.wb  = wb
        self.sta = sta
        self.prm = prm


def define_type(rec):

    # rec.geo.abstract_number and 
    # criteria for deciding the type
    regions = [
        Region(**{
            'name'      : 'texas',
            'criteria'  : rec.sta.state_code.upper() == 'TX',
            'model'     : Texas(rec)
         }),

        Region(**{
            'name'      : 'ohio_virginia',
            'criteria'  : rec.sta.state_code.upper() in ('OH', 'VA'),
            'model'     : Ohio_Virginia(rec)
         }),

        Region(**{
            'name'      : 'kentucky_tennessee',
            'criteria'  : rec.sta.state_code.upper() in ('KY', 'TN'),
            'model'     : Kentucky_Tennessee(rec)
         }),

        Region(**{
            'name'      : 'new_york',
            'criteria'  : rec.sta.state_code.upper() == 'NY',
            'model'     : NewYork(rec)
         }),

        Region(**{
            'name'      : 'wv_pensylvania',
            'criteria'  : rec.sta.state_code.upper() in ('WV', 'PA'),
            'model'     : WV_Pensylvania(rec)
         }),

        Region(**{
            'name'      : 'pls',
            'criteria'  : rec.sta.state_code.upper() in ('AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'FL', 'ID', 'IL', 'IN', 'KS', 'LA', 'MA', 'MI', 
                                    'MN', 'MO', 'MS', 'MT', 'ND', 'NE', 'NM', 'NV', 'OK', 'SD', 'UT', 'VT', 'WA', 'WI', 'WY', 'ZG'),
            'model'     : PLS(rec)
         }),

        Region(**{
            'name'      : 'british_columbia_dls',
            'criteria'  : rec.sta.state_code.upper() == 'BC' and rec.wb.uwi.startswith('1'),
            'model'     : British_Columbia_dls(rec)
         }),

        Region(**{
            'name'      : 'british_columbia_ts',
            'criteria'  : rec.sta.state_code.upper() == 'BC' and rec.wb.uwi.startswith('2'),
            'model'     : British_Columbia_ts(rec)
         }),    

        # there are no known topographic survey records for Alberta
        # Region(**{
        #     'name'      : 'alberta_ts',
        #     'criteria'  : rec.sta.state_code.upper() == 'AB' and rec.wb.uwi.startswith('2'),
        #     'model'     : Alberta_ts(rec)
        #  }),    

        Region(**{
            'name'      : 'alberta_saskatchewan_dls',
            'criteria'  : (rec.sta.state_code.upper() == 'AB' and rec.wb.uwi.startswith('1') or rec.sta.state_code.upper() == 'SK'),
            'model'     : Alberta_Saskatchewan_dls(rec)
         }),    

        Region(**{
            'name'      : 'manitoba_dls',
            'criteria'  : rec.sta.state_code.upper() == 'MB',
            'model'     : Manitoba_dls(rec)
         }),    
    ]


    # if criteria is fulfilled return the above Type object, including the reference to a model
    for region in regions:
        if region.get_criteria():
            return region.get_model()


if __name__ == '__main__':
    session = rigdata21_session_maker()
    query = session.query(Geography, Coordinates, WellBoreDetail, WellBore, State, County, Permit)
    query = query.join(Coordinates, WellBoreDetail, WellBore, State).outerjoin(County).outerjoin(Permit)

    query = query.filter(State.state_code == 'ND', Permit.posted_date < datetime.datetime(year=2011, month=1, day=1), Permit.posted_date > datetime.datetime(year=2008, month=1, day=1), WellBoreDetail.wellpoint_type_id == 513)
    # query = query.filter(State.state_code == 'TX', WellBoreDetail.locnum == '775568')
    # query = query.filter(State.state_code == 'TX', WellBoreDetail.wellpoint_type_id == 513)
    # query = query.filter(State.state_code == 'SK', Permit.posted_date < datetime.datetime(year=2012, month=1, day=1), Permit.posted_date > datetime.datetime(year=2008, month=1, day=1), WellBore.uwi.startswith('2'))
    # print query

    j = 0 #number of reported cases
    for i, (geo, coo, wbd, wb, sta, cty, prm) in enumerate(query.limit(10), start=1):    
    # for i, (geo, coo, wbd, wb, sta, cty, prm) in enumerate(query, start=1):    

        # if not i % 100: print '%i records processed.' % i
        rec = Rec(coo, geo, cty, wbd, wb, sta, prm)
        model_object = define_type(rec)
        if model_object:

            # calculate coordinates
            model_object.coordinates()

            # find all the referenced shapes in the legal description
            model_object.assign_ref_shapes()

            # assign centroid, if  unable to calculate coordinates
            if not model_object.get_point():
                model_object.assign_centroid()

            # assess the location quality
            model_object.define_location_quality()
            if model_object.get_location_quality() < 999:
                j +=1
                model_object.report()

            # store point and location QA into the ORM (still need to commit  in order to persist changes in the database)
            model_object.store_calculated_point_and_QA()
        else:
            print 'No model found for record for %s, API: %s, UWI: %s' % (rec.sta.state_code, rec.wb.api, rec.wb.uwi)
            print '\t', rec.wbd.locnum, rec.coo.northing, rec.coo.easting, rec.coo.epsg_code, rec.geo.legal_desc

    print '%i total records reported.' % j
    print '%i total records processed.' % i
    # commits the changes into the database
    # session.commit()

