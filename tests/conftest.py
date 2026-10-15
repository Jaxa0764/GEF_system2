import pytest
from alembic.config import Config
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import select
from gef.config import settings
from gef.db import engine,new_session
from gef.models import User
from app import app

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setenv('APP_ENV','test')
    monkeypatch.setenv('DATABASE_URL','sqlite:///'+str(tmp_path/'test.sqlite'))
    monkeypatch.setenv('SESSION_SECRET','test-secret-32-characters-not-for-production')
    monkeypatch.setenv('APP_ORIGIN','http://testserver')
    monkeypatch.setenv('ROUTING_URL','')
    monkeypatch.setenv('GEOCODING_URL','')
    monkeypatch.setenv('AI_API_KEY','')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','')
    # Settings are rebuilt from environment on every cache miss, not class definition.
    settings.cache_clear();engine.cache_clear()
    command.upgrade(Config('alembic.ini'),'head')
    created_engine=engine()
    with TestClient(app) as c:
        c.headers.update({'X-GEF-Request':'1','Origin':'http://testserver'})
        yield c
    created_engine.dispose();engine.cache_clear();settings.cache_clear()

def signup(client,username='tester_1'):
    res=client.post('/api/auth/register',json={'username':username,'password':'StrongPass123!','confirm_password':'StrongPass123!','first_name':'Test','last_name':'User','confirmed':True})
    assert res.status_code==201,res.text
    client.headers['X-CSRF-Token']=res.json()['csrf_token']
    return res.json()

@pytest.fixture
def user(client):
    return signup(client)

@pytest.fixture
def admin(client,user):
    with new_session() as db:
        row=db.get(User,user['user']['id']);row.role='admin';db.commit()
    return user

@pytest.fixture
def station_data():
    return {'name':'Test Station','address':'Tashkent test address','descriptions':{'uz':'Sinov','ru':'Тест','en':'Test'},'latitude':41.3111,'longitude':69.2406,'hours':{},'is_24h':True,'override':'normal','published':True,'request_key':'test-request-0000001','products':[{'category':'fuel','name':'AI-92','price':10500,'unit':'liter','available':True}]}

@pytest.fixture
def station(client,admin,station_data):
    response=client.post('/api/admin/stations',json=station_data)
    assert response.status_code==201,response.text
    return response.json()
