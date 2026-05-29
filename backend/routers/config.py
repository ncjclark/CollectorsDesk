"""
Config endpoints — read and write API keys from .env live.
Changes take effect immediately (updates os.environ + settings object).
No restart needed for new API calls.
"""

import os
import re
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/config", tags=["config"])

ENV_PATH = Path(__file__).parent.parent.parent / ".env"

# Keys exposed to the UI — display name, env var name, description, sensitive
FIELDS = [
    {
        "key": "EBAY_APP_ID",
        "label": "eBay App ID (Client ID)",
        "description": "From developer.ebay.com → My Account → Application Access Keys",
        "group": "eBay API",
        "sensitive": True,
        "setup_url": "https://developer.ebay.com/",
    },
    {
        "key": "EBAY_CERT_ID",
        "label": "eBay Cert ID (Client Secret)",
        "description": "Same page as App ID",
        "group": "eBay API",
        "sensitive": True,
        "setup_url": "https://developer.ebay.com/",
    },
    {
        "key": "EBAY_DEV_ID",
        "label": "eBay Dev ID",
        "description": "Same page as App ID",
        "group": "eBay API",
        "sensitive": True,
        "setup_url": "https://developer.ebay.com/",
    },
    {
        "key": "EBAY_ENVIRONMENT",
        "label": "eBay Environment",
        "description": "Use 'production' for real data, 'sandbox' for testing",
        "group": "eBay API",
        "sensitive": False,
        "options": ["production", "sandbox"],
    },
    {
        "key": "ETSY_API_KEY",
        "label": "Etsy API Key",
        "description": "From developers.etsy.com → Create App (free) — enables Etsy vintage listings",
        "group": "Additional Data Sources",
        "sensitive": True,
        "setup_url": "https://developers.etsy.com/",
    },
    {
        "key": "RESEARCH_CACHE_TTL_HOURS",
        "label": "Research Cache Duration (hours)",
        "description": "How long to cache results before re-fetching. Default: 24",
        "group": "App Settings",
        "sensitive": False,
    },
    {
        "key": "ETSY_ENABLED",
        "label": "Etsy Listings",
        "description": "Fetch Etsy asking prices. Disable if you're hitting rate limits.",
        "group": "Source Toggles",
        "sensitive": False,
        "options": ["true", "false"],
    },
    {
        "key": "HERITAGE_ENABLED",
        "label": "Heritage Auctions",
        "description": "Scrape Heritage Auctions realized prices. Disable to reduce external requests.",
        "group": "Source Toggles",
        "sensitive": False,
        "options": ["true", "false"],
    },
    {
        "key": "BGG_ENABLED",
        "label": "BoardGameGeek",
        "description": "Fetch BGG game data and marketplace prices. Disable to skip for non-game searches.",
        "group": "Source Toggles",
        "sensitive": False,
        "options": ["true", "false"],
    },
]


def _read_env() -> dict[str, str]:
    """Parse .env file into a dict."""
    values = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()
    return values


def _write_env(updates: dict[str, str]) -> None:
    """Update specific keys in the .env file, preserving comments and order."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text("")

    lines = ENV_PATH.read_text().splitlines()
    written = set()
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                written.add(key)
                continue
        new_lines.append(line)

    # Append any keys not yet in the file
    for key, val in updates.items():
        if key not in written:
            new_lines.append(f"{key}={val}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n")


def _mask(value: str) -> str:
    """Show first 6 chars + asterisks for sensitive values."""
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:6] + "•" * min(len(value) - 6, 20)


@router.get("")
def get_config():
    env_values = _read_env()
    groups: dict[str, list] = {}

    for field in FIELDS:
        key = field["key"]
        raw_value = env_values.get(key, "")
        is_set = bool(raw_value)

        entry = {
            **field,
            "is_set": is_set,
            "masked_value": _mask(raw_value) if field["sensitive"] and is_set else raw_value,
            # Return full value for non-sensitive fields so UI can show them
        }
        if not field["sensitive"]:
            entry["value"] = raw_value

        g = field["group"]
        groups.setdefault(g, []).append(entry)

    return {
        "groups": [
            {"name": name, "fields": fields}
            for name, fields in groups.items()
        ]
    }


@router.put("")
def update_config(body: dict):
    """
    Body: { "updates": { "EBAY_APP_ID": "new-value", ... } }
    Sensitive keys: send the actual value. Empty string = clear the key.
    """
    updates: dict[str, str] = body.get("updates", {})
    if not updates:
        raise HTTPException(400, "No updates provided")

    # Validate keys are in our allowed list
    allowed = {f["key"] for f in FIELDS}
    bad = [k for k in updates if k not in allowed]
    if bad:
        raise HTTPException(400, f"Unknown config keys: {bad}")

    # Write to .env file
    _write_env(updates)

    # Apply to live process immediately — update os.environ + settings
    import config as cfg
    for key, value in updates.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    # Reload the settings object in-place
    for key, value in updates.items():
        attr = key.lower()
        if hasattr(cfg.settings, attr):
            try:
                field_info = cfg.settings.model_fields.get(attr)
                if field_info:
                    field_type = field_info.annotation
                    typed_val = field_type(value) if value else (field_type() if field_type != str else "")
                    object.__setattr__(cfg.settings, attr, typed_val)
            except Exception:
                object.__setattr__(cfg.settings, attr, value)

    return {
        "success": True,
        "updated": list(updates.keys()),
        "message": f"Updated {len(updates)} setting(s). Changes are live immediately.",
    }
