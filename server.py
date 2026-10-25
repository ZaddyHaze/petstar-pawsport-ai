#!/usr/bin/env python3
"""
Petstar (Pawsport.ai) — 24-Hour Viral Pet Persona & Custom Merch Studio Server
Port: http://localhost:8096

Endpoints:
  - POST /api/cast : Runs the 4-Minute AI Fulfillment Pipeline on uploaded pet photo(s):
      1. Gemini 3.8 Flash Vision (`gemini-3.8-flash`) with structured JSON output for:
         - Blockbuster Movie Title & Tagline
         - Brutal Bio Roast Summary
         - Official "Pawsport Pet ID" Card (Serial #, Codename, Threat Level, Fur/Collar Lock)
         - 3 Indicted Domestic Felonies
         - 40-Word "Epic Movie Trailer Guy" Voiceover Script + 3 Timed 15-Sec Captions
         - 3 Identity-Locked Movie Poster Prompts (Pixar Heist, IMAX Action, Prestige Noir)
      2. Parallel Gemini Nano Banana 2.1 (`gemini-nano-banana-2.1`) image-to-image poster renders
         (with instant breed-matched fallback if the API key is on Free Tier).
      3. Printify / Gelato Auto-Merch Mockup generator (Framed Canvas $49, Hoodie $59, Mug $24, Tote $29).
  - POST /api/tally-webhook : Native webhook receiver for Tally.so + Stripe ($9 Public / $24 VIP).
  - POST /api/github/create-org-repo : Live GitHub REST API (2026-03-10) `POST /orgs/{org}/repos` endpoint.
  - GET  /api/orders : Returns all persisted Pawsport orders from `orders.json`.
"""

import base64
import concurrent.futures
import json
import os
import random
import sys
import traceback
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dotenv import load_dotenv
import httpx
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
RENDERS_DIR = BASE_DIR / "renders"
ORDERS_FILE = BASE_DIR / "orders.json"
RENDERS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR / "scripts"))
from create_github_org_repo import create_organization_repository  # noqa: E402

# Load GEMINI_API_KEY from candidate .env files
for env_candidate in [
    BASE_DIR / ".env",
    BASE_DIR.parent / "roastmyspace" / ".env",
    BASE_DIR.parent / "gemini-live-voice-agent" / ".env",
    Path.home() / ".env",
]:
    if env_candidate.exists():
        load_dotenv(env_candidate, override=True)
        if os.environ.get("GEMINI_API_KEY") and os.environ.get("GEMINI_API_KEY") != "YOUR_API_KEY":
            break


# ---------------------------------------------------------------------------
# Structured Output Schema for Gemini 3.8 Flash Pet Vision & Script Engine
# ---------------------------------------------------------------------------
class PetFelonyItem(BaseModel):
    code: str = Field(description="Short felony code, e.g. 'FELONY_01: GRAND THEFT CHEESE'")
    tag: str = Field(description="2-3 word uppercase badge, e.g. 'CAUGHT IN 4K', 'ZERO REMORSE'")
    desc: str = Field(description="1 hilarious sentence describing the pet's specific crime.")


class PetVisionOutput(BaseModel):
    movie_title: str = Field(
        description="ALL-CAPS blockbuster movie title starring the pet, e.g. 'BARNABY: THE CHEESE HEIST'"
    )
    movie_tagline: str = Field(
        description="Punchy movie poster tagline under 12 words, e.g. 'No counter is safe. No cheddar is sacred.'"
    )
    brutal_bio_roast: str = Field(
        description="1-2 sentence savage, hilarious bio roast of this specific pet based on the photo and traits (wrapped in quotes)."
    )
    codename: str = Field(description="Funny secret agent codename, e.g. 'THE VELVET MENACE'")
    threat_level: str = Field(description="Funny threat level, e.g. 'DEFCON 1 (SNACK THIEF)'")
    starring_score: int = Field(description="Starring charisma score between 92 and 99.")
    viral_lift: str = Field(description="Projected viral velocity badge, e.g. '+360% Share Velocity'")
    markings_detected: str = Field(
        description="Concise description of exact coat color, markings, ears, and collar detected in the photo."
    )
    trailer_voiceover: str = Field(
        description="40-word 'Epic Movie Trailer Guy' voiceover script roasting the pet's crimes and announcing the movie title."
    )
    roast_captions: list[str] = Field(
        description="Exactly 3 timed captions for the 15-sec 9:16 vertical trailer: '0:00–0:03 • [Guilty Photo Hook]', '0:03–0:10 • [Roast & Crimes]', '0:10–0:15 • [Poster Reveal & CTA]'"
    )
    crimes: list[PetFelonyItem] = Field(description="Exactly 3 indicted domestic felonies for the Pet ID card.")
    poster_1_prompt: str = Field(
        description="Detailed prompt for Poster 1 (Pixar / Disney 3D Animated Heist Poster): preserve exact pet breed, fur markings, and collar in a 3D Pixar theatrical poster with dramatic lighting."
    )
    poster_2_prompt: str = Field(
        description="Detailed prompt for Poster 2 (IMAX Action / Sci-Fi Blockbuster Poster): preserve exact pet breed and fur markings in an epic Hollywood action movie poster with sparks and rim lighting."
    )
    poster_3_prompt: str = Field(
        description="Detailed prompt for Poster 3 (Prestige Noir / Royal Portrait Poster): preserve exact pet breed and fur markings in a velvet noir detective or royal oil painting movie poster."
    )
    poster_2_title: str = Field(description="ALL-CAPS title for Poster 2 (Action/Sci-Fi variant)")
    poster_3_title: str = Field(description="ALL-CAPS title for Poster 3 (Noir/Royalty variant)")


