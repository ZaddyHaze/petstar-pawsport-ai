#!/usr/bin/env python3
"""
Printify REST API v1 Client for Petstar (Pawsport.ai)
Base URL: https://api.printify.com/v1
Docs: https://developers.printify.com/

Handles:
  1. Discovering the active Printify Shop ID (`GET /v1/shops.json`)
  2. Uploading generated Pet Movie Poster images to Printify Media Library (`POST /v1/uploads/images.json`)
  3. Creating Print-on-Demand products (`POST /v1/shops/{shop_id}/products.json`) for:
     - 16x20" Gallery Framed/Stretched Canvas ($49)
     - Heavyweight Studio Hoodie ($59)
     - 15oz Cinema Gloss Mug ($24)
     - Organic Heavy Canvas Tote ($29)
  4. Submitting customer orders (`POST /v1/shops/{shop_id}/orders.json`)
  5. Automatic Sandbox Fallback when `PRINTIFY_API_TOKEN` is not yet configured in `.env`.
"""

import base64
import json
import os
from pathlib import Path
from typing import Any
import httpx

PRINTIFY_API_BASE = "https://api.printify.com/v1"

# Standard Printify Catalog Blueprints & Print Providers
PRINTIFY_BLUEPRINTS = {
    "canvas": {
        "blueprint_id": 50,       # Matte Canvas, Stretched 1.25"
        "print_provider_id": 2,   # Sensaria (US/Global)
        "variant_id": 34244,      # 16" x 20"
        "retail_cents": 4900,
        "title_suffix": "16x20\" Gallery Movie Poster Canvas",
    },
    "hoodie": {
        "blueprint_id": 77,       # Unisex Heavy Blend Hooded Sweatshirt
        "print_provider_id": 99,  # Printify Choice
        "variant_id": 32919,      # Black / L
        "retail_cents": 5900,
        "title_suffix": "Heavyweight Studio Tour Hoodie",
    },
    "mug": {
        "blueprint_id": 68,       # Mug 15oz
        "print_provider_id": 28,  # District Photo
        "variant_id": 33719,      # 15oz White Ceramic
        "retail_cents": 2400,
        "title_suffix": "15oz Cinema Gloss Mug",
    },
    "tote": {
        "blueprint_id": 1313,     # Cotton Canvas Tote Bag
        "print_provider_id": 99,  # Printify Choice
        "variant_id": 99702,      # Natural / One Size
        "retail_cents": 2900,
        "title_suffix": "Organic Dog-Park Canvas Tote",
    },
}


def get_printify_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "Pawsport-Petstar-Printify-Integration/1.0",
    }


def resolve_shop_id(client: httpx.Client, token: str, explicit_shop_id: str | None = None) -> str:
    if explicit_shop_id and str(explicit_shop_id).strip():
        return str(explicit_shop_id).strip()
    env_shop = os.environ.get("PRINTIFY_SHOP_ID", "").strip()
    if env_shop:
        return env_shop

    resp = client.get(f"{PRINTIFY_API_BASE}/shops.json", headers=get_printify_headers(token))
    resp.raise_for_status()
    shops = resp.json()
    if isinstance(shops, list) and shops:
        return str(shops[0]["id"])
    raise RuntimeError("No Printify shops found on this account. Create a shop in Printify first.")


