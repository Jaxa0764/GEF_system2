from datetime import timedelta
from sqlalchemy import select,func
from fastapi.testclient import TestClient
from app import app
from gef.db import new_session
from gef.models import Station,User,Session,Visit,Rating,RouteSession,Favorite,Support,Audit,utcnow
from conftest import signup

def test_health_assets_and_real_404(client):
    assert client.get('/health/live').json()['status']=='alive'
    assert client.get('/health/ready').status_code==200
    for path in ['/','/favorites','/assistant','/profile','/static/js/app.js','/static/styles.css','/static/vendor/leaflet/leaflet.js']:
        assert client.get(path).status_code==200,path
    for path in ['/api/unknown','/static/missing.js','/unknown']:
        response=client.get(path);assert response.status_code==404
        assert '<!doctype html>' not in response.text.lower()

def test_admin_is_server_protected(client,station_data):
    assert client.get('/admin').status_code==401
    assert client.post('/api/admin/stations',json=station_data).status_code==401
    signup(client)
    assert client.get('/admin').status_code==403
    assert client.post('/api/admin/stations',json=station_data).status_code==403
    response=client.get('/api/admin/users')
    assert response.status_code==403

def test_registration_validation_and_real_login(client):
    response=client.post('/api/auth/register',json={'username':'x','password':'123','confirm_password':'bad','first_name':'','last_name':'','confirmed':False})
    assert response.status_code==422
    assert '"input"' not in response.text and '123' not in response.text  # no echoed secret values
    data=signup(client)
    assert 'password_hash' not in str(data)
    with new_session() as db:
        user=db.get(User,data['user']['id']);assert user.password_hash.startswith('$argon2id$')
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/me').json()['user'] is None
    assert client.post('/api/auth/login',json={'username':'tester_1','password':'wrong-password'}).status_code==401
    response=client.post('/api/auth/login',json={'username':'tester_1','password':'StrongPass123!'})
    assert response.status_code==200
    cookie=response.headers['set-cookie'];assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie

