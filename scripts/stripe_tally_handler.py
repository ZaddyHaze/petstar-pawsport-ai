#!/usr/bin/env python3
"""
Tally.so Webhook Parser & Stripe Checkout Session Integration for Petstar (Pawsport.ai)

Handles:
  1. `parse_tally_webhook_payload(payload)` — Parses native Tally.so `FORM_RESPONSE` JSON webhooks
     (file uploads, multiple choice, dropdowns, checkboxes, and Stripe payment fields) into normalized
     Pawsport casting inputs.
  2. `create_stripe_checkout_or_sandbox(data, host_url)` — Creates a live Stripe Checkout Session via
     `POST https://api.stripe.com/v1/checkout/sessions` when `STRIPE_SECRET_KEY` is present in `.env`,
     or returns a complete Stripe Checkout Session preview + instant fulfillment trigger in Sandbox Mode.
"""

import os
import time
import uuid
from typing import Any
import httpx

STRIPE_API_BASE = "https://api.stripe.com/v1"


def parse_tally_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Parses a Tally.so `FORM_RESPONSE` webhook payload (or direct JSON payload)
    into the normalized dictionary expected by `run_pawsport_pipeline()`.
    """
    if "data" not in payload or "fields" not in (payload.get("data") or {}):
        # Already a direct JSON payload
        return payload

    data = payload.get("data") or {}
    fields = data.get("fields") or []

    extracted: dict[str, Any] = {
        "pet_name": "Biscuit",
        "breed": "Golden Retriever",
        "owner_handle": "@biscuit_the_golden",
        "customer_email": "",
        "traits": "Steals snacks off the counter, weaponizes puppy eyes, initiates 3AM zoomies",
        "genre": "Pixar Heist Blockbuster",
        "package_tier": "Node A: $9 Make My Pet Famous",
        "canvas_bump": False,
        "image_url": "https://images.unsplash.com/photo-1552053831-71594a27632d?auto=format&fit=crop&w=1000&q=85",
        "tally_response_id": data.get("responseId") or data.get("submissionId") or f"tally_{uuid.uuid4().hex[:8]}",
    }

    def resolve_option_text(field_obj: dict[str, Any]) -> str:
        val = field_obj.get("value")
        options = field_obj.get("options") or []
        opt_map = {o.get("id"): o.get("text", "") for o in options if isinstance(o, dict)}
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str) and first in opt_map:
                return opt_map[first]
            return str(first)
        if isinstance(val, str):
            return opt_map.get(val, val)
        return ""

    for f in fields:
        label = (f.get("label") or "").strip().lower()
        ftype = (f.get("type") or "").strip().upper()
        val = f.get("value")

        if "pet" in label and "name" in label:
            if isinstance(val, str) and val.strip():
                extracted["pet_name"] = val.strip()
        elif "breed" in label or "species" in label:
            opt_txt = resolve_option_text(f) if ftype in ("DROPDOWN", "MULTIPLE_CHOICE") else (val or "")
            if isinstance(opt_txt, str) and opt_txt.strip():
                extracted["breed"] = opt_txt.strip()
        elif "handle" in label or "tiktok" in label and ftype == "INPUT_TEXT":
            if isinstance(val, str) and val.strip():
                h = val.strip()
                extracted["owner_handle"] = h if h.startswith("@") else f"@{h}"
        elif "email" in label or ftype == "INPUT_EMAIL":
            if isinstance(val, str) and val.strip():
                extracted["customer_email"] = val.strip()
        elif "trait" in label or "crime" in label or "personality" in label:
            if isinstance(val, str) and val.strip():
                extracted["traits"] = val.strip()
        elif "genre" in label or "theme" in label or "style" in label:
            opt_txt = resolve_option_text(f)
            if opt_txt:
                extracted["genre"] = opt_txt.strip()
        elif "photo" in label or "upload" in label or ftype == "FILE_UPLOAD":
            if isinstance(val, list) and val and isinstance(val[0], dict) and val[0].get("url"):
                extracted["image_url"] = val[0]["url"]
            elif isinstance(val, str) and val.startswith("http"):
                extracted["image_url"] = val
        elif "package" in label or "tier" in label or "famous" in label:
            opt_txt = resolve_option_text(f).lower()
            if "24" in opt_txt or "private" in opt_txt or "vip" in opt_txt:
                extracted["package_tier"] = "Node B: $24 Private VIP Bundle"
            else:
                extracted["package_tier"] = "Node A: $9 Make My Pet Famous"
        elif "bump" in label or "canvas" in label:
            extracted["canvas_bump"] = bool(val)

    return extracted


def build_sample_tally_webhook_payload(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generates a realistic Tally.so `FORM_RESPONSE` webhook payload for testing `POST /api/tally-webhook`."""
    ov = overrides or {}
    pet_name = ov.get("pet_name") or "Pickles"
    breed = ov.get("breed") or "French Bulldog"
    handle = ov.get("owner_handle") or "@pickles_the_potato"
    email = ov.get("owner_email") or "pickles@example.com"
    traits = ov.get("traits") or "Snores like a freight train, steals pizza crusts, refuses to walk in the rain"
    img_url = ov.get("image_url") or "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?auto=format&fit=crop&w=1000&q=85"
    tier_choice = "tier_vip_24" if "24" in str(ov.get("package_tier", "")) else "tier_public_9"

    return {
        "eventId": f"evt_{uuid.uuid4().hex[:12]}",
        "eventType": "FORM_RESPONSE",
        "createdAt": "2026-10-26T11:38:00.000Z",
        "data": {
            "responseId": f"tally_{uuid.uuid4().hex[:8]}",
            "submissionId": f"sub_{uuid.uuid4().hex[:8]}",
            "formId": "pawsport-petstar-intake",
            "formName": "Pawsport.ai — Turn Your Pet Into a Viral Movie Star ($9 / $24)",
            "fields": [
                {"key": "q1_pet_name", "label": "What is your pet's name?", "type": "INPUT_TEXT", "value": pet_name},
                {"key": "q2_breed", "label": "Species & Breed", "type": "INPUT_TEXT", "value": breed},
                {
                    "key": "q3_handle",
                    "label": "Your TikTok / IG Handle (for tag)",
                    "type": "INPUT_TEXT",
                    "value": handle,
                },
                {
                    "key": "q4_email",
                    "label": "Delivery Email",
                    "type": "INPUT_EMAIL",
                    "value": email,
                },
                {
                    "key": "q5_traits",
                    "label": "3 Personality Traits or Domestic Crimes",
                    "type": "INPUT_TEXT",
                    "value": traits,
                },
                {
                    "key": "q6_genre",
                    "label": "Select Blockbuster Movie Genre",
                    "type": "DROPDOWN",
                    "value": ["opt_pixar"],
                    "options": [
                        {"id": "opt_pixar", "text": ov.get("genre") or "Pixar Heist Blockbuster"},
                        {"id": "opt_action", "text": "Sci-Fi Action Epic"},
                    ],
                },
                {
                    "key": "q7_photo",
                    "label": "Upload 3 Pet Photos",
                    "type": "FILE_UPLOAD",
                    "value": [
                        {
                            "id": "file_01",
                            "name": f"{pet_name.lower()}_guilty.jpg",
                            "url": img_url,
                            "mimeType": "image/jpeg",
                        }
                    ],
                },
                {
                    "key": "q8_package",
                    "label": "Select Pawsport Package Tier",
                    "type": "MULTIPLE_CHOICE",
                    "value": [tier_choice],
                    "options": [
                        {"id": "tier_public_9", "text": "Node A: $9 Make My Pet Famous ($10 Off TikTok Opt-In)"},
                        {"id": "tier_vip_24", "text": "Node B: $24 Private VIP Bundle"},
                    ],
                },
                {
                    "key": "q9_bump",
                    "label": "1-Click Order Bump Canvas",
                    "type": "CHECKBOXES",
                    "value": bool(ov.get("canvas_bump", False)),
                },
            ],
        },
    }


