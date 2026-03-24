# 🌐 موقع يحيى محمد حمد — النظام الإحصائي الذكي

## بيانات تسجيل الدخول

| المستخدم | كلمة المرور | النوع |
|----------|-------------|-------|
| yahya    | Yahya@2024  | مدير (غير محدود) |
| demo     | demo123     | تجريبي (مرتان فقط) |

> ⚠️ غيّر كلمة المرور بعد أول دخول من داخل الكود

---

## 🚀 النشر على Render.com (مجاني)

### الطريقة 1 — عبر GitHub (الأسهل)

1. **ارفع المشروع على GitHub:**
   ```bash
   git init
   git add .
   git commit -m "first commit"
   git remote add origin https://github.com/USERNAME/yahya-portfolio.git
   git push -u origin main
   ```

2. **اذهب إلى [render.com](https://render.com) وسجّل دخولاً**

3. **اضغط New → Web Service**

4. **اربط حساب GitHub واختر المستودع**

5. **إعدادات Render:**
   - **Name:** yahya-portfolio
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt && python -c "from app import init_db; init_db()"`
   - **Start Command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Plan:** Free

6. **اضغط Create Web Service** ✅

بعد 2-3 دقائق سيظهر رابطك:
`https://yahya-portfolio.onrender.com`

---

## 💻 التشغيل المحلي (للاختبار)

```bash
# تثبيت المكتبات
pip install -r requirements.txt

# تشغيل التطبيق
python app.py
```

ثم افتح: http://localhost:5000

---

## 🗂️ هيكل المشروع

```
yahya_portfolio/
├── app.py              ← التطبيق الرئيسي
├── requirements.txt    ← المكتبات
├── Procfile            ← أمر التشغيل (Render)
├── render.yaml         ← إعدادات Render
└── templates/
    ├── index.html      ← صفحة البورتفوليو
    ├── login.html      ← تسجيل الدخول
    ├── dashboard.html  ← النظام الإحصائي
    └── trial_expired.html ← انتهاء التجربة
```
