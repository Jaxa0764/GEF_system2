from datetime import datetime,timedelta,timezone
from sqlalchemy import select,func
import pytest
from gef.models import Station,Product,RouteSession,Visit,utcnow
from gef.db import new_session
from gef.stations import is_open
from gef.schemas import StationInput
from conftest import signup


def test_overnight_week_schedule_and_overrides():
    station=Station(hours={'0':[['22:00','06:00']]},is_24h=False,override='normal')
    # Monday 23:00, Tuesday 05:59 and Tuesday 06:00 in Tashkent.
    assert is_open(station,datetime(2026,10,12,18,0,tzinfo=timezone.utc))
    assert is_open(station,datetime(2026,10,13,0,59,tzinfo=timezone.utc))
    assert not is_open(station,datetime(2026,10,13,1,0,tzinfo=timezone.utc))
    station.override='closed';station.is_24h=True
    assert not is_open(station)
    station.override='open';assert is_open(station)


def test_cheapest_grade_unknowns_availability_and_open_filter(client,admin,station_data):
    for i,(price,available,override) in enumerate([(12000,True,'normal'),(None,True,'normal'),(9000,True,'closed'),(8000,False,'normal')]):
        data=station_data|{'name':f'Station {i}','request_key':f'cheapest-request-{i:05d}','override':override,'products':[{'category':'fuel','name':'AI-92','unit':'liter','price':price,'available':available},{'category':'fuel','name':'AI-95','unit':'liter','price':14000-i*100,'available':True}]}
        assert client.post('/api/admin/stations',json=data).status_code==201
    result=client.get('/api/stations?category=fuel&grade=AI-92&sort=cheapest&open_now=true').json()['items']
    assert [x['name'] for x in result]==['Station 0','Station 1','Station 3']
    assert client.get('/api/stations?sort=nearest').status_code==422
    assert client.get('/api/stations?sort=nearest&latitude=41.3&longitude=69.2').status_code==200
    assert client.get('/api/stations?latitude=41.3').status_code==422


def test_pressure_freshness_and_unit_compatibility(client,admin,station_data):
    now=utcnow()
    for i,(pressure,unit,age) in enumerate([(190,'bar',1),(240,'bar',12),(200,'bar',2),(25,'MPa',1)]):
        data=station_data|{'name':f'Gas {i}','request_key':f'gas-request-{i:05d}','products':[{'category':'metan','name':'CNG','unit':'m3','price':4500,'available':True,'pressure':pressure,'pressure_unit':unit,'pressure_at':(now-timedelta(hours=age)).isoformat()}]}
        assert client.post('/api/admin/stations',json=data).status_code==201
    items=client.get('/api/stations?category=metan&pressure_unit=bar').json()['items']
    assert [s['name'] for s in items][:2]==['Gas 2','Gas 0']
    assert not next(s for s in items if s['name']=='Gas 1')['products'][0]['pressure_fresh']
    assert client.get('/api/stations?category=metan&pressure_unit=MPa').json()['items'][0]['name']=='Gas 3'


def test_ev_prices_only_compare_same_billing_unit(client,admin,station_data):
    for i,(price,unit) in enumerate([(2000,'kwh'),(900,'minute'),(1800,'kwh')]):
        data=station_data|{'name':f'EV {i}','request_key':f'ev-request-{i:05d}','products':[{'category':'elektr','name':'DC','price':price,'unit':unit,'available':True,'power_kw':60,'connectors':['CCS2'],'connector_available':2}]}
        assert client.post('/api/admin/stations',json=data).status_code==201
    items=client.get('/api/stations?category=elektr&sort=cheapest&unit=kwh').json()['items']
    assert [s['name'] for s in items]==['EV 2','EV 0','EV 1']


@pytest.fixture
def mock_router(monkeypatch):
    async def road(db,origin,destination,language='en'):
        return {'geometry':{'type':'LineString','coordinates':[[origin[1],origin[0]],[69.23,41.31],[destination[1],destination[0]]]},'distance_m':3400,'duration_s':500,'steps':[{'type':'depart','modifier':'straight','name':'Test road','distance_m':3400}],'traffic':False}
    monkeypatch.setattr('gef.api.road_route',road)


def test_real_route_adapter_coordinates_and_geometry(client,station,monkeypatch):
    from gef.config import settings
    monkeypatch.setenv('ROUTING_URL','https://routing.example.test');settings.cache_clear()
    captured={}
    async def fetch(url,params=None,headers=None):
        captured['url']=url
        return {'code':'Ok','routes':[{'geometry':{'type':'LineString','coordinates':[[69.2,41.3],[69.22,41.32],[69.2406,41.3111]]},'distance':6500,'duration':600,'legs':[]}]}
    monkeypatch.setattr('gef.providers.fetch_json',fetch)
    response=client.post('/api/routes',json={'station_id':station['id'],'latitude':41.3,'longitude':69.2,'origin_kind':'live'})
    assert response.status_code==200,response.text
    assert '69.200000,41.300000;69.240600,41.311100' in captured['url']
    assert len(response.json()['geometry']['coordinates'])==3
    assert response.json()['distance_m']==6500


def test_visit_requires_active_live_route_accuracy_and_deduplicates(client,station,mock_router):
    def route(kind):
        response=client.post('/api/routes',json={'station_id':station['id'],'latitude':41.3,'longitude':69.2,'origin_kind':kind})
        assert response.status_code==200,response.text
        return response.json()['route_id']
    manual=route('manual')
    client.post(f'/api/navigation/{manual}/start')
    with new_session() as db:
        obj=db.get(RouteSession,manual);obj.started_at=utcnow()-timedelta(minutes=2);db.commit()
    body={'route_id':manual,'latitude':station['latitude'],'longitude':station['longitude'],'accuracy':12,'position_timestamp':utcnow().isoformat(),'confirmed':True}
    assert client.post('/api/visits',json=body).status_code==422
    live=route('live');body['route_id']=live
    assert client.post('/api/visits',json=body).status_code==422
    client.post(f'/api/navigation/{live}/start')
    with new_session() as db:
        obj=db.get(RouteSession,live);obj.started_at=utcnow()-timedelta(minutes=2);db.commit()
    assert client.post('/api/visits',json=body|{'latitude':42}).status_code==422
    assert client.post('/api/visits',json=body|{'accuracy':999}).status_code==422
    response=client.post('/api/visits',json=body);assert response.status_code==200,response.text
    assert client.post('/api/visits',json=body).json()['visit_id']==response.json()['visit_id']
    with new_session() as db: assert db.scalar(select(func.count()).select_from(Visit))==1


def test_provider_failure_does_not_persist_fake_route(client,station,monkeypatch):
    from gef.errors import AppError
    async def fail(*args,**kwargs): raise AppError('PROVIDER_UNAVAILABLE',502)
    monkeypatch.setattr('gef.api.road_route',fail)
    response=client.post('/api/routes',json={'station_id':station['id'],'latitude':41.3,'longitude':69.2,'origin_kind':'live'})
    assert response.status_code==502
    with new_session() as db: assert db.scalar(select(func.count()).select_from(RouteSession))==0
