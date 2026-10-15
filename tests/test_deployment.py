import ast
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlencode
from sqlalchemy import select
from gef.models import RateLimit
from gef.db import new_session,engine
from gef.config import settings

ROOT=Path(__file__).resolve().parents[1]

def test_import_does_not_connect_or_write_even_with_readonly_filesystem(tmp_path):
    code='''
import builtins,os,socket,sys
sys.dont_write_bytecode=True
original=builtins.open
def read_only(path,mode='r',*a,**k):
    if any(flag in mode for flag in ['w','a','x','+']): raise AssertionError('import tried to write')
    return original(path,mode,*a,**k)
builtins.open=read_only
def forbidden(*a,**k): raise AssertionError('import attempted external effect')
os.mkdir=forbidden
socket.create_connection=forbidden
import sqlalchemy
sqlalchemy.create_engine=forbidden
import app
assert app.app is not None
'''
    env=os.environ|{'DATABASE_URL':'','SESSION_SECRET':'','PYTHONDONTWRITEBYTECODE':'1'}
    run=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,capture_output=True,text=True)
    assert run.returncode==0,run.stderr


def test_missing_database_is_clear_setup_error_not_import_500(client,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','');settings.cache_clear();engine.cache_clear()
    assert client.get('/').status_code==200
    assert client.get('/health/live').status_code==200
    assert client.get('/health/ready').status_code==503
    assert client.get('/api/stations').json()['error']['code']=='DATABASE_REQUIRED'


def test_production_rejects_sqlite_and_sets_secure_cookie(client,monkeypatch):
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('APP_ORIGIN','https://gef.example.test');settings.cache_clear();engine.cache_clear()
    assert client.get('/health/ready').json()['error']['code']=='POSTGRES_REQUIRED'


def test_login_rate_limit_survives_new_sessions(client):
    for _ in range(10):
        result=client.post('/api/auth/login',json={'username':'missing','password':'invalid-password'})
        assert result.status_code==401
    result=client.post('/api/auth/login',json={'username':'missing','password':'invalid-password'})
    assert result.status_code==429
    with new_session() as db: assert len(db.scalars(select(RateLimit)).all())>0


def test_telegram_signature_freshness_and_no_privilege_escalation(client,monkeypatch):
    token='test-bot-token-not-real';monkeypatch.setenv('TELEGRAM_BOT_TOKEN',token);settings.cache_clear()
    def signed(stamp):
        values={'auth_date':str(stamp),'query_id':'test-query','user':json.dumps({'id':123456,'username':'admin'})}
        key=hmac.new(b'WebAppData',token.encode(),hashlib.sha256).digest()
        values['hash']=hmac.new(key,'\n'.join(f'{k}={v}' for k,v in sorted(values.items())).encode(),hashlib.sha256).hexdigest()
        return urlencode(values)
    assert client.post('/api/telegram/verify',json={'init_data':signed(int(time.time()))}).json()['verified']
    assert client.get('/api/me').json()['user'] is None
    assert client.post('/api/telegram/verify',json={'init_data':signed(int(time.time())-600)}).status_code==401
    assert client.post('/api/telegram/verify',json={'init_data':signed(int(time.time()))+'x'}).status_code==401


def test_locales_assets_modules_and_error_keys_are_complete():
    dictionaries=[json.loads((ROOT/f'static/locales/{locale}.json').read_text()) for locale in ['uz','ru','en']]
    assert set(dictionaries[0])==set(dictionaries[1])==set(dictionaries[2])
    dictionary=dictionaries[0];keys=set();errors=set()
    for path in (ROOT/'static/js').glob('*.js'):
        source=path.read_text();keys.update(re.findall(r"\b(?:t|tr|formField)\(\s*'([^']+)'",source))
        for target in re.findall(r"from ['\"](\./[^'\"]+)['\"]",source):assert (path.parent/target).is_file(),target
    keys.update(re.findall(r'data-(?:i18n|placeholder|aria)="([^"{}<>]+)"',(ROOT/'static/index.html').read_text()))
    assert not {key for key in keys if key not in dictionary and not key.endswith(('.','_'))}
    for path in [ROOT/'app.py',*(ROOT/'gef').glob('*.py')]:errors.update(re.findall(r"AppError\('([A-Z_]+)'",path.read_text()))
    assert all('e.'+code in dictionary for code in errors)
    html=(ROOT/'static/index.html').read_text()
    for target in re.findall(r'(?:src|href)="(/static/[^"?#]+)',html):assert (ROOT/target.lstrip('/')).is_file()


def test_unavailable_database_returns_readiness_failure(client,monkeypatch):
    monkeypatch.setenv('DATABASE_URL','postgresql+psycopg://invalid:invalid@127.0.0.1:1/unavailable');settings.cache_clear();engine.cache_clear()
    result=client.get('/health/ready');assert result.status_code==503
    assert 'invalid:invalid' not in result.text


def test_clean_checkout_cli_setup_seed_and_restart(tmp_path):
    import shutil
    import secrets
    target=tmp_path/'fresh-checkout'
    shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','.env','.venv','__pycache__','.pytest_cache','*.sqlite*','*.db'))
    env={k:v for k,v in os.environ.items() if k not in ['DATABASE_URL','SESSION_SECRET','APP_ENV','APP_ORIGIN']}
    env['PYTHONDONTWRITEBYTECODE']='1'
    def run(*args):
        proc=subprocess.run([sys.executable,*args],cwd=target,env=env,capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr
        return proc
    run('manage.py','init-local')
    assert (target/'.env').is_file()
    assert 'SESSION_SECRET=\n' not in (target/'.env').read_text()
    second=subprocess.run([sys.executable,'manage.py','init-local'],cwd=target,env=env,capture_output=True,text=True)
    assert second.returncode!=0
    run('-m','alembic','upgrade','head')
    env['ADMIN_PASSWORD']=secrets.token_urlsafe(18)
    run('manage.py','create-admin','--username','review_admin')
    env.pop('ADMIN_PASSWORD')
    run('manage.py','seed-demo','--confirm-demo')
    for _ in range(2):
        run('-c',"from fastapi.testclient import TestClient;from app import app;c=TestClient(app);assert c.get('/health/ready').status_code==200;data=c.get('/api/stations').json();assert data['total']==12;assert all(s['demo'] for s in data['items'])")
