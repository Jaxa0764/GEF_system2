from sqlalchemy import select
from types import SimpleNamespace

from gef.config import settings
from gef.db import new_session
from gef.models import User
from gef.telegram import webhook_secret
import manage


def configure_bot(monkeypatch):
    token='test-telegram-bot-token'
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN',token)
    monkeypatch.setenv('TELEGRAM_WEBAPP_URL','https://gef.example/')
    settings.cache_clear()
    return token


def test_telegram_start_sends_welcome_with_miniapp_and_contact_buttons(client,monkeypatch):
    token=configure_bot(monkeypatch)
    sent=[]

    async def fake_send(bot_token,chat_id,text,reply_markup=None):
        sent.append((bot_token,chat_id,text,reply_markup))

    monkeypatch.setattr('gef.api.send_telegram_message',fake_send)
    response=client.post('/api/telegram/webhook',
        headers={'X-Telegram-Bot-Api-Secret-Token':webhook_secret(token)},
        json={'update_id':1,'message':{'message_id':1,'from':{'id':42},'chat':{'id':42},'text':'/start'}})

    assert response.status_code==200
    assert len(sent)==2
    assert sent[0][3]['inline_keyboard'][0][0]['web_app']['url']=='https://gef.example/'
    assert sent[1][3]['keyboard'][0][0]['request_contact'] is True


def test_telegram_webhook_registers_only_the_sender_contact(client,monkeypatch):
    token=configure_bot(monkeypatch)
    sent=[]

    async def fake_send(bot_token,chat_id,text,reply_markup=None):
        sent.append((text,reply_markup))

    monkeypatch.setattr('gef.api.send_telegram_message',fake_send)
    response=client.post('/api/telegram/webhook',
        headers={'X-Telegram-Bot-Api-Secret-Token':webhook_secret(token)},
        json={'update_id':2,'message':{
            'message_id':2,'from':{'id':987654321,'first_name':'Telegram','last_name':'User'},
            'chat':{'id':987654321},
            'contact':{'user_id':987654321,'first_name':'Telegram','phone_number':'+998901234567'},
        }})

    assert response.status_code==200
    with new_session() as db:
        user=db.scalar(select(User).where(User.telegram_id==987654321))
        assert user is not None
        assert user.phone_number=='+998901234567'
        assert user.role=='user'
    assert sent[0][1]['inline_keyboard'][0][0]['web_app']['url']=='https://gef.example/'


def test_telegram_webhook_rejects_wrong_contact_owner(client,monkeypatch):
    token=configure_bot(monkeypatch)
    sent=[]

    async def fake_send(bot_token,chat_id,text,reply_markup=None):
        sent.append(text)

    monkeypatch.setattr('gef.api.send_telegram_message',fake_send)
    response=client.post('/api/telegram/webhook',
        headers={'X-Telegram-Bot-Api-Secret-Token':webhook_secret(token)},
        json={'update_id':3,'message':{
            'message_id':3,'from':{'id':42},'chat':{'id':42},
            'contact':{'user_id':99,'phone_number':'+998901234567'},
        }})

    assert response.status_code==200
    with new_session() as db:
        assert db.scalar(select(User).where(User.telegram_id==99)) is None
    assert len(sent)==1


def test_telegram_webhook_rejects_wrong_secret(client,monkeypatch):
    configure_bot(monkeypatch)
    response=client.post('/api/telegram/webhook',
        headers={'X-Telegram-Bot-Api-Secret-Token':'wrong-secret'},
        json={'update_id':4,'message':{'from':{'id':42},'chat':{'id':42},'text':'/start'}})

    assert response.status_code==403


def test_webhook_setup_registers_public_app_origin(monkeypatch):
    token=configure_bot(monkeypatch)
    monkeypatch.setenv('APP_ORIGIN','https://gef.example')
    settings.cache_clear()
    calls=[]

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {'ok':True}

    def fake_post(url,*,json,timeout):
        calls.append((url,json,timeout))
        return Response()

    monkeypatch.setattr(manage.httpx,'post',fake_post)
    manage.set_telegram_webhook(SimpleNamespace())

    assert calls[0][0]=='https://api.telegram.org/bot'+token+'/setWebhook'
    assert calls[0][1]['url']=='https://gef.example/api/telegram/webhook'
    assert calls[0][1]['secret_token']==webhook_secret(token)
