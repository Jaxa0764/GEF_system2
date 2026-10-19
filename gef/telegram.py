import hashlib
import hmac

import httpx

from .errors import AppError


def webhook_secret(token:str)->str:
    return hmac.new(token.encode(),b'GEF_system Telegram webhook',hashlib.sha256).hexdigest()


async def send_telegram_message(token:str,chat_id:int,text:str,reply_markup:dict|None=None)->None:
    payload={'chat_id':chat_id,'text':text}
    if reply_markup is not None:
        payload['reply_markup']=reply_markup
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response=await client.post(f'https://api.telegram.org/bot{token}/sendMessage',json=payload)
            response.raise_for_status()
            result=response.json()
    except (httpx.HTTPError,ValueError) as exc:
        raise AppError('TELEGRAM_DELIVERY_FAILED',502) from exc
    if not result.get('ok'):
        raise AppError('TELEGRAM_DELIVERY_FAILED',502)
