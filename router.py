from sqlalchemy import Table, MetaData, Column, Integer, Numeric, String, create_engine, ForeignKey
from sqlalchemy.orm import sessionmaker, mapper, relationship, backref
from sqlalchemy.ext.declarative import declarative_base

from models import Texas, Ohio_Virginia, Kentucky_Tennessee, NewYork, WV_Pensylvania, PLS, Canada_dls, Canada_ts

Base = declarative_base()

engine_RigData21 = create_engine('mssql+pyodbc://%s/%s' % ('RDSQLDEV\RDSQLDEV', 'RigData21'))
engine_GIScore = create_engine('mssql+pyodbc://%s/%s' % ('RDSQLSTAGE01\Prime', 'GISCoreData'))

meta_rigdata21 = MetaData()

rigdata21_session_maker = sessionmaker(bind=engine_RigData21)


# ORM definition
class County(Base):
    __tablename__ = 'refCounty'

    id  = Column('refCountyID', Integer, primary_key=True)
    # state_id = Column('refStateID', String)
    # county_id = Column('refCountyID', String)
    state_code = Column('stateCode', String)
    county_name = Column('LongCountyName', String)
    mcode1 = Column('Mcode1', Integer)
    mcode2 = Column('Mcode2', Integer)
    mcode3 = Column('Mcode3', Integer)

    geo = relationship('Geography', backref='refCounty')


class Geography(Base): 
    __tablename__ = 'Geography'

    id = Column('GeographyID', Integer, primary_key=True)
    county_id = Column('refCountyID', Integer, ForeignKey(County.id))
    legal_desc = Column('LegalDescription', String)
    abstract_number = Column('AbstractNumber', String)
    twnshp = Column('Township', String)
    twnshp_dir = Column('TownshipDirection', String)
    range_ = Column('Range', String)
    range_dir = Column('RangeDirection', String)
    section = Column('Section', String)
    qsection = Column('QuarterSection', String)
    qqsection = Column('QuarterQuarterSection', String)
    sourceLat = Column('SourceLat', Numeric)
    sourceLon = Column('SourceLong', Numeric)

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
    api = Column('API', String)
    uwi = Column('UWI', String)

    wellboredetail = relationship('WellBoreDetail', backref='WellBore')


class WellBoreDetail(Base):
    __tablename__ = 'WellBoreDetail'

    id          = Column('WellBoreDetailID', Integer, primary_key=True)
    wellbore_id = Column('WellBoreID', Integer, ForeignKey(WellBore.id))
    geo_id      = Column('GeographyID', Integer, ForeignKey(Geography.id))
    locnum      = Column('Locnum', String)


# defining regions where different coordinate calculation logic applies
class Region(object):
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
    def __init__(self, coo, geo, cty, wbd, wb):
        self.coo = coo
        self.geo = geo
        self.cty = cty
        self.wbd = wbd
        self.wb  = wb


def define_type(rec):

    # rec.geo.abstract_number and 
    # criteria for deciding the type
    regions = [
        Region(**{
            'name'      : 'texas',
            'criteria'  : rec.cty.state_code.upper() == 'TX',
            'model'     : Texas(rec)
         }),

        Region(**{
            'name'      : 'ohio_virginia',
            'criteria'  : rec.cty.state_code.upper() in ('OH', 'VA'),
            'model'     : Ohio_Virginia(rec)
         }),

        Region(**{
            'name'      : 'kentucky_tennessee',
            'criteria'  : rec.cty.state_code.upper() in ('KY', 'TN'),
            'model'     : Kentucky_Tennessee(rec)
         }),

        Region(**{
            'name'      : 'new_york',
            'criteria'  : rec.cty.state_code.upper() == 'NY',
            'model'     : NewYork(rec)
         }),

        Region(**{
            'name'      : 'wv_pensylvania',
            'criteria'  : rec.cty.state_code.upper() in ('WV', 'PA'),
            'model'     : WV_Pensylvania(rec)
         }),

        Region(**{
            'name'      : 'pls',
            'criteria'  : rec.cty.state_code.upper() in ('AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'FL', 'ID', 'IL', 'IN', 'KS', 'LA', 'MA', 'MI', 
                                    'MN', 'MO', 'MS', 'MT', 'ND', 'NE', 'NM', 'NV', 'OK', 'SD', 'UT', 'VT', 'WA', 'WI', 'WY', 'ZG'),
            'model'     : PLS(rec)
         }),

        Region(**{
            'name'      : 'canada_dls',
            'criteria'  : rec.wb.uwi.startswith('1'),
            'model'     : Canada_dls(rec)
         }),

        Region(**{
            'name'      : 'canada_ts',
            'criteria'  : rec.wb.uwi.startswith('2'),
            'model'     : Canada_ts(rec)
         }),    ]

    # if criteria is fulfilled return the above Type object, including the reference to a model
    for region in regions:
        if region.get_criteria():
            return region.get_model()


if __name__ == '__main__':
    session = rigdata21_session_maker()
    query = session.query(Geography, Coordinates, County, WellBoreDetail, WellBore)
    # query = query.join(Geography, County, WellBoreDetail, WellBore).filter(WellBoreDetail.locnum == '2')
    # query = query.join(Geography, County, WellBoreDetail, WellBore).filter(County.state_code == 'TX', WellBoreDetail.locnum == '1262686')
    # query = query.join(Coordinates, County, WellBoreDetail, WellBore).filter(County.state_code == 'TX', WellBoreDetail.locnum == '1262693')
    query = query.join(Coordinates, County, WellBoreDetail, WellBore).filter(County.state_code == 'ND')
    # query = query.join(Geography, County, WellBoreDetail, WellBore)
    print query
    for i, (geo, coo, cty, wbd, wb) in enumerate(query.limit(10), start=1):    
    # for i, (coo, geo, cty, wbd, wb) in enumerate(query, start=1):    
        rec = Rec(coo, geo, cty, wbd, wb)
        model_object = define_type(rec)
        if model_object:
            pass
            model_object.coordinates()
            model_object.location_quality()
            if not model_object.get_point():
                model_object.assign_centroid()
        else:
            print rec.wbd.locnum, rec.coo.northing, rec.coo.easting, rec.coo.epsg_code, rec.geo.legal_desc, rec.cty.state_code

    # commits the changes into the database
    # session.commit()