def upload_poster_to_printify(
    client: httpx.Client,
    token: str,
    file_name: str,
    poster_url_or_path: str,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Uploads the pet's Movie Poster PNG/JPG to `POST /v1/uploads/images.json`."""
    payload: dict[str, Any] = {"file_name": file_name}

    if poster_url_or_path.startswith("http://") or poster_url_or_path.startswith("https://"):
        payload["url"] = poster_url_or_path
    else:
        local_path = (base_dir / poster_url_or_path) if base_dir else Path(poster_url_or_path)
        img_bytes = local_path.read_bytes()
        payload["contents"] = base64.b64encode(img_bytes).decode("utf-8")

    resp = client.post(
        f"{PRINTIFY_API_BASE}/uploads/images.json",
        headers=get_printify_headers(token),
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


def build_printify_product_payload(
    pet_name: str,
    movie_title: str,
    mockup_type: str,
    printify_image_id: str,
) -> dict[str, Any]:
    spec = PRINTIFY_BLUEPRINTS.get(mockup_type, PRINTIFY_BLUEPRINTS["canvas"])
    return {
        "title": f"{pet_name} — '{movie_title}' {spec['title_suffix']}",
        "description": (
            f"Official Pawsport.ai Theatrical Movie Merch starring {pet_name} in '{movie_title}'. "
            f"Printed on museum-grade stock via Printify."
        ),
        "blueprint_id": spec["blueprint_id"],
        "print_provider_id": spec["print_provider_id"],
        "variants": [
            {
                "id": spec["variant_id"],
                "price": spec["retail_cents"],
                "is_enabled": True,
            }
        ],
        "print_areas": [
            {
                "variant_ids": [spec["variant_id"]],
                "placeholders": [
                    {
                        "position": "front",
                        "images": [
                            {
                                "id": printify_image_id,
                                "x": 0.5,
                                "y": 0.5,
                                "scale": 1.0,
                                "angle": 0,
                            }
                        ],
                    }
                ],
            }
        ],
    }


def create_printify_product_or_sandbox(
    order_id: str,
    pet_name: str,
    movie_title: str,
    mockup_type: str,
    poster_img: str,
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """
    If `PRINTIFY_API_TOKEN` is set in `.env`, uploads the poster to Printify (`POST /v1/uploads/images.json`)
    and creates a live product (`POST /v1/shops/{shop_id}/products.json`).
    Otherwise returns a complete Sandbox preview with the exact Printify v1 request payload.
    """
    token = os.environ.get("PRINTIFY_API_TOKEN", "").strip()
    spec = PRINTIFY_BLUEPRINTS.get(mockup_type, PRINTIFY_BLUEPRINTS["canvas"])

    if not token:
        simulated_img_id = f"671a9f{abs(hash(order_id + mockup_type)) % 1000000:06d}"
        req_body = build_printify_product_payload(pet_name, movie_title, mockup_type, simulated_img_id)
        return {
            "mode": "sandbox",
            "live_api_connected": False,
            "message": "Printify Sandbox Mode active (Add PRINTIFY_API_TOKEN to .env for live shop creation)",
            "endpoints": {
                "1_upload_image": f"POST {PRINTIFY_API_BASE}/uploads/images.json",
                "2_create_product": f"POST {PRINTIFY_API_BASE}/shops/{{shop_id}}/products.json",
                "3_submit_order": f"POST {PRINTIFY_API_BASE}/shops/{{shop_id}}/orders.json",
            },
            "image_upload_response": {
                "id": simulated_img_id,
                "file_name": f"{order_id}_{mockup_type}.png",
                "preview_url": poster_img,
            },
            "product_create_payload": req_body,
            "retail_price_usd": f"${spec['retail_cents'] / 100:.2f}",
        }

    with httpx.Client(timeout=25.0) as client:
        shop_id = resolve_shop_id(client, token)
        upload_res = upload_poster_to_printify(
            client=client,
            token=token,
            file_name=f"{order_id}_{mockup_type}.jpg",
            poster_url_or_path=poster_img,
            base_dir=base_dir,
        )
        image_id = upload_res["id"]
        product_payload = build_printify_product_payload(pet_name, movie_title, mockup_type, image_id)
        prod_resp = client.post(
            f"{PRINTIFY_API_BASE}/shops/{shop_id}/products.json",
            headers=get_printify_headers(token),
            json=product_payload,
        )
        prod_resp.raise_for_status()
        prod_json = prod_resp.json()
        return {
            "mode": "live",
            "live_api_connected": True,
            "shop_id": shop_id,
            "image_upload_response": upload_res,
            "product_response": prod_json,
            "product_id": prod_json.get("id"),
            "retail_price_usd": f"${spec['retail_cents'] / 100:.2f}",
        }


if __name__ == "__main__":
    print(
        json.dumps(
            create_printify_product_or_sandbox(
                order_id="paw849201",
                pet_name="Barnaby",
                movie_title="CRIMSON: THE CHEESE HEIST",
                mockup_type="canvas",
                poster_img="https://images.unsplash.com/photo-1537151608828-ea2b11777ee8?auto=format&fit=crop&w=1000&q=85",
            ),
            indent=2,
        )
    )
