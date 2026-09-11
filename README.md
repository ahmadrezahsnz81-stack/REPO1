# DJAR RVC Studio

Portable Windows desktop controller for the local RVC API.

---

## 🇮🇷 راهنمای فارسی

**DJAR RVC Studio** یک نرم‌افزار ویندوزی Portable برای اتصال ساده و مستقیم به RVC WebUI/API روی همان کامپیوتر است.

> **نکته مهم:** این برنامه خودِ موتور RVC، مدل‌های Voice و فایل‌های سنگین مدل را داخل خود ندارد. RVC روی ویندوز شما اجرا می‌شود و برنامه از طریق API به آن متصل می‌شود.

### ⬇️ دانلود نسخه Portable

**[دانلود DJAR RVC Studio Portable از GitHub Actions](https://github.com/ahmadrezahsnz81-stack/REPO1/actions/workflows/build-windows.yml)**

برای دانلود:

1. روی لینک بالا وارد GitHub Actions شوید.
2. آخرین اجرای موفق با وضعیت **Success** را باز کنید.
3. پایین صفحه، بخش **Artifacts** را پیدا کنید.
4. روی **DJAR-RVC-Studio-Portable** کلیک کنید.
5. فایل ZIP دانلودشده را در یک پوشه معمولی مثل `Downloads` یا Desktop ذخیره کنید.
6. ZIP را با Windows Explorer یا WinRAR روی هارد استخراج کنید.
7. بعد از Extract، وارد پوشه **DJAR RVC Studio** شوید.
8. فایل **`DJAR RVC Studio.exe`** را اجرا کنید.

> **توجه:** نسخه جدید Artifact مستقیماً پوشه Portable را ارائه می‌کند و دیگر نباید یک ZIP داخلی را از داخل ZIP دیگری باز یا استخراج کنید.

### 🖥️ پیش‌نیازها

- Windows 10 یا Windows 11
- RVC WebUI/API روی همان کامپیوتر
- API باید روی پورت `7897` فعال باشد.
- آدرس پیش‌فرض اتصال برنامه:
  `http://127.0.0.1:7897`

### 🔌 اتصال به RVC

اگر RVC WebUI شما روی پورت پیش‌فرض اجرا می‌شود، نیازی به تغییر چیزی نیست.

برنامه به این آدرس متصل می‌شود:

`http://127.0.0.1:7897`

ابتدا داخل برنامه **Test Connection** را بزنید. اگر اتصال موفق باشد، می‌توانید تبدیل صدا را انجام دهید.

### 🎙️ امکانات فعلی

- Native Windows GUI
- اتصال به Local RVC API
- انتخاب Voice / Speaker ID
- انتخاب فایل صوتی
- F0 Method:
  - RMVPE
  - CREPE
  - Harvest
  - PM
- Pitch / Transpose
- Index / Feature Ratio
- Protect
- Median Filter
- Resample Rate
- Volume Envelope Mix
- تست اتصال به RVC
- دریافت خروجی تبدیل‌شده

### 🧩 معماری اتصال

```text
DJAR روی cPanel
       │
       │  Job / Request
       ▼
DJAR RVC Studio روی Windows
       │
       │  HTTP API
       ▼
RVC WebUI / API :7897
       │
       ▼
Voice Conversion
       │
       ▼
Output Audio
```

در نسخه فعلی، **DJAR RVC Studio فقط رابط ویندوز و Bridge سمت RVC است**. اتصال واقعی ربات DJAR روی cPanel به این برنامه در مرحله بعدی قابل اضافه شدن است.

### ❗ اگر برنامه یا استخراج فایل مشکل داشت

**خطای WinRAR مثل `The system cannot find the path specified`:**

1. فایل ZIP را مستقیماً از داخل مرورگر اجرا نکنید.
2. ابتدا آن را کامل در `Downloads` ذخیره کنید.
3. روی فایل ZIP راست‌کلیک کنید و **Extract All** یا **Extract to...** را بزنید.
4. اگر WinRAR فایل را از یک مسیر موقت باز کرده، WinRAR را ببندید و ZIP را دوباره از محل ذخیره‌شده روی هارد باز کنید.
5. اگر باز هم خطا داشت، ZIP را دوباره دانلود کنید و مطمئن شوید دانلود کامل شده است.

**اگر برنامه به RVC وصل نشد:**

1. مطمئن شوید RVC WebUI در حال اجراست.
2. مطمئن شوید API روی پورت `7897` فعال است.
3. اگر پورت RVC را تغییر داده‌اید، آدرس API داخل برنامه را اصلاح کنید.
4. در Windows Firewall دسترسی برنامه را بررسی کنید.
5. دوباره **Test Connection** را اجرا کنید.

---

## 🇬🇧 English Guide

**DJAR RVC Studio** is a portable Windows desktop controller for a local RVC WebUI/API instance.

### Download

**[Download the latest Portable build from GitHub Actions](https://github.com/ahmadrezahsnz81-stack/REPO1/actions/workflows/build-windows.yml)**

Open the latest successful workflow run, find **Artifacts**, download **DJAR-RVC-Studio-Portable**, save it to a normal local folder, extract it, open the **DJAR RVC Studio** folder, and run:

`DJAR RVC Studio.exe`

The latest workflow uploads the portable folder directly, avoiding a ZIP-inside-a-ZIP package.

### Requirements

- Windows 10 or Windows 11
- RVC WebUI/API running locally
- Default API endpoint: `http://127.0.0.1:7897`

### Build

GitHub Actions automatically builds the portable Windows package on pushes to `main` and on manual workflow runs.

The application is packaged with PyInstaller and does not require Python to be installed separately.

RVC itself remains local on the Windows machine. The desktop application calls the RVC API documented for port `7897`.

---

## Repository

**DJAR RVC Studio — REPO1**

https://github.com/ahmadrezahsnz81-stack/REPO1
