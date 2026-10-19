import hashlib
import hmac
import io
import json
import secrets
import time
import re
from datetime import timedelta
from urllib.parse import parse_qsl
from fastapi import APIRouter, Depends, Request, Response, UploadFile, File, Query
from fastapi import Header
from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError
from PIL import Image, ImageOps, UnidentifiedImageError
from .db import get_db, new_session
from .config import settings
from .errors import AppError
from .models import User, Session, Recovery, Station, Product, Favorite, Rating, Visit, RouteSession, Support, Audit, utcnow
from .schemas import Registration, Login, Reset, Names, Password, Preferences, StationInput, RouteInput, Arrival, Stars, Message, Chat, SupportStatus, TelegramData, BotRegistration
from .security import optional_user, require_user, require_admin, digest, password_hash, password_ok, safe_user, recovery_code, sign_in, aware, limit, client_key
from .stations import listing, public_station, serialize, stats_map, distance
from .providers import reverse_geocode, road_route
from .assistant import answer
from .telegram import send_telegram_message, webhook_secret

router=APIRouter(prefix='/api')

@router.post('/telegram/webhook')
async def telegram_webhook(request:Request,secret_token:str|None=Header(default=None,alias='X-Telegram-Bot-Api-Secret-Token')):
    cfg=settings()
    if not cfg.telegram_token: raise AppError('TELEGRAM_UNCONFIGURED',503)
    if not secret_token or not hmac.compare_digest(secret_token,webhook_secret(cfg.telegram_token)):
        raise AppError('TELEGRAM_INVALID',403)
    try:
        update=await request.json()
    except ValueError:
        raise AppError('TELEGRAM_INVALID',400)
    if not isinstance(update,dict): raise AppError('TELEGRAM_INVALID',400)
    message=update.get('message')
    if not isinstance(message,dict): return {'ok':True}
    sender=message.get('from')
    chat=message.get('chat')
    if not isinstance(sender,dict) or not isinstance(chat,dict) or not isinstance(chat.get('id'),int):
        return {'ok':True}
    chat_id=chat['id']
    text=message.get('text')
    command=text.split(maxsplit=1)[0].split('@',1)[0] if isinstance(text,str) and text.strip() else ''
    if command == '/start':
        webapp_url=cfg.telegram_webapp_url or cfg.origin
        if not webapp_url.startswith('https://'):
            raise AppError('TELEGRAM_WEBAPP_URL_REQUIRED',503)
        await send_telegram_message(cfg.telegram_token,chat_id,
            "👋 Assalomu alaykum! GEF_system botiga xush kelibsiz!\n\n"
            "GEF_system mini ilovasi orqali o‘zingizga mos zapravkani tez va qulay toping:\n"
            "📍 Atrofingizdagi eng yaqin zapravkalarni xaritada ko‘ring.\n"
            "💰 Narxlarni solishtirib, hamyonbop variantni tanlang.\n"
            "🗺️ Tanlangan zapravkagacha bo‘lgan masofa va taxminiy yo‘l vaqtini bilib oling.\n"
            "🧭 Marshrutni xaritada ko‘rib, manzilga qulay yo‘lni toping.\n"
            "🕒 Zapravkaning ish holati va ish vaqtini tekshiring.\n\n"
            "Joylashuvingizni aniqlash uchun mini ilovada geolokatsiyaga ruxsat bering.\n\n"
            "Mini ilovani oching va o‘zingizga yaqin zapravkani toping!",
            {'inline_keyboard':[[{'text':'🚀 MiniApp ni ochish','web_app':{'url':webapp_url}}]]})
        await send_telegram_message(cfg.telegram_token,chat_id,
            "Avtomatik ro‘yxatdan o‘tish uchun pastdagi tugma orqali o‘z telefon raqamingizni ulashing.",
            {'keyboard':[[{'text':'📱 Kontaktni ulashish','request_contact':True}]],'resize_keyboard':True,'one_time_keyboard':True})
        return {'ok':True}

    contact=message.get('contact')
    if isinstance(contact,dict):
        telegram_id=sender.get('id')
        if not isinstance(telegram_id,int) or contact.get('user_id') != telegram_id:
            await send_telegram_message(cfg.telegram_token,chat_id,
                "Iltimos, faqat o‘zingizning Telegram akkauntingizga tegishli kontaktni ulashing.")
            return {'ok':True}
        phone=contact.get('phone_number')
        if not isinstance(phone,str) or not phone.strip():
            raise AppError('TELEGRAM_INVALID',400)
        first_name=(sender.get('first_name') or 'Foydalanuvchi').strip()[:80]
        last_name=(sender.get('last_name') or '').strip()[:80]
        username=f'tg_{telegram_id}'
        with new_session() as db:
            user=db.scalar(select(User).where(User.telegram_id==telegram_id))
            if user:
                if not user.active:
                    await send_telegram_message(cfg.telegram_token,chat_id,
                        "Akkauntingiz vaqtincha faol emas. Yordam uchun administratorga murojaat qiling.")
                    return {'ok':True}
                user.first_name=first_name
                user.last_name=last_name
                user.phone_number=phone.strip()[:32]
            else:
                if db.scalar(select(User.id).where(User.username==username)):
                    username=f'{username[:26]}_1'
                user=User(username=username,first_name=first_name,last_name=last_name,
                    phone_number=phone.strip()[:32],telegram_id=telegram_id,
                    role='user',active=True,language='uz',theme='light',password_hash=None)
                db.add(user)
            db.commit()
        await send_telegram_message(cfg.telegram_token,chat_id,
            "✅ Ro‘yxatdan o‘tdingiz! Mini ilovani ochish uchun quyidagi tugmani bosing.",
            {'inline_keyboard':[[{'text':'🚀 MiniApp ni ochish','web_app':{'url':cfg.telegram_webapp_url or cfg.origin}}]],
             'remove_keyboard':True})
    return {'ok':True}