def create_stripe_checkout_or_sandbox(
    data: dict[str, Any],
    order_id: str,
    host_url: str = "http://localhost:8096",
) -> dict[str, Any]:
    """
    Creates a Stripe Checkout Session (`POST https://api.stripe.com/v1/checkout/sessions`)
    if `STRIPE_SECRET_KEY` is configured in `.env`, or returns a complete Stripe Checkout
    Session object in Sandbox Mode.
    """
    stripe_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    is_vip = "24" in str(data.get("package_tier", "")) or data.get("tier_code") == "private"
    canvas_bump = bool(data.get("canvas_bump", False))
    pet_name = data.get("pet_name") or "Your Pet"

    base_cents = 2400 if is_vip else 900
    base_name = (
        f"Pawsport.ai Private VIP Bundle — Starring {pet_name}"
        if is_vip
        else f"Pawsport.ai 'Make My Pet Famous' Bundle ($10 TikTok Opt-In Discount) — Starring {pet_name}"
    )

    line_items_summary = [
        {
            "name": base_name,
            "amount_cents": base_cents,
            "amount_formatted": f"${base_cents / 100:.2f}",
            "quantity": 1,
        }
    ]
    total_cents = base_cents

    if canvas_bump:
        line_items_summary.append(
            {
                "name": f"1-Click Order Bump: 16x20\" Framed '{pet_name}' Movie Poster Canvas (Printify)",
                "amount_cents": 3900,
                "amount_formatted": "$39.00",
                "quantity": 1,
            }
        )
        total_cents += 3900

    success_url = f"{host_url}/?order={order_id}&checkout=success"
    cancel_url = f"{host_url}/?order={order_id}&checkout=cancel"

    if stripe_key and stripe_key.startswith(("sk_live_", "sk_test_")):
        form_data: dict[str, str] = {
            "mode": "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "payment_intent_data[statement_descriptor]": "PAWSPORT AI STUDIO",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(base_cents),
            "line_items[0][price_data][product_data][name]": base_name,
            "line_items[0][quantity]": "1",
            "metadata[order_id]": order_id,
            "metadata[pet_name]": pet_name,
            "metadata[canvas_bump]": str(canvas_bump),
        }
        if canvas_bump:
            form_data.update(
                {
                    "line_items[1][price_data][currency]": "usd",
                    "line_items[1][price_data][unit_amount]": "3900",
                    "line_items[1][price_data][product_data][name]": (
                        f"16x20 Framed Movie Poster Canvas ({pet_name})"
                    ),
                    "line_items[1][quantity]": "1",
                }
            )
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{STRIPE_API_BASE}/checkout/sessions",
                headers={"Authorization": f"Bearer {stripe_key}"},
                data=form_data,
            )
            resp.raise_for_status()
            session_json = resp.json()
            return {
                "mode": "live",
                "live_stripe_connected": True,
                "session_id": session_json.get("id"),
                "checkout_url": session_json.get("url"),
                "total_formatted": f"${total_cents / 100:.2f}",
                "line_items": line_items_summary,
            }

    # Sandbox Stripe Checkout Session (when STRIPE_SECRET_KEY is not yet added to .env)
    return {
        "mode": "sandbox",
        "live_stripe_connected": False,
        "session_id": f"cs_test_{uuid.uuid4().hex[:24]}",
        "created": int(time.time()),
        "statement_descriptor": "PAWSPORT AI STUDIO",
        "checkout_url": success_url,
        "total_cents": total_cents,
        "total_formatted": f"${total_cents / 100:.2f}",
        "line_items": line_items_summary,
        "note": "Stripe Sandbox Mode active (Add STRIPE_SECRET_KEY to .env for live Stripe hosted redirect)",
    }
