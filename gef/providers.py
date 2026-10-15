import hashlib
import time
from datetime import timedelta
from urllib.parse import urlparse
import httpx
from .config import settings
from .models import ProviderCache, utcnow
from .security import aware, limit
from .errors import AppError

async def fetch_json(url, params=None, headers=None):
    if urlparse(url).scheme != 'https': raise AppError('PROVIDER_CONFIG',503)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12,connect=4), follow_redirects=False) as client:
            # One retry for transient network failures; never an unbounded loop.
            for attempt in range(2):
                try:
                    res=await client.get(url,params=params,headers=headers)
                    if res.status_code==429: raise AppError('PROVIDER_LIMIT',429)
                    res.raise_for_status()
                    return res.json()
                except httpx.TransportError:
                    if attempt: raise
    except (httpx.HTTPError,ValueError):
        raise AppError('PROVIDER_UNAVAILABLE',502)

def cached(db,key):
    item=db.get(ProviderCache,key)
    return item.value if item and aware(item.expires_at)>utcnow() else None

def cache(db,key,value,seconds):
    row=db.get(ProviderCache,key)
    if row:
        row.value, row.expires_at=value,utcnow()+timedelta(seconds=seconds)
    else:
        db.add(ProviderCache(key=key,value=value,expires_at=utcnow()+timedelta(seconds=seconds)))
    db.commit()

def provider_slot(db, name, seconds):
    # Atomic time-based lease: fixed windows could allow two calls across a boundary.
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    now=utcnow(); expires=now+timedelta(seconds=max(1,seconds))
    stmt=insert(ProviderCache).values(key='gate:'+name,value={},expires_at=expires)
    stmt=stmt.on_conflict_do_update(index_elements=['key'],set_={'expires_at':expires},where=ProviderCache.expires_at<=now).returning(ProviderCache.key)
    accepted=db.scalar(stmt);db.commit()
    if not accepted: raise AppError('PROVIDER_LIMIT',429)

async def reverse_geocode(db,latitude,longitude,language):
    cfg=settings()
    if not cfg.geocoding_url: raise AppError('GEOCODING_UNCONFIGURED',503)
    key=f'geo:{latitude:.4f}:{longitude:.4f}:{language}'
    value=cached(db,key)
    if value: return value
    # Global DB-backed throttle, including across serverless instances. Nominatim: >=1s.
    provider_slot(db,'geocoder',cfg.geocoding_interval)
    data=await fetch_json(cfg.geocoding_url.rstrip('/')+'/reverse',{'lat':latitude,'lon':longitude,'format':'jsonv2','accept-language':language}, {'User-Agent':cfg.provider_agent})
    value={'address':data.get('display_name') or f'{latitude:.5f}, {longitude:.5f}'}
    cache(db,key,value,86400*7)
    return value

async def road_route(db,origin,destination,language='en'):
    cfg=settings()
    if not cfg.routing_url: raise AppError('ROUTING_UNCONFIGURED',503)
    # Configured OSRM-compatible driving service. Routing uses lon,lat; maps use lat,lon.
    points=f'{origin[1]:.6f},{origin[0]:.6f};{destination[1]:.6f},{destination[0]:.6f}'
    key='route:'+hashlib.sha256(points.encode()).hexdigest()
    value=cached(db,key)
    if value: return value
    provider_slot(db,'router',cfg.routing_interval)
    headers={'User-Agent':cfg.provider_agent}
    if cfg.routing_key: headers['Authorization']='Bearer '+cfg.routing_key
    data=await fetch_json(cfg.routing_url.rstrip('/')+'/route/v1/driving/'+points, {'overview':'full','geometries':'geojson','steps':'true'}, headers)
    if data.get('code')!='Ok' or not data.get('routes'): raise AppError('ROUTE_NOT_FOUND',422)
    route=data['routes'][0]
    if route.get('geometry',{}).get('type')!='LineString' or len(route['geometry'].get('coordinates',[]))<2:
        raise AppError('PROVIDER_UNAVAILABLE',502)
    steps=[]
    for leg in route.get('legs',[]):
        for step in leg.get('steps',[]):
            maneuver=step.get('maneuver',{})
            steps.append({'type':maneuver.get('type','continue'),'modifier':maneuver.get('modifier',''),'name':step.get('name',''),'distance_m':round(step.get('distance',0)),'location':maneuver.get('location')})
    value={'geometry':route['geometry'],'distance_m':round(route['distance']),'duration_s':round(route['duration']),'steps':steps,'traffic':False}
    cache(db,key,value,120)
    return value