@router.get('/config')
def config():
    cfg=settings()
    return {'name':'GEF_system','default_language':'uz','tile_url':cfg.tile_url,'tile_attribution':cfg.tile_attribution,
            'tile_fallback_url':cfg.tile_fallback_url,'tile_fallback_attribution':cfg.tile_fallback_attribution,
            'routing_configured':bool(cfg.routing_url),'geocoding_configured':bool(cfg.geocoding_url),
            'ai_configured':bool(cfg.ai_key),'telegram_configured':bool(cfg.telegram_token),'support_url':cfg.support_url,
            'pressure_fresh_hours':cfg.pressure_hours,'poll_seconds':25,'setup_required':bool(cfg.problem())}

@router.post('/auth/register',status_code=201)
def register(payload:Registration,request:Request,response:Response,db=Depends(get_db)):
    limit(db,'register',client_key(request),6,3600)
    user=User(username=payload.username.lower(),first_name=payload.first_name,last_name=payload.last_name,password_hash=password_hash(payload.password))
    db.add(user)
    try: db.flush()
    except IntegrityError: raise AppError('USERNAME_TAKEN',409)
    code=recovery_code(db,user.id)
    return sign_in(db,user,response,request)|{'recovery_code':code}

@router.post('/auth/login')
def login(payload:Login,request:Request,response:Response,db=Depends(get_db)):
    limit(db,'login_ip',client_key(request),30,900)
    limit(db,'login_account',payload.username.lower(),10,900)
    user=db.scalar(select(User).where(User.username==payload.username.lower()))
    # Always perform a password hash for missing accounts to reduce enumeration timing.
    valid=password_ok(user.password_hash,payload.password) if (user and user.password_hash) else bool(password_hash(payload.password)) and False
    if not user or not user.active or not valid: raise AppError('INVALID_CREDENTIALS',401)
    return sign_in(db,user,response,request)

@router.get('/me')
def me(request:Request,user=Depends(optional_user)):
    return {'user':safe_user(user) if user else None,'csrf_token':request.state.session.csrf if user else None}

@router.post('/auth/logout')
def logout(request:Request,response:Response,user=Depends(require_user),db=Depends(get_db)):
    db.delete(request.state.session); db.commit()
    response.delete_cookie('gef_session',path='/')
    return {'ok':True}