def test_csrf_cross_origin_and_ownership(client,user):
    assert client.patch('/api/me',json={'first_name':'Hack','last_name':'Test'},headers={'X-CSRF-Token':'incorrect'}).status_code==403
    assert client.patch('/api/me',json={'first_name':'Hack','last_name':'Test'},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.patch('/api/me',json={'first_name':'Updated','last_name':'User'}).status_code==200
    assert client.patch('/api/me',json={'id':99,'role':'admin','first_name':'Hack','last_name':'Test'}).status_code==422

def test_publish_edit_unpublish_soft_delete_and_audit(client,admin,station_data):
    station_data['published']=False
    response=client.post('/api/admin/stations',json=station_data);assert response.status_code==201,response.text
    station_id=response.json()['id']
    assert client.get('/api/stations').json()['total']==0
    station_data['published']=True
    assert client.put('/api/admin/stations/'+str(station_id),json=station_data).status_code==200
    result=client.get('/api/stations?grade=AI-92').json()
    assert result['total']==1 and result['map_items'][0]['id']==station_id
    station_data['products'][0]['price']=9900
    client.put('/api/admin/stations/'+str(station_id),json=station_data)
    assert client.get('/api/stations/'+str(station_id)).json()['products'][0]['price']==9900
    # A retried create cannot duplicate the station.
    assert client.post('/api/admin/stations',json=station_data).json()['id']==station_id
    assert client.get('/api/stations').json()['total']==1
    assert client.delete('/api/admin/stations/'+str(station_id)).status_code==200
    assert client.get('/api/stations').json()['total']==0
    assert client.get('/api/stations/'+str(station_id)).status_code==404
    assert len(client.get('/api/admin/audit').json()['items'])>=4

def test_compatibility_and_coordinate_validation(client,admin,station_data):
    station_data['latitude']=95
    assert client.post('/api/admin/stations',json=station_data).status_code==422
    station_data['latitude']=41
    station_data['products'][0]['unit']='kwh'
    assert client.post('/api/admin/stations',json=station_data).status_code==422
    station_data['products'][0].update(unit='liter',pressure=2)
    assert client.post('/api/admin/stations',json=station_data).status_code==422

def test_account_favorites_support_and_persistence_across_client_restarts(client,station):
    sid=station['id']
    for _ in range(2): assert client.put('/api/favorites/'+str(sid)).status_code==200
    assert len(client.get('/api/favorites').json()['items'])==1
    assert client.post('/api/support',json={'message':'A real support request.'}).status_code==201
    saved_cookies=dict(client.cookies)
    with TestClient(app) as restarted:
        restarted.cookies.update(saved_cookies)
        assert restarted.get('/api/me').json()['user'] is not None
        assert len(restarted.get('/api/favorites').json()['items'])==1
        assert len(restarted.get('/api/support').json()['items'])==1
    # Independent account sees only its own data.
    client.post('/api/auth/logout');signup(client,'other_user')
    assert client.get('/api/favorites').json()['items']==[]
    assert client.get('/api/support').json()['items']==[]

def test_recovery_is_single_use_and_revokes_sessions(client,user):
    old_code=user['recovery_code']
    result=client.post('/api/auth/recover',json={'username':'tester_1','recovery_code':old_code,'password':'NewStrongPass456!'})
    assert result.status_code==200,result.text
    assert result.json()['recovery_code']!=old_code
    assert client.get('/api/me').json()['user'] is None
    assert client.post('/api/auth/recover',json={'username':'tester_1','recovery_code':old_code,'password':'AnotherPass789!'}).status_code==400
    assert client.post('/api/auth/login',json={'username':'tester_1','password':'NewStrongPass456!'}).status_code==200

def test_rating_requires_exact_station_visit_and_favorites_respect_removal(client,station):
    sid=station['id'];uid=client.get('/api/me').json()['user']['id']
    assert client.post(f'/api/stations/{sid}/rating',json={'stars':5}).status_code==403
    with new_session() as db:
        route=RouteSession(id='test-visited-route',user_id=uid,station_id=sid,live_origin=True,active=False,arrived=True)
        db.add(route);db.flush();db.add(Visit(user_id=uid,station_id=sid,route_id=route.id));db.commit()
    assert client.post(f'/api/stations/{sid}/rating',json={'stars':5}).status_code==200
    assert len(client.get('/api/favorites').json()['items'])==1
    client.delete(f'/api/favorites/{sid}')
    client.get(f'/api/stations/{sid}')
    assert client.get('/api/favorites').json()['items']==[]
    client.post(f'/api/stations/{sid}/rating',json={'stars':4})
    client.post(f'/api/stations/{sid}/rating',json={'stars':2})
    assert len(client.get('/api/favorites').json()['items'])==1
    with new_session() as db:
        assert db.scalar(select(func.count()).select_from(Rating))==1
    assert client.get(f'/api/stations/{sid}').json()['rating']==2

def test_support_admin_destination_and_safe_user_list(client,station):
    created=client.post('/api/support',json={'message':'Please check the fuel price.'}).json()
    requests=client.get('/api/admin/support').json()['items']
    assert requests[0]['id']==created['id']
    assert client.patch('/api/admin/support/'+str(created['id']),json={'status':'resolved'}).status_code==200
    assert client.get('/api/support').json()['items'][0]['status']=='resolved'
    text=client.get('/api/admin/users').text
    for secret in ['password_hash','code_hash','csrf','token_hash']: assert secret not in text

def test_avatar_is_processed_and_persistent(client,user):
    from PIL import Image
    import io
    image=Image.new('RGB',(100,120),'blue');out=io.BytesIO();image.save(out,format='PNG')
    response=client.post('/api/me/avatar',files={'file':('test.png',out.getvalue(),'image/png')})
    assert response.status_code==200,response.text
    result=client.get('/api/me/avatar');assert result.headers['content-type']=='image/webp'
    assert Image.open(io.BytesIO(result.content)).size==(256,256)
    assert client.post('/api/me/avatar',files={'file':('bad.png',b'<script>bad</script>','image/png')}).status_code==422

def test_no_key_database_assistant_uses_real_data(client,station):
    response=client.post('/api/assistant',json={'message':'AI-92 qayerda eng arzon?','language':'uz'})
    assert response.status_code==200,response.text
    data=response.json();assert data['mode']=='database' and data['stations'][0]['id']==station['id']
    assert data['stations'][0]['products'][0]['price']==10500
    response=client.post('/api/assistant',json={'message':'Eng yaqin metan qayerda?','language':'uz'})
    assert response.json()['needs_location'] is True

def test_routing_missing_is_honest(client,station):
    response=client.post('/api/routes',json={'station_id':station['id'],'latitude':41.3,'longitude':69.2,'origin_kind':'live'})
    assert response.status_code==503 and response.json()['error']['code']=='ROUTING_UNCONFIGURED'
