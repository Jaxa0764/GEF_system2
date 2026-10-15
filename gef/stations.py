import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from .models import Station, Product, Rating, Visit, utcnow
from .config import settings
from .security import aware
from .errors import AppError

CATEGORIES = ['fuel','metan','propan','elektr']

def distance(a, b, c, d):
    rad = math.pi/180
    p = math.sin((c-a)*rad/2)**2 + math.cos(a*rad)*math.cos(c*rad)*math.sin((d-b)*rad/2)**2
    return 6371000*2*math.atan2(math.sqrt(min(1,p)), math.sqrt(max(0,1-p)))

def is_open(station, now=None):
    if station.override != 'normal':
        return station.override == 'open'
    if station.is_24h:
        return True
    now = (now or utcnow()).astimezone(ZoneInfo('Asia/Tashkent'))
    minute, today = now.hour*60+now.minute, now.weekday()
    def mins(s):
        h,m = map(int,s.split(':')); return h*60+m
    for start,end in station.hours.get(str(today),[]):
        s,e = mins(start),mins(end)
        if (s<e and s<=minute<e) or (s>e and minute>=s):
            return True
    for start,end in station.hours.get(str((today-1)%7),[]):
        s,e = mins(start),mins(end)
        if s>e and minute<e:
            return True
    return False

def serialize(station, stats=None, origin=None):
    avg, count, visits = stats or (None,0,0)
    products=[]
    for product in station.products:
        data = {key:getattr(product,key) for key in ['id','category','name','unit','available','pressure','pressure_unit','pressure_at','power_kw','connectors','connector_available']}
        data['price'] = float(product.price) if product.price is not None else None
        data['pressure_fresh'] = bool(product.pressure_at and utcnow()-aware(product.pressure_at) <= timedelta(hours=settings().pressure_hours))
        products.append(data)
    return {key:getattr(station,key) for key in ['id','name','address','descriptions','latitude','longitude','hours','is_24h','override','published','demo','updated_at']} | {
        'categories': sorted({p.category for p in station.products}, key=CATEGORIES.index),
        'products':products, 'open_now':is_open(station), 'rating':round(float(avg),1) if avg is not None else None,
        'rating_count':count, 'visits':visits,
        'distance_m':round(distance(*origin,station.latitude,station.longitude)) if origin else None,
        'distance_kind':'approximate' if origin else None,
    }

def stats_map(db, ids):
    if not ids: return {}
    ratings={row[0]:(row[1],row[2]) for row in db.execute(select(Rating.station_id,func.avg(Rating.stars),func.count()).where(Rating.station_id.in_(ids)).group_by(Rating.station_id))}
    visits=dict(db.execute(select(Visit.station_id,func.count()).where(Visit.station_id.in_(ids)).group_by(Visit.station_id)).all())
    return {i:(*ratings.get(i,(None,0)),visits.get(i,0)) for i in ids}

def public_station(db, station_id):
    station=db.get(Station,station_id)
    if not station or station.deleted or not station.published: raise AppError('STATION_UNAVAILABLE',404)
    return station

def listing(db, category='fuel', sort='default', opened=False, grade=None, unit=None, pressure_unit='bar', origin=None, page=1, per_page=9, query=None, ids=None):
    if category not in CATEGORIES or sort not in ['default','cheapest','nearest']:
        raise AppError('FILTER_INVALID',422)
    if sort=='nearest' and origin is None: raise AppError('LOCATION_REQUIRED',422)
    if grade and len(grade)>80: raise AppError('FILTER_INVALID',422)
    stmt=select(Station).where(Station.published.is_(True),Station.deleted.is_(False),Station.products.any(Product.category==category))
    if ids is not None: stmt=stmt.where(Station.id.in_(ids))
    if query: stmt=stmt.where((Station.name.ilike(f'%{query}%'))|(Station.address.ilike(f'%{query}%')))
    stations=db.scalars(stmt).all()
    # Fetch only matching category first; aggregate counters in two bounded SQL queries.
    stats=stats_map(db,[s.id for s in stations])
    result=[]
    unit=unit or {'fuel':'liter','metan':'m3','propan':'liter','elektr':'kwh'}[category]
    for s in stations:
        if opened and not is_open(s): continue
        products=[p for p in s.products if p.category==category and (not grade or p.name==grade)]
        if not products: continue
        prices=[float(p.price) for p in products if p.available and p.price is not None and p.unit==unit]
        pressures=[p.pressure for p in products if p.available and p.pressure is not None and p.pressure_unit==pressure_unit and p.pressure_at and utcnow()-aware(p.pressure_at)<=timedelta(hours=settings().pressure_hours)]
        avg,count,visits=stats.get(s.id,(None,0,0))
        if sort=='cheapest': rank=(not prices,min(prices) if prices else float('inf'),s.id)
        elif sort=='nearest': rank=(distance(*origin,s.latitude,s.longitude),s.id)
        elif category in ['metan','propan']: rank=(not pressures,-max(pressures) if pressures else 0,-visits,-float(avg or 0),-count,s.id)
        else: rank=(-visits,-float(avg or 0),-count,s.id)
        result.append((rank,s))
    result.sort(key=lambda item:item[0])
    total=len(result)
    subset=result[(page-1)*per_page:page*per_page]
    return {'items':[serialize(s,stats.get(s.id),origin) for _,s in subset], 'total':total,'page':page,'per_page':per_page,'comparison_unit':unit,'pressure_unit':pressure_unit, 'map_items':[{k:v for k,v in serialize(s,stats.get(s.id),origin).items() if k in ['id','name','address','latitude','longitude','open_now','categories']} for _,s in result[:1000]], 'map_limit':1000}
