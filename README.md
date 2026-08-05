# AI Video OS — "Cursor for Video Editing"

An AI-native video operating system that directs, not just generates, documentary-style
video from a script. This repo is a deployable scaffold: a FastAPI orchestration backend
running a modular agent pipeline, a Next.js "director" frontend (Script → Storyboard →
Preview → Suggestions → Render), and a Remotion + FFmpeg render engine — wired for
Docker Compose locally and Railway in production.

This is a working skeleton, not a finished unicorn. The hard, defensible IP (the Editor
Agent's taste) is a prompting/fine-tuning problem you'll iterate on for months — the code
below gives it a real home to live in, with real data flowing end to end.

---

## 1. Product thesis

Existing tools (Runway, Pika, LTX Studio, Veo, InVideo, CapCut, Descript) optimize for
**generating clips**. None of them optimize for **editorial judgment** — the thing that
makes MagnatesMedia or Johnny Harris videos watchable is pacing, not pixels: where a cut
lands, when music drops, when a chart earns its 4 seconds on screen.

So the core object in this system is not a "clip." It's a **Scene Graph** — a structured,
editable, re-renderable representation of editorial decisions. The AI's job is to produce
and refine that graph. Rendering is a mechanical last step, not the product.

**Differentiation, one line each:**
- **Runway/Pika/Veo** — clip generators; no concept of a whole video's pacing.
- **LTX Studio** — storyboards clips, but no editorial reasoning layer or scene graph you can query/edit.
- **CapCut/Premiere/Descript** — human-driven timelines; AI is autocomplete, not the director.
- **InVideo/Canva** — templated slideshow logic; can't reason about tension, rhythm, curiosity.

We compete by owning the **editorial decision layer**, and treating rendering as a
pluggable backend (Remotion today; could be swapped for a different engine later without
touching the product).

---

## 2. System architecture

```
                         ┌─────────────────────────┐
                         │        Frontend          │
                         │  Next.js (App Router)    │
                         │  Script / Storyboard /   │
                         │  Preview / Suggestions /  │
                         │  Render                  │
                         └────────────┬─────────────┘
                                      │ REST + WS
                         ┌────────────▼─────────────┐
                         │        Backend            │
                         │  FastAPI + SQLAlchemy     │
                         │  Orchestrator             │
                         └────────────┬─────────────┘
                                      │
        ┌───────────────┬────────────┼────────────┬───────────────┐
        ▼               ▼            ▼            ▼               ▼
  Script Agent   Editor Agent  Storyboard    Visual Agent   Motion/Audio/
  (parse, NER,   (pacing,      Agent (shot   (asset type    Subtitle Agents
  emotion, beats) tension map) list, timing) per shot)
        │               │            │            │               │
        └───────────────┴────────────┴────────────┴───────────────┘
                                      │
                              Scene Graph (Postgres)
                                      │
                         ┌────────────▼─────────────┐
                         │      Render Queue          │
                         │  (Postgres-backed jobs;    │
                         │   swap for Redis/RQ later) │
                         └────────────┬─────────────┘
                                      ▼
                         ┌───────────────────────────┐
                         │      Render Engine          │
                         │  Remotion (React → frames)  │
                         │  + FFmpeg (mux, encode,     │
                         │    audio mastering)         │
                         └───────────────────────────┘
```

### Agent pipeline (matches `backend/app/agents/`)

1. **ScriptAgent** — segments the script into beats, tags entities/topics, scores emotional
   valence + tension per beat, emits a scene list.
2. **EditorAgent** — the taste layer. Consumes the scene list and produces *editorial
   directives* per beat: cut cadence, where tension should rise/fall, where a pause earns
   its silence, where a visual reveal should land. This is the component you'll spend the
   most time tuning (prompt-engineered against reference-channel pacing patterns, never
   against copyrighted footage/branding itself).
3. **StoryboardAgent** — turns directives into a concrete shot list: duration, camera
   move, transition, animation type per shot.
4. **VisualAgent** — per shot, decides asset type (stock, AI image, motion graphic, chart,
   map, timeline, UI mockup, website recording) and asset spec.
5. **MotionAgent** — attaches camera/parallax/zoom/pan/lighting parameters per shot.
6. **AudioAgent** — music cue placement, ducking, SFX, mastering chain parameters.
7. **SubtitleAgent** — caption styling, timing, emphasis/highlight animation.
8. **Orchestrator** — runs the pipeline in order, persists the Scene Graph after each
   stage (so the frontend can show incremental progress and let a user edit mid-pipeline),
   and enqueues a render job at the end.

Each agent is an isolated module with a plain input/output contract (typed Pydantic
models) so you can swap the underlying model (see §4) per agent independently.

---

## 3. Database schema (see `backend/app/models.py`)

- **projects** — script, target platform, length, brand kit ref, status
- **brand_kits** — colors, fonts, logo asset refs
- **voice_profiles** — TTS voice id/provider, style params
- **scenes** — ordered beats per project (script text span, emotion score, tension score)
- **shots** — ordered shots per scene (duration, camera move, transition, asset ref, motion/audio/subtitle params as JSONB)
- **assets** — generated/fetched media (type, provider, uri, metadata)
- **render_jobs** — queue table (status, progress, output uri, error)
- **agent_runs** — audit log of each agent invocation (input hash, output, model used, latency) — this is your future fine-tuning dataset

JSONB columns hold agent-specific parameters so each agent can evolve its schema without
migrations on every iteration; promote a field to a real column once it stabilizes.

---

## 4. AI model recommendations

| Function | Recommendation | Why |
|---|---|---|
| Scene/entity/emotion understanding | Claude (Sonnet-class) | Long-context script reasoning, structured JSON output |
| Editorial reasoning (pacing/tension) | Claude, heavily prompt-engineered + few-shot on your own annotated examples | This is the moat; keep it swappable behind the EditorAgent interface |
| Image generation | Flux / SDXL via API, or Ideogram for text-in-image | Fast iteration, good style control |
| Stock/asset retrieval | Pexels/Storyblocks API + your own vector search over a licensed library | Avoids copyright risk entirely |
| Speech (TTS) | ElevenLabs or Azure Neural TTS | Quality + voice cloning if user provides one |
| Music | Suno API or a licensed stock-music bed library with mood tagging | Licensed music is lower legal risk than pure generation at first |
| Sound effects | Licensed SFX library (Soundstripe/Epidemic) | Same reasoning |
| Motion/camera generation | Deterministic, rule-based (see MotionAgent) informed by LLM-selected motion *style* | Camera math doesn't need an LLM; style selection does |

Keep every model call behind a thin provider interface (`backend/app/agents/providers.py`
stub included) so you can A/B or swap vendors without touching agent logic.

---

## 5. Rendering engine

- **Remotion** renders each shot as a React composition (`render-engine/src/compositions`),
  driven entirely by the Scene Graph JSON — no hardcoded content.
- Backend calls `render-engine/render.js`, which shells out to `npx remotion render`,
  producing an MP4 per project.
- **FFmpeg** does the final pass: audio mixing/ducking, loudness normalization, subtitle
  burn-in (or soft subs), and platform-specific export (9:16 for TikTok/Reels, 16:9 for
  YouTube).
- Render jobs are queued in Postgres (`render_jobs` table) and polled by a worker process;
  swap in Redis/RQ or a proper queue (SQS, Cloud Tasks) once volume justifies it — the
  interface (`enqueue`, `claim_next`, `mark_done`) is already isolated in
  `backend/app/render_queue.py` so the swap doesn't touch calling code.
- Scale path: containerize the render worker separately from the API so you can run N
  render workers behind the same queue (Railway lets you deploy the same repo as multiple
  services with different start commands — see `railway.json`).

---

## 6. Repo layout

```
ai-video-os/
├── backend/                  FastAPI app
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── render_queue.py
│   │   ├── routers/
│   │   │   ├── projects.py
│   │   │   └── render.py
│   │   └── agents/
│   │       ├── providers.py
│   │       ├── orchestrator.py
│   │       ├── script_agent.py
│   │       ├── editor_agent.py
│   │       ├── storyboard_agent.py
│   │       ├── visual_agent.py
│   │       ├── motion_agent.py
│   │       ├── audio_agent.py
│   │       └── subtitle_agent.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                 Next.js app
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── project/[id]/page.tsx
│   ├── package.json
│   ├── Dockerfile
│   └── .env.example
├── render-engine/            Remotion + render script
│   ├── src/index.ts
│   ├── src/compositions/DocumentaryComposition.tsx
│   ├── render.js
│   └── package.json
├── docker-compose.yml
├── railway.json
└── .gitignore
```

---

## 7. Pricing & business model (starting point)

- **Free** — 3 projects/mo, 1080p, watermark
- **Creator** — $39/mo — 30 projects, 4K, no watermark, brand kit
- **Studio** — $149/mo — unlimited projects, priority render, team seats, API access
- **Enterprise** — custom — dedicated render capacity, custom voice/brand training, SSO

Usage-based render minutes as an add-on once volume is meaningful — rendering is your
real marginal cost (GPU/CPU time + model API spend), so keep an eye on cost-per-render
from day one via `agent_runs` + render job duration logging.

## 8. Roadmap: MVP → $100M ARR

1. **MVP (0–3mo)** — Script + EditorAgent + StoryboardAgent producing an editable Scene
   Graph; manual asset upload; Remotion render for 16:9 YouTube only. Validate that the
   *pacing* output is good enough that creators would rather fix AI edits than start blank.
   This is the whole bet — don't build anything else until this is true.
2. **v1 (3–6mo)** — Add VisualAgent (stock + AI image), AudioAgent, SubtitleAgent. Multi-
   platform export. Brand kits. Paid tiers.
3. **v2 (6–12mo)** — Fine-tune EditorAgent on your `agent_runs` dataset + creator feedback
   (accept/reject/edit signals become training data). Team collaboration. API for
   programmatic video generation. Motion graphics library.
4. **Scale (12–24mo)** — Distributed render workers, enterprise voice/brand training,
   marketplace for style templates, usage-based render pricing, SOC2.
5. **$100M ARR path** — This is a volume-and-retention game: land via prosumer creators
   (low CAC, viral output), expand into agencies/media companies (high ACV via API +
   enterprise render SLAs). Retention hinges entirely on EditorAgent quality — treat every
   creator edit-to-AI-output as labeled training data from day one.

---

## 9. Running locally

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
docker compose up --build
```

Frontend: http://localhost:3000 · Backend: http://localhost:8000/docs

## 10. Deploying to Railway

1. Push this repo to GitHub.
2. In Railway: New Project → Deploy from GitHub → select repo.
3. Add a **Postgres** plugin (Railway sets `DATABASE_URL` automatically).
4. Create three services from the same repo, each with its root/start command set via
   `railway.json` (already configured): `backend`, `frontend`, and optionally a separate
   `render-worker` once you split rendering out for scale.
5. Set env vars per service (see each `.env.example`) in the Railway dashboard —
   `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `STOCK_MEDIA_API_KEY`, etc.
6. Deploy. Railway builds each service's Dockerfile automatically.
