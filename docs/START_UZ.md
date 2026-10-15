# GEF_system’ni ishga tushirish

ZIP’ni oching. Terminalda `GEF_system` papkasiga kiring. Python 3.12 kerak.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py init-local
alembic upgrade head
python manage.py create-admin --username gef_admin
python manage.py seed-demo --confirm-demo
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Brauzerda `http://localhost:8000` ni oching. `create-admin` paytida parolni o‘zingiz kiritasiz. Universal tayyor admin paroli yo‘q. Parol terminalda ko‘rinmaydi — bu normal. Ko‘rsatilgan tiklash kodini xavfsiz joyga saqlang.

Profil → Kirish orqali kiring. Tepada **Admin panel** tugmasi chiqadi. Yoki `/admin` manziliga o‘ting.

1. **Shoxobcha qo‘shish** ni bosing.
2. Nom, manzil, ish vaqti va mahsulotlarni to‘ldiring.
3. Mahsulot toifasiga mos narx va birlikni kiriting. Metan/propan uchun bosimni kiritsangiz, o‘lchangan vaqtni ham ko‘rsating.
4. Pastdagi **Manzilni xaritada tanlang** tugmasini bosing. Xaritaga belgini qo‘ying yoki koordinatalarni kiriting.
5. **Joylashuvni saqlash** ni bosing, keyin **E’lon qilish** ni bosing.
6. Shoxobcha tegishli toifada ko‘rinadi. Boshqa ochiq oynalarda 25 soniyagacha yangilanadi.

`seed-demo` faqat tekshirish uchun 12 ta **sun’iy DEMO** shoxobcha qo‘shadi. Ular haqiqiy narx yoki tekshirilgan shoxobcha emas. Bo‘sh sayt kerak bo‘lsa, bu buyruqni bajarmang. Production’da bu buyruq taqiqlangan.

## Xarita, joylashuv va marshrut

Xarita OpenStreetMap qatlamlari bilan ochiladi. Joylashuv tugmasini bosib ruxsat bering. Kompyuterda aniqlik qurilmaga bog‘liq. Toshkent xaritaning boshlang‘ich ko‘rish markazi; u sizning joylashuvingiz deb ko‘rsatilmaydi.

Marshrutni sayt ichida chizish uchun `.env` dagi `ROUTING_URL` ga haqiqiy OSRM-mos HTTPS xizmati kerak. Kichik mahalliy sinov uchun `https://router.project-osrm.org` demo xizmatidan uning foydalanish shartlari bilan foydalanish mumkin. Production uchun alohida mos xizmat yoki o‘z serveringizni tanlang. Manzilni matn sifatida olish uchun `GEOCODING_URL` sozlanadi; sozlanmasa koordinatalar ko‘rsatiladi.

Ushbu xizmatlar sozlanmagan paytda ham **Yandex Maps’da ochish** tugmasi manzilga tashqi yo‘nalish beradi. AI yordamchi API kalitsiz ham bazadagi shoxobchalar bo‘yicha javob beradi. Kengroq matnli AI javobi uchun serverda `AI_API_KEY` va mos modelni sozlash mumkin.

## GitHub → hosting

GitHub’da bo‘sh repository yarating. **GEF_system papkasining ichidagi fayllarni** repository ildiziga yuklang: ildizda `app.py`, `requirements.txt`, `static/` va `gef/` turishi kerak. `.env`, `.venv` yoki baza faylini yuklamang.

Vercel yoki Railway’da shu repository’ni import qiling. Har ikkisi uchun:

- `APP_ENV=production`
- Tashqi PostgreSQL bazaning `DATABASE_URL` manzili
- `python manage.py generate-secret` orqali olingan alohida `SESSION_SECRET`
- Saytingizning to‘liq HTTPS manzili bo‘lgan `APP_ORIGIN`

Kerakli xarita/marshrut xizmatlarini ham sozlang. Bazani `alembic upgrade head` bilan tayyorlang, keyin administratorni bir marta yarating. Railway migratsiyani `railway.toml` orqali pre-deploy bosqichida bajaradi. Vercel uchun migratsiyani terminaldan alohida bajarasiz.

Batafsil: [DEPLOYMENT.md](DEPLOYMENT.md). Sayt hali Vercel/Railway akkauntingizga joylangan deb hisoblanmaydi; ZIP ichida shu hostinglarga tayyor loyiha mavjud.
