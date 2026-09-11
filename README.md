# DJAR RVC Studio

**Professional portable Windows desktop workstation for your local RVC API.**

---

## 🇮🇷 راهنمای فارسی

**DJAR RVC Studio** یک نرم‌افزار ویندوزی Portable با رابط مدرن و حرفه‌ای برای کنترل RVC WebUI/API روی همان کامپیوتر است. این نسخه با یک رابط دسکتاپ مدرن ساخته شده و برای استفاده روزمره در تبدیل صدا طراحی شده است.

> **مهم:** این برنامه موتور RVC و مدل‌های Voice را داخل خود ندارد. RVC روی کامپیوتر شما اجرا می‌شود و DJAR RVC Studio از طریق API محلی به آن متصل می‌شود.

### ✨ امکانات

- رابط گرافیکی مدرن و Dark
- وضعیت لحظه‌ای اتصال RVC
- تست اتصال با یک کلیک
- انتخاب Voice / Speaker
- Refresh مدل‌ها / Voiceها
- انتخاب فایل صوتی
- F0: RMVPE، CREPE، Harvest، PM
- Pitch / Transpose از -12 تا +12
- Index / Feature Ratio
- Protect Breath / Consonants
- Median Filter
- Resample Rate
- Volume Envelope Mix
- انتخاب Feature Index
- نوار پیشرفت تبدیل
- نمایش وضعیت عملیات
- ذخیره خودکار تنظیمات برنامه
- ذخیره خروجی در پوشه `DJAR_RVC_Output`
- باز کردن مستقیم پوشه خروجی
- بدون نیاز به نصب Python

### ⬇️ دانلود نسخه Portable

**[دانلود DJAR RVC Studio از GitHub Actions](https://github.com/ahmadrezahsnz81-stack/REPO1/actions/workflows/build-windows.yml)**

مراحل:

1. وارد صفحه GitHub Actions شوید.
2. آخرین اجرای **Success** را باز کنید.
3. پایین صفحه قسمت **Artifacts** را پیدا کنید.
4. روی **DJAR-RVC-Studio-Portable** کلیک کنید.
5. فایل ZIP را کامل روی کامپیوتر ذخیره کنید.
6. روی ZIP راست‌کلیک و **Extract All** را انتخاب کنید.
7. وارد پوشه `DJAR RVC Studio` شوید.
8. فایل **`DJAR RVC Studio.exe`** را اجرا کنید.

### 🖥️ پیش‌نیاز

- Windows 10 / 11
- RVC WebUI/API روی همان کامپیوتر
- API روی پورت `7897`
- آدرس پیش‌فرض:
  `http://127.0.0.1:7897`

Python جداگانه لازم نیست.

### 🔌 راه‌اندازی

**مرحله ۱ — RVC را اجرا کنید**

ابتدا RVC WebUI/API خودتان را اجرا کنید و مطمئن شوید API روی پورت 7897 در دسترس است.

**مرحله ۲ — DJAR RVC Studio را اجرا کنید**

برنامه را باز کنید. در بالای برنامه آدرس API قرار دارد:

`http://127.0.0.1:7897`

اگر RVC روی پورت دیگری اجرا می‌شود، همان‌جا آدرس را تغییر دهید.

**مرحله ۳ — تست اتصال**

روی **Test Connection** بزنید. در صورت موفقیت، وضعیت بالای برنامه به **RVC CONNECTED** تغییر می‌کند.

**مرحله ۴ — انتخاب Voice**

روی **Refresh** بزنید تا لیست Voice/مدل‌های قابل دریافت از RVC تازه شود. در صورت عدم ارائه لیست توسط نسخه RVC، می‌توانید Speaker ID موجود را استفاده کنید.

**مرحله ۵ — انتخاب صدا**

فایل WAV، MP3، FLAC، OGG یا M4A را انتخاب کنید.

**مرحله ۶ — تنظیم پارامترها**

Pitch، Index، Protect و تنظیمات Advanced را مطابق مدل و پروژه تنظیم کنید.

**مرحله ۷ — تبدیل**

روی **CONVERT AUDIO** بزنید. فایل خروجی در کنار فایل اصلی، داخل پوشه:

`DJAR_RVC_Output`

ذخیره می‌شود.

### 📁 محل خروجی

مثلاً اگر فایل شما این باشد:

`D:\Music\input.wav`

خروجی در این مسیر قرار می‌گیرد:

`D:\Music\DJAR_RVC_Output\input_RVC.wav`

### 🧩 معماری

```text
Telegram / DJAR (cPanel)
          │
          │  Job / Request
          ▼
   DJAR RVC Studio
        Windows
          │
          │ HTTP API
          ▼
   RVC WebUI / API
      127.0.0.1:7897
          │
          ▼
   Voice Conversion
          │
          ▼
     Output Audio
```

نسخه فعلی نرم‌افزار رابط دسکتاپ و Bridge سمت RVC است. اتصال مستقیم و امن DJAR روی cPanel به این برنامه می‌تواند در نسخه بعدی اضافه شود.

### ❗ عیب‌یابی

**RVC CONNECTED نمی‌شود:**

1. RVC را اجرا کنید.
2. پورت API را بررسی کنید.
3. آدرس داخل برنامه را بررسی کنید.
4. Windows Firewall را بررسی کنید.
5. دوباره Test Connection را بزنید.

**فایل تبدیل نمی‌شود:**

1. مطمئن شوید فایل صوتی واقعاً وجود دارد.
2. Voice/Speaker ID را بررسی کنید.
3. Feature Index را فقط در صورت نیاز انتخاب کنید.
4. لاگ خطای نمایش‌داده‌شده توسط برنامه را بررسی کنید.

**WinRAR خطای `The system cannot find the path specified` می‌دهد:**

ZIP را ابتدا کامل روی هارد ذخیره کنید و بعد Extract کنید؛ فایل را مستقیماً از داخل مسیر موقت مرورگر یا پنجره WinRAR باز نکنید.

---

## 🇬🇧 English

DJAR RVC Studio is a modern portable Windows desktop workstation for controlling a local RVC WebUI/API instance.

### Features

- Modern dark desktop UI
- RVC connection status
- Connection test
- Voice/Speaker selection and refresh
- RMVPE / CREPE / Harvest / PM
- Pitch / transpose
- Index / feature ratio
- Protect
- Median filter
- Resample rate
- Volume envelope mix
- Feature index selection
- Conversion progress
- Persistent settings
- Output folder management

### Requirements

- Windows 10 or Windows 11
- Local RVC WebUI/API
- Default API: `http://127.0.0.1:7897`
- Python is not required separately.

### Download

**[Download the latest Portable build](https://github.com/ahmadrezahsnz81-stack/REPO1/actions/workflows/build-windows.yml)**

Open the latest successful workflow, download `DJAR-RVC-Studio-Portable`, extract it, open the `DJAR RVC Studio` folder, and run `DJAR RVC Studio.exe`.

---

## Repository

**DJAR RVC Studio — REPO1**

https://github.com/ahmadrezahsnz81-stack/REPO1
