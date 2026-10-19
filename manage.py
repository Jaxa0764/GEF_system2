"""Explicit management operations. Never invoked by an import or HTTP request."""
import argparse
import getpass
import os
import secrets
import re
from datetime import timedelta
from sqlalchemy import select, delete
from gef.db import new_session
from gef.config import settings
from gef.models import User, Station, Product, Session, RouteSession, RateLimit, ProviderCache, utcnow
from gef.security import password_hash, recovery_code


def init_local(args):
    from pathlib import Path
    target=Path('.env')
    if target.exists(): raise SystemExit('.env already exists; refusing to overwrite it.')
    template=Path('.env.example').read_text()
    template=template.replace('APP_ENV=production','APP_ENV=development')
    template=template.replace('DATABASE_URL=\n','DATABASE_URL=sqlite:///./gef-local.sqlite3\n')
    template=template.replace('SESSION_SECRET=\n','SESSION_SECRET='+secrets.token_urlsafe(48)+'\n')
    template=re.sub(r'APP_ORIGIN=https?://[^\n]+', f'APP_ORIGIN=http://localhost:{args.port}', template)
    template=template.replace('http://localhost:8000','http://localhost:'+str(args.port))
    target.write_text(template)
    target.chmod(0o600)
    print('Local .env created with a fresh secret. Run alembic upgrade head next.')

def admin(args):
    username=(args.username or os.getenv('ADMIN_USERNAME') or input('Admin username: ')).lower()
    if not re.fullmatch(r'[a-z0-9_]{3,32}',username): raise SystemExit('Username: 3–32 letters/digits/underscore.')
    password=os.getenv('ADMIN_PASSWORD') or getpass.getpass('Admin password (8+ characters): ')
    if not 8<=len(password)<=128: raise SystemExit('Password must contain 8–128 characters.')
    if not os.getenv('ADMIN_PASSWORD') and password!=getpass.getpass('Repeat password: '): raise SystemExit('Passwords differ.')
    with new_session() as db:
        user=db.scalar(select(User).where(User.username==username))
        if user: raise SystemExit('Account already exists. Use a unique initial administrator username.')
        user=User(username=username,first_name='Admin',last_name='GEF',password_hash=password_hash(password),role='admin')
        db.add(user); db.flush(); code=recovery_code(db,user.id); db.commit()
        print('Administrator created. Store this one-time recovery code securely: '+code)


def seed(args):
    if not args.confirm_demo: raise SystemExit('Pass --confirm-demo. All entries are fictional DEMO data.')
    if settings().production: raise SystemExit('Demo seeding is restricted to APP_ENV=development/test.')
    names=['Amir Temur','Chilonzor','Yunusobod','Sergeli','Mirzo Ulug‘bek','Olmazor','Yakkasaroy','Uchtepa','Bektemir','Shayxontohur','Chirchiq','Farg‘ona']
    with new_session() as db:
        for i,name in enumerate(names):
            key=f'demo-station-{i:04d}'
            if db.scalar(select(Station.id).where(Station.request_key==key)): continue
            lat=41.3111+(i%4-1.5)*0.018; lon=69.2406+(i//4-1)*0.024
            if i==11: lat,lon=40.3864,71.7864
            s=Station(name='DEMO · '+name,address='DEMO · '+name+', O‘zbekiston',latitude=lat,longitude=lon,is_24h=i%3!=1,hours={str(d):[['07:00','23:00']] for d in range(7)},published=True,demo=True,request_key=key,descriptions={'uz':'Faqat sinov uchun sun’iy ma’lumot.','ru':'Вымышленные данные для тестирования.','en':'Fictional data for testing only.'})
            db.add(s); db.flush()
            for category in ['fuel','metan','propan','elektr']:
                if category=='fuel':
                    for grade,price in [('AI-80',8000),('AI-92',10500),('AI-95',12500)]: s.products.append(Product(category=category,name=grade,price=price+(i%4)*300,unit='liter',available=i%5!=4))
                elif category in ['metan','propan']:
                    s.products.append(Product(category=category,name='CNG' if category=='metan' else 'LPG',price=(4200 if category=='metan' else 5800)+i*50,unit='m3' if category=='metan' else 'liter',available=True,pressure=200-i*3 if category=='metan' else 8-i*.2,pressure_unit='bar',pressure_at=utcnow()-timedelta(minutes=i*20)))
                else:
                    s.products.append(Product(category=category,name='DC',price=1700+i*50,unit='kwh',available=i%4!=3,power_kw=60 if i%2 else 120,connectors=['CCS2','GB/T'],connector_available=2))
        db.commit()
    print('12 DEMO stations seeded. No visits/ratings/accounts were fabricated.')


def cleanup(args):
    with new_session() as db:
        db.execute(delete(Session).where(Session.expires_at<utcnow()))
        db.execute(delete(ProviderCache).where(ProviderCache.expires_at<utcnow()))
        # Every rate window is <=1 hour; preserve the last 48 hours conservatively.
        import time
        db.execute(delete(RateLimit).where(RateLimit.window<int(time.time())//3600-48))
        db.execute(delete(RouteSession).where(RouteSession.started_at<utcnow()-timedelta(days=2),RouteSession.arrived.is_(False)))
        db.commit()
    print('Expired transient records removed.')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='GEF_system management')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('init-local'); p.add_argument('--port',type=int,default=8000); p.set_defaults(run=init_local)
    p=sub.add_parser('create-admin'); p.add_argument('--username'); p.set_defaults(run=admin)
    p=sub.add_parser('seed-demo'); p.add_argument('--confirm-demo',action='store_true'); p.set_defaults(run=seed)
    p=sub.add_parser('cleanup'); p.set_defaults(run=cleanup)
    p=sub.add_parser('generate-secret'); p.set_defaults(run=lambda args:print(secrets.token_urlsafe(48)))
    args=parser.parse_args(); args.run(args)