@router.post('/auth/recover')
def recover(payload:Reset,request:Request,db=Depends(get_db)):
    limit(db,'recovery_ip',client_key(request),8,3600)
    limit(db,'recovery_account',payload.username.lower(),5,3600)
    user=db.scalar(select(User).where(User.username==payload.username.lower()).with_for_update())
    credential=db.get(Recovery,user.id) if user else None
    if not user or not user.active or not credential or not hmac.compare_digest(credential.code_hash,digest(payload.recovery_code)):
        raise AppError('RECOVERY_INVALID',400)
    user.password_hash=password_hash(payload.password)
    code=recovery_code(db,user.id)
    db.execute(delete(Session).where(Session.user_id==user.id))
    db.commit()
    return {'ok':True,'recovery_code':code}

@router.patch('/me')
def update_me(payload:Names,user=Depends(require_user),db=Depends(get_db)):
    user.first_name,user.last_name=payload.first_name,payload.last_name; db.commit()
    return {'user':safe_user(user)}

@router.patch('/me/preferences')
def preferences(payload:Preferences,user=Depends(require_user),db=Depends(get_db)):
    user.language,user.theme=payload.language,payload.theme; db.commit()
    return {'ok':True}

@router.post('/me/password')
def change_password(payload:Password,request:Request,user=Depends(require_user),db=Depends(get_db)):
    limit(db,'password_change',user.id,6,900)
    if user.password_hash and not password_ok(user.password_hash,payload.current_password): raise AppError('INVALID_CREDENTIALS',401)
    user.password_hash=password_hash(payload.new_password)
    code=recovery_code(db,user.id)
    current=request.state.session.token_hash
    db.execute(delete(Session).where(Session.user_id==user.id,Session.token_hash!=current)); db.commit()
    return {'ok':True,'recovery_code':code}

@router.post('/me/avatar')
async def avatar(file:UploadFile=File(...),user=Depends(require_user),db=Depends(get_db)):
    if file.content_type not in ['image/jpeg','image/png','image/webp']: raise AppError('AVATAR_INVALID',422)
    raw=await file.read(2*1024*1024+1)
    if len(raw)>2*1024*1024: raise AppError('AVATAR_TOO_LARGE',413)
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ['JPEG','PNG','WEBP'] or image.width*image.height>16000000:
                raise AppError('AVATAR_INVALID',422)
            image=ImageOps.exif_transpose(image).convert('RGB')
            image=ImageOps.fit(image,(256,256))
            out=io.BytesIO(); image.save(out,format='WEBP',quality=82)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError): raise AppError('AVATAR_INVALID',422)
    user.avatar=out.getvalue(); db.commit()
    return {'ok':True}

@router.get('/me/avatar')
def get_avatar(user=Depends(require_user)):
    if not user.avatar: raise AppError('NOT_FOUND',404)
    return Response(user.avatar,media_type='image/webp',headers={'Cache-Control':'private, no-store'})

@router.get('/stations')
def stations(category:str='fuel',sort:str='default',open_now:bool=False,grade:str|None=None,unit:str|None=None,pressure_unit:str='bar',latitude:float|None=Query(None,ge=-90,le=90),longitude:float|None=Query(None,ge=-180,le=180),page:int=Query(1,ge=1,le=100000),per_page:int=Query(9,ge=1,le=100),q:str|None=Query(None,max_length=160),db=Depends(get_db)):
    if (latitude is None)!=(longitude is None): raise AppError('LOCATION_INVALID',422)
    return listing(db,category,sort,open_now,grade,unit,pressure_unit,(latitude,longitude) if latitude is not None else None,page,per_page,q)

@router.get('/stations/{station_id}')
def station_detail(station_id:int,db=Depends(get_db)):
    station=public_station(db,station_id)
    return serialize(station,stats_map(db,[station_id]).get(station_id))

@router.get('/favorites')
def favorites(user=Depends(require_user),db=Depends(get_db)):
    ids=list(db.scalars(select(Favorite.station_id).where(Favorite.user_id==user.id)))
    stations=db.scalars(select(Station).where(Station.id.in_(ids))).all()
    stats=stats_map(db,ids)
    return {'items':[serialize(s,stats.get(s.id))|{'unavailable':s.deleted or not s.published} for s in stations]}

