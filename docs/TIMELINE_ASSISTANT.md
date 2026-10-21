# Interactive editing and optional assistant

The Composer now includes a graphical timeline backed by the same project shot
and audio-track data used by FFmpeg export. Drag shots to change their order;
drag the square bracket handles to change source in/out points. Drag an audio
block to change its start offset. Focus these controls and use Left/Right for
keyboard editing (0.1 seconds for trim/offset). Zoom changes only the display.
The playhead supports seeking and sequential video/audio playback. Drafts are
saved per project in this browser; the existing numeric inspector remains usable.

The editing preview is approximate: browser volume is capped at unity and it
does not reproduce FFmpeg's sidechain compressor, limiter or embedded subtitles.
The actual MP4 export remains the authoritative mixed preview. Video source audio
is silent unless explicitly added as an audio track. This is a sequential editor,
not a multi-layer video compositor or a frame-accurate NLE.

## اتصال دستیار

در «دستیار تولید»، اتصال را باز کنید. یکی از این دو روش را انتخاب کنید:

- **Ollama:** سرویس از قبل اجرا باشد؛ نشانی loopback و نام دقیق مدل نصب‌شده را
  وارد کنید و «ذخیره اتصال» بزنید. اپ مدلی دانلود یا سرویسی راه‌اندازی نمی‌کند.
  درخواست با `num_gpu=0` و `keep_alive=0` ارسال می‌شود تا GPU برای مدیا بماند.
  اجرای CPU ممکن است کند باشد؛ مهلت هر درخواست ۱۸۰ ثانیه است.
- **OpenAI API:** نشانی `https://api.openai.com/v1`، نام مدل سازگار با Chat
  Completions و JSON mode، و کلید API خودتان را وارد کنید. پیش از ارسال، اجازهٔ
  ارسال متن گفت‌وگو را فعال کنید. فایل‌های مدیا به دستیار فرستاده نمی‌شوند.

API keys are kept in backend process memory only; after restart re-enter the key
or supply `STUDIO_ASSISTANT_API_KEY` to the backend process. The public config never
returns the key. Non-secret settings live in `assistant.local.json` in the data
root. Chat text persists in this browser's local storage per project. It is sent
only to the explicitly configured provider; no background model/provider calls.
Third-party remote hosts and arbitrary URL proxies are intentionally unsupported.

دستیار می‌تواند دربارهٔ ایده‌ها پاسخ بدهد یا برنامه‌ای تا هشت مرحله پیشنهاد کند.
متن مراحل را بازبینی و ویرایش کنید، سپس «تأیید و افزودن برنامه به صف» را بزنید.
این کار گردش‌کار معمولی می‌سازد و همان صف پایدار تولید آن را اجرا می‌کند.
خود مدل اجازهٔ اجرای دستور، نصب مدل، تغییر تنظیمات یا دسترسی به فایل ندارد.
ابعاد و مدت از پیش‌تنظیم‌های فعلی می‌آیند؛ دستیار تدوین/اکسپورت را خودکار نمی‌کند.

## Verification scope

Provider tests use synthetic HTTP responses, checking remote consent, backend-only
keys, endpoint restrictions, local CPU settings, invalid plans and zero automatic
job submission. Browser tests mock only the assistant response, then exercise the
real application workflow queue in labelled CPU demo mode. They do not prove a
live LLM answer. A real assistant requires an available installed Ollama model or
an owner's API key; no model/key is bundled.

Protocols: [Ollama chat](https://docs.ollama.com/api/chat) and
[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat).
