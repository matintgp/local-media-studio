# Local Media Studio | استودیوی مدیای لوکال

A local-first, Persian/English media workspace for existing ComfyUI and Wan2GP installations: image, video, speech, music, synchronized ambience, and final clip assembly.

**Status: implementation handoff repository.** This initial commit contains requirements, architecture, sanitized integration recipes and an implementation task. The application is not implemented yet. Model weights, private media, machine configuration and credentials are not included.

## برای شروع در سایت ChatGPT

۱. این ریپو را به محیط کار ابری دارای دسترسی نوشتن به GitHub وصل کنید. مطابق رابط فعلی، مسیر Work → Cloud و انتخاب یا ساخت Environment است؛ در بعضی حساب‌ها این قابلیت با نام Codex نمایش داده می‌شود. صرف فرستادن لینک ریپو در گفت‌وگویی که دسترسی نوشتن ندارد، انتشار کد را تضمین نمی‌کند.

۲. متن [پرامپت آماده](tasks/CHATGPT_TASK.md) را به تسک بدهید. فایل‌های specs و AGENTS.md راهنمای اجرایی کامل‌اند.

۳. تحویل باید یک شاخه و Pull Request، گزارش تست و تصاویر رابط باشد. فعلاً روی main ادغام نکنید.

۴. بعد از تحویل، لینک PR را به دستیار محلی بدهید تا کد را بازبینی، روی ویندوز و GPU واقعی تست و سپس اجرا کند. پایان تسک ابری به معنی تأیید تولید واقعی مدل‌ها روی رایانهٔ شخصی نیست.

## Handoff map

- [Implementation task](tasks/CHATGPT_TASK.md): copy this into the cloud coding task.
- [Product and acceptance specification](specs/PRODUCT.md)
- [Architecture and decisions](specs/ARCHITECTURE.md)
- [Engine integration contracts](specs/INTEGRATIONS.md)
- [Safety and storage boundaries](specs/SAFETY.md)
- [Visual and interaction brief](specs/DESIGN.md)
- [Test and local review gates](specs/ACCEPTANCE.md)
- [Windows deployment handoff](docs/LOCAL_HANDOFF.md)
- [Public configuration example](config/studio.example.json)
- [Sanitized recipes](examples/recipes/)

## Constraints

- Target: Windows, one NVIDIA GPU with 8 GB VRAM, 32 GB system RAM. Cloud development must also work on CPU-only Linux.
- Existing engines remain separate; do not install Torch, weights or another ComfyUI/WanGP into this repository.
- New application data, caches and output go to a configurable B-drive root on the target machine. Never silently fall back to C.
- No new model downloads, package upgrades in engine environments, tunnels or public deployment.
- Build and test against an explicitly labelled mock engine in the cloud. Real engine adapters are required, with transport-level tests; on-device generation is a later integration gate.
- Optional chat/provider integration is an extension point. API credentials and a local language model are not required for the first release.

## Proposed implementation stack

React + TypeScript + Vite frontend; FastAPI backend; SQLite durable state; FFmpeg final assembly. Keep dependencies small and locked. No Redis, Docker, separate database server or GPU libraries are needed. The implementer must add exact install, test, build and Windows run commands to this README when code exists.

## Scope and licenses

MIT covers this repository's original code and documentation. It does not grant rights to third-party models, voices, fonts, music, engines or user media. Those components retain their respective licenses.