@router.put('/favorites/{station_id}')
def add_favorite(station_id:int,user=Depends(require_user),db=Depends(get_db)):
    public_station(db,station_id)
    insert_favorite(db,user.id,station_id); db.commit()
    return {'ok':True}

def insert_favorite(db,user_id,station_id):
    if db.bind.dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(Favorite).values(user_id=user_id,station_id=station_id,created_at=utcnow()).on_conflict_do_nothing())

@router.delete('/favorites/{station_id}')
def remove_favorite(station_id:int,user=Depends(require_user),db=Depends(get_db)):
    db.execute(delete(Favorite).where(Favorite.user_id==user.id,Favorite.station_id==station_id)); db.commit()
    return {'ok':True}

@router.post('/stations/{station_id}/rating')
def rate(station_id:int,payload:Stars,user=Depends(require_user),db=Depends(get_db)):
    public_station(db,station_id)
    limit(db,'rating',user.id,15,3600)
    if not db.scalar(select(Visit.id).where(Visit.user_id==user.id,Visit.station_id==station_id).limit(1)):
        raise AppError('VISIT_REQUIRED',403)
    if db.bind.dialect.name=='postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt=insert(Rating).values(user_id=user.id,station_id=station_id,stars=payload.stars,updated_at=utcnow())
    db.execute(stmt.on_conflict_do_update(index_elements=['user_id','station_id'],set_={'stars':payload.stars,'updated_at':utcnow()}))
    if payload.stars>=4: insert_favorite(db,user.id,station_id)
    db.commit()
    return {'ok':True,'station':serialize(db.get(Station,station_id),stats_map(db,[station_id]).get(station_id))}

@router.post('/routes')
async def routes(payload:RouteInput,request:Request,user=Depends(optional_user),db=Depends(get_db)):
    # Optional authenticated endpoint still checks CSRF before creating account-owned route state.
    if user and not hmac.compare_digest(request.headers.get('X-CSRF-Token',''),request.state.session.csrf): raise AppError('CSRF_INVALID',403)
    limit(db,'routes',user.id if user else client_key(request),20,60)
    station=public_station(db,payload.station_id)
    result=await road_route(db,(payload.latitude,payload.longitude),(station.latitude,station.longitude))
    route=None
    if user:
        if payload.route_id:
            route=db.get(RouteSession,payload.route_id)
            if not route or route.user_id!=user.id or route.station_id!=station.id or route.finished_at:
                raise AppError('ROUTE_INVALID',422)
            if payload.origin_kind!='live': route.live_origin=False
        else:
            route=RouteSession(id=secrets.token_urlsafe(24),user_id=user.id,station_id=station.id,live_origin=payload.origin_kind=='live')
            db.add(route)
        db.commit()
    return result|{'route_id':route.id if route else None,'station_id':station.id}

@router.post('/navigation/{route_id}/start')
def start_navigation(route_id:str,user=Depends(require_user),db=Depends(get_db)):
    route=db.get(RouteSession,route_id)
    if not route or route.user_id!=user.id or route.finished_at: raise AppError('ROUTE_INVALID',422)
    route.active=True; route.started_at=utcnow(); db.commit()
    return {'ok':True}

@router.post('/navigation/{route_id}/stop')
def stop_navigation(route_id:str,user=Depends(require_user),db=Depends(get_db)):
    route=db.get(RouteSession,route_id)
    if not route or route.user_id!=user.id: raise AppError('NOT_FOUND',404)
    route.active=False; route.finished_at=utcnow(); db.commit()
    return {'ok':True}

