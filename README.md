# 🎬 Petstar (`Pawsport.ai`) — 24-Hour Viral Pet Persona & Custom Merch Studio

Production-ready frontend studio portal, Stripe-compliant 3-photo intake funnel, 4-minute AI fulfillment server (`gemini-3.8-flash` Vision + `gemini-nano-banana-2.1` Poster Engine + Printify/Gelato Auto-Mockups), and GitHub REST API (`2026-03-10`) Organization Repository deployer.

Blueprint Source: [`https://www.madethis.com/business/petstar-hp5`](https://www.madethis.com/business/petstar-hp5)

---

## Project Structure

- [`index.html`](./index.html) — Complete standalone web application containing:
  1. **Pawsport Studio (`🎬 Pawsport Studio` tab)**:
     - Interactive **Real Guilty Pet Photo vs. AI Movie Poster Split Stage** with native theatrical poster typography overlay.
     - **15-Sec 9:16 Viral Movie Trailer Player** with synthesized “Epic Movie Trailer Guy” voiceover, live timed captions (`0:00–0:03`, `0:03–0:10`, `0:10–0:15`), and automatic photo-to-poster reveal sweep.
     - **Brutal Bio Roast** banner + **Official Holographic "Pawsport Pet ID" Card** (Serial #, Secret Agent Codename, Threat Level, Flux PuLID Fur/Collar Lock, and 3 Indicted Domestic Felonies).
     - **3 Selectable High-Res Movie Poster Themes** (`Poster 1: Pixar Animated Heist`, `Poster 2: IMAX Action Blockbuster`, `Poster 3: Prestige Detective Noir`).
     - **1-Click Custom Merch Store (Printify / Gelato Auto-Mockup)** — Framed 16x20" Gallery Canvas (`$49`), Heavyweight Studio Hoodie (`$59`), 15oz Cinema Gloss Mug (`$24`), and Organic Heavy Canvas Dog-Park Tote (`$29`) dynamically mocked up with the active pet poster.
  2. **Cast My Pet (`+ Cast My Pet ($9)` tab)**:
     - Complete **Tally.so + Stripe Compliant Intake & Checkout Funnel** with live photo upload preview, 3 personality traits input, conditional **Node A (`$9` Make My Pet Famous — $10 off TikTok opt-in)** vs. **Node B (`$24` Private VIP Bundle)** pricing, and `+$39` 1-Click Framed Canvas order bump.
  3. **4-Min Map & GitHub API (`⚙️ 4-Min Map & GitHub API` tab)**:
     - Complete **4-Minute AI Fulfillment Map**, **Revenue & Unit Economics Map**, **30-Day Launch Roadmap**, and live **GitHub REST API (`2026-03-10`) `POST /orgs/{org}/repos` Repository Creator**.
- [`server.py`](./server.py) — Live Python AI server on port `8096` serving `POST /api/cast`, `POST /api/tally-webhook`, `POST /api/github/create-org-repo`, and `GET /api/orders`.
- [`scripts/create_github_org_repo.py`](./scripts/create_github_org_repo.py) — Standalone CLI & SDK module for GitHub REST API (`apiVersion=2026-03-10`) `POST /orgs/{org}/repos`.
- [`pipeline/claude_vision_prompt.json`](./pipeline/claude_vision_prompt.json) — Structured JSON system prompt for Minute 0:30 Vision + Flux PuLID + Printify pipeline.
- [`pipeline/make_blueprint.md`](./pipeline/make_blueprint.md) — Full Business Strategy & Viral Ecosystem Map reference.
- [`assets/logo.svg`](./assets/logo.svg) — Custom vector SVG mark for Pawsport.ai / Petstar.

---

## Quick Start (Live AI Server on Port 8096)

```bash
/Users/haze/.gemini/antigravity/scratch/gemini-live-voice-agent/.venv/bin/python /Users/haze/.gemini/antigravity/scratch/petstar/server.py
```

Then open:
- **Live Studio & Intake Funnel:** `http://localhost:8096`
- **Demo Star 1 (Barnaby — Golden Retriever):** `http://localhost:8096/?order=paw849201`
- **Demo Star 2 (Mochi — French Bulldog):** `http://localhost:8096/?order=paw910442`
- **Demo Star 3 (Luna — Tuxedo Cat):** `http://localhost:8096/?order=paw773190`

---

## Create GitHub Organization Repository (`apiVersion=2026-03-10`)

```bash
/Users/haze/.gemini/antigravity/scratch/gemini-live-voice-agent/.venv/bin/python \
  /Users/haze/.gemini/antigravity/scratch/petstar/scripts/create_github_org_repo.py \
  --org YOUR_ORG_NAME \
  --name petstar-pawsport-ai \
  --fallback-user
```