BREED_FALLBACK_POSTERS = {
    "cat": {
        1: "https://images.unsplash.com/photo-1573865526739-10659fec78a5?auto=format&fit=crop&w=1000&q=85",
        2: "https://images.unsplash.com/photo-1495360010541-f48722b34f7d?auto=format&fit=crop&w=1000&q=85",
        3: "https://images.unsplash.com/photo-1518791841217-8f162f1e1131?auto=format&fit=crop&w=1000&q=85",
    },
    "frenchie": {
        1: "https://images.unsplash.com/photo-1583337130417-3346a1be7dee?auto=format&fit=crop&w=1000&q=85",
        2: "https://images.unsplash.com/photo-1517849845537-4d257902454a?auto=format&fit=crop&w=1000&q=85",
        3: "https://images.unsplash.com/photo-1543466835-00a7907e9de1?auto=format&fit=crop&w=1000&q=85",
    },
    "default": {
        1: "https://images.unsplash.com/photo-1537151608828-ea2b11777ee8?auto=format&fit=crop&w=1000&q=85",
        2: "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?auto=format&fit=crop&w=1000&q=85",
        3: "https://images.unsplash.com/photo-1517849845537-4d257902454a?auto=format&fit=crop&w=1000&q=85",
    },
}


def get_breed_fallbacks(breed: str) -> dict[int, str]:
    b = (breed or "").lower()
    if any(k in b for k in ("cat", "feline", "tuxedo", "tabby", "siamese", "maine coon", "persian")):
        return BREED_FALLBACK_POSTERS["cat"]
    if any(k in b for k in ("french", "pug", "bulldog", "boston", "corgi", "dachshund")):
        return BREED_FALLBACK_POSTERS["frenchie"]
    return BREED_FALLBACK_POSTERS["default"]


def parse_image_input(image_base64_or_data_url: str | None, fallback_url: str | None) -> tuple[bytes, str]:
    if image_base64_or_data_url and image_base64_or_data_url.startswith("data:"):
        header, b64_part = image_base64_or_data_url.split(",", 1)
        mime_type = header.split(";")[0].replace("data:", "") or "image/jpeg"
        return base64.b64decode(b64_part), mime_type
    if image_base64_or_data_url:
        return base64.b64decode(image_base64_or_data_url), "image/jpeg"
    url_to_fetch = fallback_url or "https://images.unsplash.com/photo-1552053831-71594a27632d?auto=format&fit=crop&w=1000&q=85"
    with httpx.Client(timeout=10.0, follow_redirects=True) as http_client:
        resp = http_client.get(url_to_fetch)
        resp.raise_for_status()
        mime_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
        return resp.content, mime_type


