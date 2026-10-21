# Running Local Media Studio

First locally tested version, kept on a feature branch. GPU generation runs in the existing engines. The app installs no models, GPU packages or browsers.

## Windows setup

Prerequisites: installed Python 3.12, uv, Node/npm and FFmpeg/ffprobe. Use an approved data volume; do not install into an engine environment.

```powershell
New-Item -ItemType Directory -Path 'B:\MediaStudio' -Force
.\scripts\install-windows.ps1 -DataRoot 'B:\MediaStudio'
```

This explicitly installs the app-only .venv and builds the frontend using lockfiles. Caches/temp stay under the selected data root. `scripts/check-windows.ps1` is a read-only prerequisite check.

Create an ignored `studio.local.json` in the data root, replacing these generic engine paths with actual approved roots:

```json
{
  "STUDIO_COMFY_OUTPUT_ROOT": "B:/ExistingComfy/output",
  "STUDIO_WAN_OUTPUT_ROOT": "B:/ExistingWan/outputs",
  "STUDIO_COMFY_URL": "http://127.0.0.1:8188",
  "STUDIO_WAN_URL": "http://127.0.0.1:7866/mcp",
  "STUDIO_RESERVE_GIB": "60"
}
```

Use a stricter reserve if an existing storage budget requires it. STUDIO_FFMPEG/STUDIO_FFPROBE may specify existing executables. Never commit this configuration, databases, sessions or media.

```powershell
# Start both existing engines separately in Pinokio, then:
.\scripts\run-windows.ps1 -Mode real -DataRoot 'B:\MediaStudio'
# Synthetic CPU-only demonstration:
.\scripts\run-windows.ps1 -Mode mock -DataRoot 'B:\MediaStudio'
```

Open http://127.0.0.1:8787. Use one backend worker per data root. A second runner is rejected by the OS lock. Stop with Ctrl+C or the local Pinokio entry. Stopping the app does not cancel native engine jobs; reconnect with the same data root to track them.

## استفاده

۱. پروژه بسازید. در «ساخت مدیا» نوع خروجی را انتخاب، متن و ورودی را وارد و به صف اضافه کنید. موتور و مدل باید از قبل نصب باشند.

۲. در کتابخانه، تصویر را برای ویدیو یا ویدیو را برای صدای محیط دوباره استفاده کنید. Import یک نسخه در داده‌های اپ می‌سازد؛ خروجی خود موتورها با مرجع ثبت می‌شود و کپی حجیم اضافه ندارد.

۳. در گردش‌کار، مراحل را مرتب کنید. تصویر پیش از ویدیو و ویدیو پیش از صدای محیط، ورودی مرحلهٔ بعد را تأمین می‌کند. اجرای مجدد مراحل موفق را حفظ می‌کند؛ وضعیت هر کار در صف دیده می‌شود.

۴. در «تدوین نهایی»، نماها را به ترتیب اضافه و IN/OUT را بر حسب ثانیه تعیین کنید. مسیرهای گفتار، موسیقی و صدای محیط را اضافه کنید. Gain ضریب شدت صداست؛ 1 یعنی بدون تغییر. Offset محل شروع صدا در کلیپ نهایی است. Fade تدریجی است و ducking بستر صدا را هنگام گفتار آرام می‌کند. برای نگه‌داشتن صدای ویدیوی ورودی، خود ویدیو را به‌عنوان مسیر ambience نیز انتخاب کنید.

۵. زیرنویس SRT/VTT اختیاری وارد کنید. زیرنویس در MP4 قابل انتخاب است؛ روی تصویر سوزانده نمی‌شود. Export به صف CPU می‌رود و نتیجه در کتابخانه می‌آید؛ وضعیت آن در Composer دیده می‌شود. مجموع مدت نماها، مدت نهایی است؛ گفتار بلندتر را پیش از خروجی بازبینی کنید.

۶. زبان، متن‌ها و پیش‌نویس تدوین هر پروژه در همان مرورگر ذخیره می‌شوند. پروژه‌ها، دارایی‌ها، صف و لینک مراحل در SQLite ماندگارند. فایل‌های اصلی و پایگاه داده را برای انتقال پروژه حفظ کنید؛ localStorage به همان مرورگر وابسته است.

اگر ارتباط قطع شد، کار تأییدنشده تکرار نمی‌شود. unknown ممکن است صف را نگه دارد تا نتیجه بازیابی شود. فقط پس از بررسی دستی موتور و تأیید خالی بودن هر دو صف از «آزادسازی پس از بررسی» استفاده کنید؛ نتیجهٔ مبهم در تاریخچه باقی می‌ماند و هیچ کاری دوباره ارسال یا لغو نمی‌شود.

## Verification

```powershell
uv pip install --no-cache --python 'B:\MediaStudio\.venv\Scripts\python.exe' -r backend/requirements-dev.lock
$env:PYTHONPATH = "$PWD\backend"
$env:STUDIO_DATA_ROOT = 'B:\MediaStudio'
& 'B:\MediaStudio\.venv\Scripts\python.exe' -m pytest -q backend/tests
cd frontend
npm ci --ignore-scripts
npm run typecheck
npm run build
```

Run browser tests against a separate mock server/data root: STUDIO_E2E_URL selects the origin; STUDIO_BROWSER_CHANNEL=msedge uses installed Edge without downloading Chromium. CI installs Chromium explicitly. Never aim the mock E2E test at real mode. See docs/LOCAL_REVIEW.md for actual results.

## Limits

One user, loopback-only, engines managed separately. Direct engine UI jobs can race an admission check; the app pauses further admission when conflicts are observed. Composer is a clip/track form with previews, not a mixed live timeline. Workflows support ordered earlier-step binding, not a general node editor. No automatic transcription, lip sync, chatbot or API provider is enabled. The provider interface is reserved for future work. Generated video artifacts and Persian pronunciation need human review.


## تایم‌لاین و دستیار

کنترل‌های تعاملی تدوین و اتصال اختیاری Ollama / OpenAI اضافه شده‌اند. برای روش استفاده، محدودیت پیش‌نمایش و نگهداری کلید، [راهنمای تایم‌لاین و دستیار](docs/TIMELINE_ASSISTANT.md) را ببینید. اتصال زندهٔ چت‌بات به مدل موجود یا کلید API شما نیاز دارد.
