import hashlib
import hmac
import secrets
import time
from datetime import timedelta, timezone
from fastapi import Depends, Request
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from sqlalchemy import select, delete
from .config import settings
from .db import get_db
from .models import User, Session, Recovery, RateLimit, utcnow
from .errors import AppError

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)

def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def digest(value):
    return hmac.new(settings().session_secret.encode(), value.encode(), hashlib.sha256).hexdigest()

def password_hash(password):
    return hasher.hash(password)

def password_ok(encoded, password):
    try:
        return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False

def limit(db, scope, identity, maximum, seconds=60):
    """Atomic durable fixed-window limit shared by workers and cold starts."""
    window = int(time.time()) // seconds
    key = digest(f'{scope}:{identity}')
    dialect = db.bind.dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(RateLimit).values(key=key, window=window, count=1)
    stmt = stmt.on_conflict_do_update(index_elements=['key','window'], set_={'count': RateLimit.count + 1}).returning(RateLimit.count)
    count = db.scalar(stmt)
    db.commit()  # Failed authentication attempts also consume the budget.
    if count > maximum:
        raise AppError('RATE_LIMIT', 429)

def client_key(request):
    # Do not trust arbitrary X-Forwarded-For. Configure the deployment proxy correctly.
    return request.client.host if request.client else 'unknown'

def optional_user(request: Request, db=Depends(get_db)):
    token = request.cookies.get('gef_session', '')
    if not token:
        return None
    session = db.get(Session, digest(token))
    if not session or aware(session.expires_at) <= utcnow():
        return None
    user = db.get(User, session.user_id)
    if not user or not user.active:
        return None
    request.state.session = session
    if not user.last_activity or utcnow() - aware(user.last_activity) > timedelta(minutes=5):
        user.last_activity = utcnow()
        db.commit()
    return user

def require_user(request: Request, user=Depends(optional_user)):
    if not user:
        raise AppError('AUTH_REQUIRED', 401)
    if request.method not in ['GET','HEAD','OPTIONS']:
        supplied = request.headers.get('X-CSRF-Token','')
        if not hmac.compare_digest(supplied, request.state.session.csrf):
            raise AppError('CSRF_INVALID', 403)
    return user

def require_admin(user=Depends(require_user)):
    if user.role != 'admin':
        raise AppError('ADMIN_REQUIRED', 403)
    return user

def safe_user(user):
    return {k:getattr(user,k) for k in ['id','username','first_name','last_name','role','active','language','theme','created_at','last_login','last_activity']} | {'has_avatar': bool(user.avatar)}

def recovery_code(db, user_id):
    code = secrets.token_urlsafe(32)
    old = db.get(Recovery, user_id)
    if old:
        old.code_hash, old.created_at = digest(code), utcnow()
    else:
        db.add(Recovery(user_id=user_id, code_hash=digest(code)))
    return code

def sign_in(db, user, response, request):
    old = request.cookies.get('gef_session')
    if old:
        db.execute(delete(Session).where(Session.token_hash == digest(old)))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(Session(token_hash=digest(token), user_id=user.id, csrf=csrf, expires_at=utcnow()+timedelta(days=settings().session_days)))
    user.last_login = user.last_activity = utcnow()
    db.commit()
    response.set_cookie('gef_session', token, max_age=settings().session_days*86400, httponly=True, secure=settings().secure_cookie, samesite='lax', path='/')
    return {'user': safe_user(user), 'csrf_token': csrf}