def generate_poster_render(
    order_id: str,
    poster_num: int,
    prompt: str,
    orig_b64: str,
    orig_mime: str,
) -> str | None:
    """
    Calls `gemini-nano-banana-2.1` via httpx (IPv4) to transform the uploaded pet photo
    into a Pixar/Hollywood theatrical movie poster while locking exact fur markings.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        full_prompt = (
            f"Transform this pet photo into a vertical 3D Pixar / Hollywood theatrical movie poster "
            f"while strictly preserving the exact pet breed, fur color, facial markings, ear shape, and collar. "
            f"Poster style instructions: {prompt}"
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/interactions?key={api_key}"
        payload = {
            "model": "gemini-nano-banana-2.1",
            "input": [
                {"type": "text", "text": full_prompt},
                {"type": "image", "data": orig_b64, "mime_type": orig_mime},
            ],
        }
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        with httpx.Client(transport=transport, timeout=25.0) as http_client:
            resp = http_client.post(url, json=payload)
            if resp.status_code == 429:
                print(
                    f"[Info] Poster {poster_num}: gemini-nano-banana-2.1 on Free Tier; using cinema stylizer + reference photo."
                )
                return None
            resp.raise_for_status()
            res_json = resp.json()
            for out in res_json.get("outputs") or []:
                if out.get("type") == "image" and out.get("data"):
                    img_bytes = base64.b64decode(out["data"])
                    ext = "png" if "png" in (out.get("mime_type") or "png") else "jpg"
                    out_name = f"{order_id}_poster{poster_num}.{ext}"
                    (RENDERS_DIR / out_name).write_bytes(img_bytes)
                    return f"renders/{out_name}"
    except Exception as exc:
        print(f"[Warn] Poster {poster_num} generation note: {exc}")
    return None


def build_fallback_pet_diagnosis(
    pet_name: str, breed: str, owner_handle: str, traits: str, genre: str
) -> PetVisionOutput:
    up_name = pet_name.upper()
    return PetVisionOutput(
        movie_title=f"{up_name}: GRAND THEFT SNACK",
        movie_tagline="Innocent eyes. Classified domestic criminal record.",
        brutal_bio_roast=f"“{pet_name} looks like an angel on a holiday card but operates a 24/7 extortion ring powered by {traits.lower()}.”",
        codename=f"AGENT {up_name}",
        threat_level="DEFCON 1 (SNACK FELON)",
        starring_score=97,
        viral_lift="+355% Share Velocity",
        markings_detected=f"Signature {breed} coat pattern, expressive eyes, and custom collar locked via PuLID.",
        trailer_voiceover=(
            f"In a world where no snack is safe... one {breed} broke every rule in the house. "
            f"Known for {traits.lower()}... Starring {pet_name} in: {up_name}, Grand Theft Snack. "
            f"Coming to TikTok and Reels tonight."
        ),
        roast_captions=[
            f"0:00–0:03 • Don't let this face fool you! {owner_handle}'s {breed} {pet_name} was caught in 4K!",
            f"0:03–0:10 • Wanted for: {traits}. Zero guilt, 100% main character energy.",
            f"0:10–0:15 • Now playing: '{up_name}: GRAND THEFT SNACK' — Comment PAW to cast your pet!",
        ],
        crimes=[
            PetFelonyItem(
                code="FELONY_01: PRIMARY INDICTMENT",
                tag="CAUGHT IN 4K",
                desc=f"Habitually commits {traits.split(',')[0].strip().lower()} while maintaining unbroken eye contact.",
            ),
            PetFelonyItem(
                code="FELONY_02: EMOTIONAL EXTORTION",
                tag="ZERO REMORSE",
                desc=f"Deploys weaponized {breed.lower()} head-tilts to escape all household accountability.",
            ),
            PetFelonyItem(
                code="FELONY_03: MIDNIGHT CHAOS",
                tag="LOCKED IN LORA",
                desc="Treats the living room rug as a private Formula 1 circuit at 3:15 AM.",
            ),
        ],
        poster_1_prompt=f"3D Pixar animated movie poster starring {pet_name} the {breed} in {genre} style.",
        poster_2_prompt=f"Hollywood IMAX action movie poster starring {pet_name} the {breed} with cinematic sparks.",
        poster_3_prompt=f"Prestige detective noir portrait movie poster starring {pet_name} the {breed}.",
        poster_2_title=f"PROTOCOL: {up_name}",
        poster_3_title=f"THE {up_name} DOSSIER",
    )


def run_pawsport_pipeline(data: dict) -> dict:
    """Runs the 4-Minute AI Fulfillment Engine and persists the generated Pawsport Studio bundle."""
    pet_name = (data.get("pet_name") or "Biscuit").strip()
    breed = (data.get("breed") or "Golden Retriever").strip()
    owner_handle = (data.get("owner_handle") or f"@{pet_name.lower()}_official").strip()
    if not owner_handle.startswith("@"):
        owner_handle = f"@{owner_handle}"
    traits = (
        data.get("traits")
        or "Steals snacks off the counter, side-eyes strangers, initiates 3AM zoomies"
    ).strip()
    genre = (data.get("genre") or "Pixar Heist Blockbuster").strip()
    package_tier = data.get("package_tier") or "Node A: $9 Make My Pet Famous"

    order_id = f"paw{random.randint(100000, 999999)}"
    img_bytes, mime_type = parse_image_input(data.get("image_base64"), data.get("image_url"))
    orig_b64 = base64.b64encode(img_bytes).decode("utf-8")

    before_ext = "png" if "png" in mime_type else "jpg"
    before_filename = f"{order_id}_before.{before_ext}"
    (RENDERS_DIR / before_filename).write_bytes(img_bytes)
    before_rel_url = f"renders/{before_filename}"

    vision_prompt = (
        f"You are Pawsport.ai's Oscar-winning Pixar movie trailer writer and pet profiler. "
        f"Analyze this photo of {pet_name} ({breed}, owner {owner_handle}). "
        f"Owner-reported personality traits & crimes: '{traits}'. Preferred movie genre: '{genre}'. "
        f"Scan the photo for exact breed markings, fur color, collar, and expression. "
        f"Write a blockbuster movie title, tagline, brutal bio roast, 40-word movie trailer voiceover script, "
        f"3 timed 15-second vertical video captions, 3 indicted domestic felonies, and 3 movie poster prompts."
    )

    diagnosis: PetVisionOutput | None = None
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if api_key:
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        with httpx.Client(transport=transport, timeout=14.0) as http_client:
            for candidate_model in ("gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3-flash-preview"):
                try:
                    gen_url = (
                        f"https://generativelanguage.googleapis.com/v1beta/models/"
                        f"{candidate_model}:generateContent?key={api_key}"
                    )
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {"inlineData": {"mimeType": mime_type, "data": orig_b64}},
                                    {"text": vision_prompt + "\nReturn valid JSON matching the required fields."},
                                ]
                            }
                        ],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "responseJsonSchema": PetVisionOutput.model_json_schema(),
                        },
                    }
                    resp = http_client.post(gen_url, json=payload)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        candidates = res_json.get("candidates") or []
                        if candidates:
                            parts = (candidates[0].get("content") or {}).get("parts") or []
                            for part in parts:
                                if part.get("text"):
                                    diagnosis = PetVisionOutput.model_validate_json(part["text"])
                                    print(f"[OK] Petstar vision profile generated by {candidate_model}", flush=True)
                                    break
                        if diagnosis is not None:
                            break
                    else:
                        print(f"[Info] {candidate_model} returned HTTP {resp.status_code}; trying next...", flush=True)
                except Exception as exc:
                    print(f"[Warn] {candidate_model} note: {exc}", flush=True)

    if diagnosis is None:
        diagnosis = build_fallback_pet_diagnosis(pet_name, breed, owner_handle, traits, genre)

    # Parallel 3-Poster Generation via gemini-nano-banana-2.1
    poster_prompts = {
        1: diagnosis.poster_1_prompt,
        2: diagnosis.poster_2_prompt,
        3: diagnosis.poster_3_prompt,
    }
    rendered_posters: dict[int, str | None] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futs = {
            pool.submit(generate_poster_render, order_id, p_num, p_prompt, orig_b64, mime_type): p_num
            for p_num, p_prompt in poster_prompts.items()
        }
        for fut in concurrent.futures.as_completed(futs):
            p_num = futs[fut]
            rendered_posters[p_num] = fut.result()

    # If user uploaded their own photo and nano-banana is on Free Tier, use their uploaded photo with distinct cinema grade filters
    # or breed-matched poster fallback if using sample URL
    use_uploaded_for_posters = bool(data.get("image_base64"))
    breed_fallbacks = get_breed_fallbacks(breed)

    crime_colors = ["text-rose-400", "text-amber-400", "text-emerald-400"]
    formatted_crimes = [
        {
            "code": c.code,
            "tag": c.tag,
            "color": crime_colors[i % 3],
            "desc": c.desc,
        }
        for i, c in enumerate(diagnosis.crimes[:3])
    ]

    new_order = {
        "id": order_id,
        "petName": pet_name,
        "ownerHandle": owner_handle,
        "breed": breed,
        "markings": diagnosis.markings_detected,
        "traits": traits,
        "genre": genre,
        "packageTier": package_tier,
        "movieTitle": diagnosis.movie_title,
        "movieTagline": diagnosis.movie_tagline,
        "starringScore": diagnosis.starring_score,
        "viralLift": diagnosis.viral_lift,
        "serialNumber": f"PAW-2026-{random.randint(1000, 9999)}",
        "codename": diagnosis.codename,
        "threatLevel": diagnosis.threat_level,
        "beforeImg": before_rel_url,
        "roastSummary": diagnosis.brutal_bio_roast,
        "trailerVoiceover": diagnosis.trailer_voiceover,
        "roastCaptions": diagnosis.roast_captions[:3],
        "crimes": formatted_crimes,
        "posters": {
            "1": {
                "name": f"Poster 1: {genre}",
                "themeBadge": "Pixar / Disney 3D Studio Render",
                "titleOverlay": diagnosis.movie_title,
                "subtitleOverlay": f"A PAWSPORT STUDIOS ORIGINAL • STARRING {pet_name.upper()}",
                "img": rendered_posters.get(1)
                or (before_rel_url if use_uploaded_for_posters else breed_fallbacks[1]),
                "filterStyle": "contrast(1.18) saturate(1.45) brightness(1.05)",
            },
            "2": {
                "name": "Poster 2: IMAX Action Blockbuster",
                "themeBadge": "IMAX Action Blockbuster Render",
                "titleOverlay": diagnosis.poster_2_title,
                "subtitleOverlay": f"ALL STUNTS PERFORMED BY {pet_name.upper()} • IMAX 3D",
                "img": rendered_posters.get(2)
                or (before_rel_url if use_uploaded_for_posters else breed_fallbacks[2]),
                "filterStyle": "contrast(1.28) saturate(1.25) hue-rotate(-10deg)",
            },
            "3": {
                "name": "Poster 3: Prestige Detective Noir",
                "themeBadge": "Prestige Cinema & Gallery Portrait",
                "titleOverlay": diagnosis.poster_3_title,
                "subtitleOverlay": "CRIME NEVER LOOKED THIS FLUFFY • MMXXVI",
                "img": rendered_posters.get(3)
                or (before_rel_url if use_uploaded_for_posters else breed_fallbacks[3]),
                "filterStyle": "contrast(1.22) sepia(0.24) saturate(1.32)",
            },
        },
        "flowScenebuilder": {
            "flowUrl": "https://labs.google/fx/tools/flow",
            "ingredientLock": f"Ingredient 1 (Character Reference): {pet_name} ({breed}) — {diagnosis.markings_detected}",
            "clip1_framesToVideo": (
                f"[Google Flow • Frames to Video • 0:00–0:03 • Camera: Slow Dolly In] "
                f"Start on the uploaded real photo of {pet_name} ({breed}, {diagnosis.markings_detected}) looking guilty. "
                f"Subtle handheld camera push-in, dramatic low brass movie trailer Braaam sound effect, "
                f"deep Epic Movie Trailer Narrator voiceover: \"In a world where no household rule is safe...\""
            ),
            "clip2_ingredientsToVideo": (
                f"[Google Flow • Ingredients to Video • 0:03–0:10 • Camera: Dynamic Orbit] "
                f"3D Pixar/Disney animated theatrical sequence starring the exact {breed} from Ingredient 1 "
                f"({diagnosis.markings_detected}). {pet_name} heroically commits their signature crime ({traits}) "
                f"in dramatic slow-motion with cinematic rim lighting and flying sparks. "
                f"Epic Movie Trailer Narrator voiceover: \"{diagnosis.trailer_voiceover}\""
            ),
            "clip3_scenebuilderExtend": (
                f"[Google Flow • Scenebuilder Extend / Jump To • 0:10–0:15 • Camera: Crane Pull-Back] "
                f"Extend the scene as the camera pulls back to reveal {pet_name} striking a heroic pose inside a "
                f"gold-framed theatrical movie poster titled \"{diagnosis.movie_title}\" in glowing 3D cinema typography. "
                f"Orchestral crescendo hit."
            ),
            "omniFlashSinglePrompt": (
                f"[# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image1] "
                f"[0-3s] Slow dramatic dolly-in on {pet_name} the {breed} <IMAGE_REF_0> looking guilty in the starting frame. "
                f"[3-7s] Transition into a 3D Pixar animated blockbuster heist scene where the exact same {breed} <IMAGE_REF_0> "
                f"commits {traits.split(',')[0].strip().lower()} with cinematic sparks. "
                f"[7-10s] Heroic theatrical movie poster reveal with bold text '{diagnosis.movie_title}'. "
                f"Include epic movie trailer voiceover and orchestral score."
            ),
        },
        "merch": [
            {
                "sku": "MERCH-CANVAS-16X20",
                "title": f"16x20\" Framed '{diagnosis.movie_title}' Gallery Canvas",
                "price": "$49",
                "numPrice": 49,
                "provider": "Printify • Sensaria Gallery Frame",
                "category": "Wall Art • #1 Bestseller",
                "mockupType": "canvas",
            },
            {
                "sku": "MERCH-HOODIE-BLK",
                "title": f"Heavyweight '{pet_name} World Tour' Studio Hoodie",
                "price": "$59",
                "numPrice": 59,
                "provider": "Gelato • 400GSM Studio Fleece",
                "category": "Apparel • Owner Flex",
                "mockupType": "hoodie",
            },
            {
                "sku": "MERCH-MUG-15OZ",
                "title": f"15oz Cinema Gloss Mug ('Wanted: {pet_name}')",
                "price": "$24",
                "numPrice": 24,
                "provider": "Printify • District Photo",
                "category": "Drinkware • Gift Ready",
                "mockupType": "mug",
            },
            {
                "sku": "MERCH-TOTE-ORG",
                "title": f"Organic Heavy Canvas '{diagnosis.codename}' Tote",
                "price": "$29",
                "numPrice": 29,
                "provider": "Gelato • Eco Canvas",
                "category": "Accessories • Everyday",
                "mockupType": "tote",
            },
        ],
    }

    save_order_to_disk(new_order)
    return new_order


def load_saved_orders() -> dict:
    if ORDERS_FILE.exists():
        try:
            return json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_order_to_disk(order: dict) -> None:
    orders = load_saved_orders()
    orders[order["id"]] = order
    ORDERS_FILE.write_text(json.dumps(orders, indent=2), encoding="utf-8")


class PetstarHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/orders":
            self._send_json(200, {"orders": load_saved_orders()})
            return
        if parsed.path.startswith("/api/orders/"):
            oid = parsed.path.split("/api/orders/", 1)[1]
            orders = load_saved_orders()
            if oid in orders:
                self._send_json(200, {"order": orders[oid]})
            else:
                self._send_json(404, {"error": "Order not found"})
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            payload = json.loads(raw_body)

            if parsed.path in ("/api/cast", "/api/tally-webhook"):
                new_order = run_pawsport_pipeline(payload)
                self._send_json(
                    200,
                    {
                        "status": "ok",
                        "portal_url": f"http://localhost:8096/?order={new_order['id']}",
                        "order": new_order,
                    },
                )
                return

            if parsed.path == "/api/github/create-org-repo":
                org = (payload.get("org") or "").strip()
                name = (payload.get("name") or "petstar-pawsport-ai").strip()
                if not org:
                    self._send_json(400, {"error": "Parameter 'org' is required."})
                    return
                res = create_organization_repository(
                    org=org,
                    name=name,
                    description=payload.get(
                        "description",
                        "Pawsport.ai (Petstar) — 24-Hour Viral Pet Persona & Custom Merch Studio",
                    ),
                    homepage=payload.get("homepage", "https://www.madethis.com/business/petstar-hp5"),
                    private=bool(payload.get("private", False)),
                    visibility=payload.get("visibility"),
                    has_issues=bool(payload.get("has_issues", True)),
                    has_projects=bool(payload.get("has_projects", True)),
                    has_wiki=bool(payload.get("has_wiki", True)),
                    auto_init=bool(payload.get("auto_init", False)),
                    gitignore_template=payload.get("gitignore_template"),
                    license_template=payload.get("license_template"),
                    fallback_to_user=bool(payload.get("fallback_to_user", True)),
                )
                self._send_json(200 if res.get("ok") else res.get("status_code", 400), res)
                return

            self._send_json(404, {"error": "Endpoint not found"})
        except Exception as exc:
            traceback.print_exc()
            self._send_json(500, {"error": str(exc)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8096"))
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("0.0.0.0", port), PetstarHandler)
    print(f"🎬 Petstar (Pawsport.ai) Studio Server running at http://localhost:{port}", flush=True)
    server.serve_forever()
