# content-ai — Plan

Daily 20–30s AI explainer shorts for **Instagram Reels** and **YouTube Shorts**, produced end to end by Claude.
Starting from zero (no accounts yet). Last updated: 2026-10-20.

## Decisions so far

| Topic | Decision |
|---|---|
| Format | 20–30s vertical video, 1080×1920, 9:16 |
| Niche | AI: trending topics + trending GitHub repos |
| Schedule | Claude scheduled task, **9:00am daily, `CRON_TZ=Australia/Melbourne`** |
| Budget | **$0** — Claude subscription only. No paid APIs. Open-source tools, free official APIs. |
| Voice | **Original "cute golden retriever" character voice** (NOT the user's voice — changed 2026-10-20). Generated with **Chatterbox** (Resemble AI, MIT) on CPU, from a permissively licensed reference speaker + expressive settings + pitch shift. Never imitate a real person or existing cartoon character. Fallback: Kokoro (Apache 2.0) preset voices + pitch shift. Avoid F5-TTS / XTTS (non-commercial model licenses). |
| Visual style | **Motion graphics**, written as HTML/SVG/GSAP code per scene (approach inspired by `yihui-dev/awesome-opus5-5-videos`) |
| Character | **Joey**, a golden retriever mascot, voice/personality: **goofy best friend, male**, consistent across all explainers. Built as an SVG rig animated with GSAP (consistency for free). Lip-synced via Rhubarb. |
| Sandbox | **Separate sandbox accounts**: 2nd YouTube channel (private/unlisted uploads) + 2nd Instagram Professional account. Note: Instagram Professional accounts **cannot be private** (API requires Professional) → sandbox IG is public but obscure (no hashtags, no followers), posts deleted after verification. |
| Approval | **Human approval step: YES** for the first weeks. Claude emails sandbox links (Gmail MCP); user replies "ship" → publish to main. |
| Music | Royalty-free only (Pixabay / YouTube Audio Library), curated one-time pack of ~20 tracks stored in repo; Claude picks by mood. No trending IG audio (not possible via API). |
| Publishing | Official APIs via our own scripts (no third-party MCP holding tokens): YouTube Data API v3, Instagram API with Instagram Login |
| Inspiration | User sends Instagram links; Claude tries to fetch (often login-walled; yt-dlp may work). Fallback: screenshot/description. Confirmed: profile fetch returned HTTP 429. Reference creator: **@vaibhavsisinty** (fast-paced AI tools/news reels). |

## Pipeline

1. **Research** (9am Melbourne) — WebSearch/WebFetch, HN Algolia API, GitHub Trending, Hugging Face + arXiv APIs → commit `ideas/YYYY-MM-DD.md` (3 ranked ideas + sources).
2. **Script** — top idea → 60–80 word script (hook in first 2s), captions, shot list, music mood. Committed.
3. **Voice** — `scripts/tts.py` with user's reference voice (Chatterbox).
4. **Timing** — faster-whisper word timestamps (captions) + Rhubarb mouth shapes (lip sync).
5. **Render** — HTML/GSAP scenes + retriever rig → Playwright (preinstalled Chromium) frame capture → ffmpeg mux voice + music.
6. **QA** — extract frames, check text safe-areas, timing, audio levels, facts vs sources.
7. **Archive** — upload MP4 + script + thumbnail to Google Drive `content-ai/YYYY-MM-DD/` (Drive MCP; rclone fallback).
8. **Sandbox publish** — sandbox YouTube (private) + sandbox Instagram (private account). Verify live posts.
9. **Approval** — email user the links; wait for "ship".
10. **Main publish** — upload the same file to main YouTube + Instagram.

## Toolchain (all free)

| Need | Tool | Status |
|---|---|---|
| Scheduling | Claude scheduled tasks | available |
| Voice cloning | Chatterbox (CPU) | **in setup** |
| Captions timing | faster-whisper (MIT) | todo |
| Lip sync | Rhubarb Lip Sync (MIT) | todo |
| Render | Playwright + Chromium, ffmpeg | available in container |
| Character design | SVG/GSAP (Figma MCP optional) | todo |
| Drive | Google Drive MCP / rclone | connected, large-file upload untested |
| Approval | Gmail MCP | connected |
| Publish | YouTube Data API v3, Instagram API | needs accounts |

## Accounts created

- Gmail: askjoey.ai@gmail.com
- Instagram (main): askjoey.ai

## User to-do (not blocking POCs)

- [ ] Pick the retriever's voice from generated candidates
- [ ] Create main + sandbox YouTube channels (Brand Accounts under one Google account is fine)
- [ ] Switch askjoey.ai to Professional (Creator); create sandbox Instagram Professional account
- [ ] Google Cloud project: enable YouTube Data API v3, OAuth consent; **apply for API audit early** (unaudited projects can only upload as private)
- [ ] Meta developer app with Instagram API (Instagram Login) + content publishing permission
- [ ] Download ~20 royalty-free music tracks (check each license)
- [ ] Add API secrets + network allowlist to the Claude environment (never commit secrets)

## POC order

1. **Voice** — Chatterbox on CPU: install, generate 3–4 cute retriever voice candidates, user picks one, lock settings into `voice/`. ← *current*
2. **Character + render** — golden retriever SVG rig lip-syncing to voice → 9:16 MP4.
3. **Research → script** — one day's ideas + script committed.
4. **Feasibility checks** — Drive large-file upload, Instagram link fetch.
5. **Publishing** — after accounts exist.

## Open questions

- Handle (name the dog: Joey; e.g. joey.ai / joeythegolden / askjoey.ai — check availability) and language.
- Content mix: news vs tutorials vs "repo of the day".
- Joey's art style + visual details.

## Notes / risks

- Containers are ephemeral: `scripts/setup_voice.sh` must reinstall deps + weights each fresh session (setup script / SessionStart hook later).
- Chatterbox CPU speed is unverified — if too slow, consider shorter scripts or OpenVoice v2.
- Credit creators when using inspiration; never repost others' videos.