@router.post('/visits')
def visit(payload:Arrival,user=Depends(require_user),db=Depends(get_db)):
    limit(db,'visit',user.id,12,3600)
    # Serialize account arrivals across routes/tabs so the cooldown cannot race.
    db.scalar(select(User.id).where(User.id==user.id).with_for_update())
    route=db.scalar(select(RouteSession).where(RouteSession.id==payload.route_id).with_for_update())
    if not route or route.user_id!=user.id: raise AppError('ROUTE_INVALID',422)
    prior=db.scalar(select(Visit).where(Visit.route_id==route.id))
    if prior: return {'ok':True,'visit_id':prior.id,'station_id':route.station_id}
    age=utcnow()-aware(route.started_at)
    stamp=aware(payload.position_timestamp)
    if not payload.confirmed or not route.live_origin or not route.active or route.finished_at or age<timedelta(seconds=45) or age>timedelta(hours=6) or abs((utcnow()-stamp).total_seconds())>60:
        raise AppError('ARRIVAL_UNCONFIRMED',422)
    station=public_station(db,route.station_id)
    if distance(payload.latitude,payload.longitude,station.latitude,station.longitude)>max(40,min(100,payload.accuracy*1.5)):
        raise AppError('ARRIVAL_UNCONFIRMED',422)
    recent=db.scalar(select(Visit).where(Visit.user_id==user.id,Visit.station_id==station.id,Visit.created_at>utcnow()-timedelta(hours=12)).limit(1))
    if recent: raise AppError('VISIT_RECENT',409)
    row=Visit(user_id=user.id,station_id=station.id,route_id=route.id)
    db.add(row); route.arrived=True; route.active=False; route.finished_at=utcnow(); db.commit()
    return {'ok':True,'visit_id':row.id,'station_id':station.id}

@router.get('/geocode')
async def geocode(request:Request,latitude:float=Query(ge=-90,le=90),longitude:float=Query(ge=-180,le=180),language:str=Query('uz',pattern='^(uz|ru|en)$'),db=Depends(get_db)):
    limit(db,'geocode',client_key(request),10,60)
    return await reverse_geocode(db,latitude,longitude,language)

@router.post('/assistant')
async def chat(payload:Chat,request:Request,user=Depends(optional_user),db=Depends(get_db)):
    limit(db,'assistant',user.id if user else client_key(request),12,60)
    return await answer(db,payload)

@router.get('/support')
def support_history(user=Depends(require_user),db=Depends(get_db)):
    return {'items':[{'id':s.id,'message':s.message,'status':s.status,'created_at':s.created_at} for s in db.scalars(select(Support).where(Support.user_id==user.id).order_by(Support.created_at.desc()).limit(100))]}

@router.post('/support',status_code=201)
def support(payload:Message,user=Depends(require_user),db=Depends(get_db)):
    limit(db,'support',user.id,10,3600)
    item=Support(user_id=user.id,message=payload.message); db.add(item); db.commit()
    return {'id':item.id,'status':item.status}

@router.post('/telegram/verify')
def verify_telegram(payload:TelegramData,request:Request,db=Depends(get_db)):
    limit(db,'telegram',client_key(request),10,60)
    cfg=settings()
    if not cfg.telegram_token: raise AppError('TELEGRAM_UNCONFIGURED',503)
    pairs=parse_qsl(payload.init_data,keep_blank_values=True)
    if len({k for k,v in pairs})!=len(pairs): raise AppError('TELEGRAM_INVALID',401)
    values=dict(pairs); provided=values.pop('hash','')
    check='\n'.join(f'{k}={v}' for k,v in sorted(values.items()))
    key=hmac.new(b'WebAppData',cfg.telegram_token.encode(),hashlib.sha256).digest()
    expected=hmac.new(key,check.encode(),hashlib.sha256).hexdigest()
    try: age=time.time()-int(values.get('auth_date','0'))
    except ValueError: raise AppError('TELEGRAM_INVALID',401)
    if not hmac.compare_digest(provided,expected) or not -30<=age<=300: raise AppError('TELEGRAM_INVALID',401)
    try: identity=json.loads(values.get('user','{}'))
    except ValueError: raise AppError('TELEGRAM_INVALID',401)
    # Verification only: never grants application membership/admin or logs an account in.
    return {'verified':True,'telegram_id':identity.get('id')}

