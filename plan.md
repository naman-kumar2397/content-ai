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
| Voice | Chatterbox (CPU), preset `voice/joey.json` | done |
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

## Windsor.ai (connected 2026-10-20, TRIAL plan — paid after trial, conflicts with $0 budget)

- Instagram `askjoey.ai` (id 17841450494293781): **can publish Reels** via `create_video_post` (needs a *publicly accessible* MP4 URL), stories, image posts, comments.
- YouTube `askjoey.ai@gmail.com`: **read-only analytics** — no upload. YouTube publishing still needs YouTube Data API v3.
- Open: public video hosting for IG (Drive links aren't direct MP4); decide Windsor vs direct Instagram API before trial ends.

## User to-do (not blocking POCs)

- [x] Joey's voice chosen: B4 → `voice/joey.json` (Chatterbox, ref `voice/joey_ref.wav`, exaggeration 0.6, cfg 0.5, no pitch shift, seed 42). Use `scripts/tts.py --voice joey`.
- [ ] Create main + sandbox YouTube channels (Brand Accounts under one Google account is fine)
- [ ] Switch askjoey.ai to Professional (Creator); create sandbox Instagram Professional account
- [ ] Google Cloud project: enable YouTube Data API v3, OAuth consent; **apply for API audit early** (unaudited projects can only upload as private)
- [ ] Meta developer app with Instagram API (Instagram Login) + content publishing permission
- [ ] Download ~20 royalty-free music tracks (check each license)
- [ ] Add API secrets + network allowlist to the Claude environment (never commit secrets)

## POC order

1. **Voice** — ✅ done. Joey = Chatterbox preset `voice/joey.json`. (~6.5× real-time on CPU → ~3 min for a 25s script.)
2. **Character + render** — (first 3 SVG styles rejected by user 2026-10-20) Joey rig lip-syncing to voice → 9:16 MP4. ← *next*
3. **Research → script** — one day's ideas + script committed.
4. **Feasibility checks** — Drive large-file upload, Instagram link fetch.
5. **Publishing** — after accounts exist.

## Open questions

- Handle (name the dog: Joey; e.g. joey.ai / joeythegolden / askjoey.ai — check availability) and language.
- Content mix: news vs tutorials vs "repo of the day".
- Joey's art style + framing + signature item.

## Style reference (user likes, 2026-10-20)

- @canwebuildthis reel DePGWqgThxq (19K followers): **low-poly 3D character**, Blender-style render, warm cinematic key light, blurred night-city window background (depth of field), simple deadpan face (dot eyes, tiny mouth), white bold captions in dark rounded box at top. Format: **comedic skit — character talking to "Claude"**. Caption ends with an engagement question.
- @canwebuildthis reel Det_3TmTAsF — **series format** "EXPLAIN IT LIKE I'M FIVE · PART 1 — What's an API?": daytime office set (window, city, bookshelf), **whiteboard** with stick-figure diagram (YOU → ? → KITCHEN), **technical words crossed out in red** ("no technical words allowed"), the sidekick holds a pointer stick. Cover frame = big bold title (white + accent colour) + small pill label for the series/part. Caption ends with a question picking the next episode ("which tech word should Claude explain next?").
- **Our adaptation:** recurring series **"Explain it like I'm a dog 🐶"** — Joey asks, the Ball explains with a whiteboard + dog-world analogies (API = playing fetch, etc.). Numbered parts; ask audience for next topic. Cover frame with series pill + big title.
- Tools note: Instagram reels can't be downloaded from the container (HTTP 429). Agent-Reach needs a desktop Chrome login → not usable here. Working method: embed page (`/reel/<id>/embed/captioned/`) gives caption + cover frames.
- Implication: Joey as a **low-poly 3D golden retriever** rendered in **Blender** (free, scriptable via Python, CPU render). Risk: CPU render time per frame — POC needed.

## Hugsy — second character (decided 2026-10-20, replaces the tennis ball)

- **Hugsy**, a **penguin plush toy** — nod to Joey's stuffed penguin in *Friends* (Joey's name is also from Friends). Our own design, not a replica of the show prop; no catchphrases or show clips.
- Personality: deadpan, sarcastic know-it-all (default unless user changes it). Teacher role in the "Explain it like I'm a dog" series (flipper points at whiteboard).
- Low-poly plush in the same style as Joey; separate flippers, eyes, beak for gestures/blinks.

## Joey — based on the user's real dog

Character is modelled on the user's own golden retriever, Joey (channel named after him). Key traits from reference photo:
- Pale cream / light golden coat (lighter than typical goldens), slightly darker golden ears
- Broad, round head; big fluffy chest ruff; cream-white legs and paws
- Large dark brown-black nose; round dark eyes with a soft, sweet expression
- Signature look: big open-mouth smile with pink tongue


## Notes / risks

- Containers are ephemeral: `scripts/setup_voice.sh` must reinstall deps + weights each fresh session (setup script / SessionStart hook later).
- Chatterbox CPU speed is unverified — if too slow, consider shorter scripts or OpenVoice v2.
- Credit creators when using inspiration; never repost others' videos.
