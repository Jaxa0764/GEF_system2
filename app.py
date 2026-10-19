"""Supported Vercel/FastAPI entrypoint. Import is read-only and network-free."""
import logging
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from gef.api import router
from gef.config import settings
from gef.db import get_db
from gef.errors import AppError
from gef.security import require_admin

ROOT=Path(__file__).resolve().parent
app=FastAPI(title='GEF_system API',version='1.0.0',debug=False)
app.include_router(router)

@app.exception_handler(AppError)
async def app_error(request,exc):
    return JSONResponse({'error':{'code':exc.code,'fields':exc.fields}},status_code=exc.status)

@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    fields={'.'.join(str(x) for x in item['loc'][1:]):item['type'] for item in exc.errors()}
    return JSONResponse({'error':{'code':'VALIDATION_ERROR','fields':fields}},status_code=422)

@app.exception_handler(SQLAlchemyError)
async def database_error(request,exc):
    # SQL/credentials/parameters are deliberately excluded from logs and responses.
    logging.getLogger('gef').warning('Database operation failed: %s',type(exc).__name__)
    return JSONResponse({'error':{'code':'DATABASE_UNAVAILABLE','fields':{}}},status_code=503)

@app.exception_handler(HTTPException)
async def http_error(request,exc):
    return JSONResponse({'error':{'code':'NOT_FOUND' if exc.status_code==404 else 'REQUEST_FAILED','fields':{}}},status_code=exc.status_code)

@app.middleware('http')
async def request_security(request:Request,call_next):
    if request.url.path.startswith('/api/') and request.method not in ['GET','HEAD','OPTIONS']:
        if request.url.path in ['/api/register-user', '/api/telegram/register-bot-user']:
            response = await call_next(request)
            return response
        origin=request.headers.get('origin')
        allowed=settings().origin or str(request.base_url).rstrip('/')
        if request.url.path!='/api/telegram/webhook' and (request.headers.get('X-GEF-Request')!='1' or (origin and origin!=allowed)):
            return JSONResponse({'error':{'code':'CSRF_INVALID','fields':{}}},status_code=403)
        length=request.headers.get('content-length')
        if length:
            try: too_large=int(length)>3*1024*1024
            except ValueError: too_large=True
            if too_large:
                return JSONResponse({'error':{'code':'REQUEST_TOO_LARGE','fields':{}}},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['Permissions-Policy']='geolocation=(self), camera=(), microphone=()'
    # No X-Frame-Options: Telegram Web embeds Mini Apps. CSP confines executable code.
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' https://telegram.org; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' https:; frame-ancestors 'self' https://web.telegram.org https://*.telegram.org; base-uri 'self'; form-action 'self'; object-src 'none'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response

@app.get('/health/live')
def live():
    return {'status':'alive'}

@app.get('/health/ready')
def ready(db=Depends(get_db)):
    db.execute(text('SELECT 1'))
    version=db.scalar(text('SELECT version_num FROM alembic_version'))
    if version not in ['0001_initial', '0002_telegram_fields']: raise AppError('MIGRATIONS_REQUIRED',503)
    return {'status':'ready'}

@app.get('/admin',include_in_schema=False)
def admin_page(admin=Depends(require_admin)):
    return FileResponse(ROOT/'static/admin.html',headers={'Cache-Control':'no-store'})

@app.get('/',include_in_schema=False)
@app.get('/favorites',include_in_schema=False)
@app.get('/assistant',include_in_schema=False)
@app.get('/profile',include_in_schema=False)
def index():
    return FileResponse(ROOT/'static/user.html',headers={'Cache-Control':'no-cache'})

@app.get('/favicon.ico',include_in_schema=False)
def favicon():
    return FileResponse(ROOT/'static/logo.svg',media_type='image/svg+xml')

# Exact mount only. Unknown /api routes and missing assets remain real 404s.
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')

# DEBUG: show details for admin requests (remove in production)
@app.get('/debug_admin', include_in_schema=False)
def debug_admin(request: Request, admin=Depends(require_admin)):
    # Return useful debug info about the request and session
    info = {
        'origin': request.headers.get('origin'),
        'host': request.headers.get('host'),
        'secure_cookie': settings().secure_cookie,
        'session_token': request.cookies.get('gef_session'),
        'csrf_token': request.state.session.csrf if hasattr(request.state, 'session') else None,
        'user': admin.username,
        'role': admin.role,
    }
    return info