@router.post('/register-user')
@router.post('/telegram/register-bot-user')
def register_bot_user(payload:BotRegistration,request:Request,db=Depends(get_db)):
    limit(db,'bot_register',client_key(request),120,60)
    user=db.scalar(select(User).where(User.telegram_id==payload.telegram_id))
    first_name=(payload.first_name or '').strip() or 'Foydalanuvchi'
    last_name=(payload.last_name or '').strip()
    phone=(payload.phone_number or '').strip()

    if user:
        if first_name: user.first_name=first_name[:80]
        if last_name: user.last_name=last_name[:80]
        if phone: user.phone_number=phone[:32]
        db.commit()
        return {'ok':True,'action':'updated','user':safe_user(user)}

    raw_username=(payload.username or '').strip().lower()
    cleaned=re.sub(r'[^a-z0-9_]','',raw_username)[:32]
    candidate=cleaned if len(cleaned)>=3 else f'tg_{payload.telegram_id}'[:32]
    base_candidate=candidate[:28]
    counter=1
    while db.scalar(select(User.id).where(User.username==candidate)):
        candidate=f"{base_candidate}_{counter}"[:32]
        counter+=1

    user=User(
        username=candidate,
        first_name=first_name[:80],
        last_name=last_name[:80],
        phone_number=phone[:32] if phone else None,
        telegram_id=payload.telegram_id,
        role='user',
        active=True,
        language='uz',
        theme='light',
        password_hash=None
    )
    db.add(user)
    db.commit()
    return {'ok':True,'action':'created','user':safe_user(user)}

@router.post('/telegram/auth')
def telegram_auth(payload:TelegramData,request:Request,response:Response,db=Depends(get_db)):
    limit(db,'telegram_auth',client_key(request),30,60)
    cfg=settings()
    if not cfg.telegram_token: raise AppError('TELEGRAM_UNCONFIGURED',503)
    pairs=parse_qsl(payload.init_data,keep_blank_values=True)
    if len({k for k,v in pairs})!=len(pairs): raise AppError('TELEGRAM_INVALID',401)
    values=dict(pairs); provided=values.pop('hash','')
    check='\n'.join(f'{k}={v}' for k,v in sorted(values.items()))
    key=hmac.new(b'WebAppData',cfg.telegram_token.encode(),hashlib.sha256).digest()
    expected=hmac.new(key,check.encode(),hashlib.sha256).hexdigest()
    try: age=time.time()-int(values.get('auth_date','0'))
    except ValueError: raise AppError('TELEGRAM_INVALID',401)
    if not hmac.compare_digest(provided,expected) or not -300<=age<=86400: raise AppError('TELEGRAM_INVALID',401)
    try: identity=json.loads(values.get('user','{}'))
    except ValueError: raise AppError('TELEGRAM_INVALID',401)
    telegram_id=identity.get('id')
    if not telegram_id: raise AppError('TELEGRAM_INVALID',401)

    user=db.scalar(select(User).where(User.telegram_id==telegram_id))
    if not user:
        tg_username=identity.get('username')
        if tg_username:
            user=db.scalar(select(User).where(User.username==tg_username.lower()))
            if user and not user.telegram_id:
                user.telegram_id=telegram_id
                db.commit()

    if not user:
        first_name=(identity.get('first_name') or 'Foydalanuvchi').strip()
        last_name=(identity.get('last_name') or '').strip()
        tg_username=(identity.get('username') or '').strip().lower()
        cleaned=re.sub(r'[^a-z0-9_]','',tg_username)[:32]
        candidate=cleaned if len(cleaned)>=3 else f'tg_{telegram_id}'[:32]
        base_candidate=candidate[:28]
        counter=1
        while db.scalar(select(User.id).where(User.username==candidate)):
            candidate=f"{base_candidate}_{counter}"[:32]
            counter+=1
        user=User(
            username=candidate,
            first_name=first_name[:80],
            last_name=last_name[:80],
            telegram_id=telegram_id,
            role='user',
            active=True,
            language=identity.get('language_code','uz') if identity.get('language_code') in ['uz','ru','en'] else 'uz',
            theme='light',
            password_hash=None
        )
        db.add(user)
        db.flush()
    else:
        if identity.get('first_name'): user.first_name=identity['first_name'][:80]
        if identity.get('last_name'): user.last_name=identity['last_name'][:80]
        db.flush()

    if not user.active: raise AppError('INVALID_CREDENTIALS',401)
    return sign_in(db,user,response,request)|{'authenticated':True}

@router.get('/admin/stations')
def admin_stations(q:str=Query('',max_length=160),category:str|None=None,status:str='all',page:int=Query(1,ge=1),admin=Depends(require_admin),db=Depends(get_db)):
    stmt=select(Station).where(Station.deleted.is_(False))
    if q: stmt=stmt.where(Station.name.ilike(f'%{q}%'))
    if category: stmt=stmt.where(Station.products.any(Product.category==category))
    if status in ['published','draft']: stmt=stmt.where(Station.published.is_(status=='published'))
    total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    items=db.scalars(stmt.order_by(Station.updated_at.desc()).offset((page-1)*30).limit(30)).all()
    return {'items':[serialize(s)|{'request_key':s.request_key} for s in items],'total':total,'page':page}

def write_station(db,payload,admin,station=None):
    data=payload.model_dump(exclude={'products','request_key'})
    if station is None:
        station=Station(**data,request_key=payload.request_key); db.add(station); db.flush()
    else:
        for key,value in data.items(): setattr(station,key,value)
        station.products.clear(); db.flush()
    for p in payload.products:
        station.products.append(Product(**p.model_dump()))
    station.updated_at=utcnow()
    db.add(Audit(user_id=admin.id,action='station.publish' if station.published else 'station.draft',station_id=station.id))
    db.commit()
    return serialize(station)|{'request_key':station.request_key}

@router.post('/admin/stations',status_code=201)
def create_station(payload:StationInput,admin=Depends(require_admin),db=Depends(get_db)):
    existing=db.scalar(select(Station).where(Station.request_key==payload.request_key))
    if existing: return serialize(existing)|{'request_key':existing.request_key}
    try: return write_station(db,payload,admin)
    except IntegrityError:
        db.rollback()
        existing=db.scalar(select(Station).where(Station.request_key==payload.request_key))
        if existing: return serialize(existing)|{'request_key':existing.request_key}
        raise AppError('VALIDATION_ERROR',422)

@router.put('/admin/stations/{station_id}')
def edit_station(station_id:int,payload:StationInput,admin=Depends(require_admin),db=Depends(get_db)):
    station=db.get(Station,station_id)
    if not station or station.deleted: raise AppError('NOT_FOUND',404)
    return write_station(db,payload,admin,station)

@router.delete('/admin/stations/{station_id}')
def delete_station(station_id:int,admin=Depends(require_admin),db=Depends(get_db)):
    station=db.get(Station,station_id)
    if not station or station.deleted: raise AppError('NOT_FOUND',404)
    station.deleted=True; station.published=False; station.updated_at=utcnow()
    db.add(Audit(user_id=admin.id,station_id=station.id,action='station.delete')); db.commit()
    return {'ok':True}

@router.get('/admin/users')
def users(page:int=Query(1,ge=1),admin=Depends(require_admin),db=Depends(get_db)):
    return {'items':[safe_user(u) for u in db.scalars(select(User).order_by(User.id).offset((page-1)*50).limit(50))],'total':db.scalar(select(func.count()).select_from(User))}

@router.get('/admin/support')
def admin_support(page:int=Query(1,ge=1),admin=Depends(require_admin),db=Depends(get_db)):
    return {'items':[{'id':s.id,'user_id':s.user_id,'message':s.message,'status':s.status,'created_at':s.created_at} for s in db.scalars(select(Support).order_by(Support.created_at.desc()).offset((page-1)*50).limit(50))]}

@router.patch('/admin/support/{support_id}')
def update_support(support_id:int,payload:SupportStatus,admin=Depends(require_admin),db=Depends(get_db)):
    item=db.get(Support,support_id)
    if not item: raise AppError('NOT_FOUND',404)
    item.status=payload.status
    db.add(Audit(user_id=admin.id,action=f'support.{support_id}.{payload.status}')); db.commit()
    return {'ok':True}

@router.get('/admin/audit')
def audit(page:int=Query(1,ge=1),admin=Depends(require_admin),db=Depends(get_db)):
    return {'items':[{'id':a.id,'user_id':a.user_id,'action':a.action,'station_id':a.station_id,'created_at':a.created_at} for a in db.scalars(select(Audit).order_by(Audit.id.desc()).offset((page-1)*50).limit(50))]}
