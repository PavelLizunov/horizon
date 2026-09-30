"""Public dashboard metadata and deterministic selection (stdlib only)."""

import hashlib
import html
import math
import re
from datetime import date, timedelta
from urllib.parse import urlsplit

from .archive import parse_summary

ISSUE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z]{2,3})$")
SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+-\d+$")


def plain(value: object, limit: int = 240) -> str:
    text = str(value or "")
    text = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.S | re.I)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]*>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\\([\\`*_{}\[\]()#+\-.!|])", r"\1", text)
    text = re.sub(r"[`*_]", "", text)
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit - 1].rsplit(" ", 1)[0] + "…"


def score_value(value: object):
    if isinstance(value, bool):
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if math.isfinite(score) and 0 <= score <= 10 else None


def cover_key(profile: str) -> str:
    p = profile.lower()
    for tokens, key in [
        (("finance", "econom", "market"), "finance"),
        (("video", "speech"), "video"),
        (("gaming", "raiders", "community"), "community"),
        (("vpn", "censor", "network"), "network"),
        (("infra", "homelab", "server"), "server"),
        (("agent", "harness", "workflow", "sdd"), "orbit"),
        (("token", "local", "llm", "quant"), "chip"),
    ]:
        if any(token in p for token in tokens):
            return key
    return "wave"


def metadata(*, title, teaser, profile_id, profile_name, score=None, tags=(), source_url=""):
    """Allowlist only reader-facing fields; ignore private model state entirely."""
    profile = str(profile_id or "unclassified")
    url = str(source_url or "")
    try:
        parsed = urlsplit(url)
    except ValueError:
        parsed = urlsplit("")
        url = ""
    public_url = url if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password else ""
    return {
        "schema_version": 1,
        "title": plain(title, 500), "teaser": plain(teaser),
        "profile_id": profile if re.fullmatch(r"[\w-]{1,100}", profile, re.ASCII) else "unclassified",
        "profile_name": plain(profile_name or profile, 100),
        "score": score_value(score),
        "tags": [plain(t, 60).lstrip("#") for t in list(tags or ())[:20] if plain(t, 60)],
        "source_url": public_url,
        "source_label": parsed.hostname if public_url else "",
    }


def page_item(path: str, body: str, meta: dict, profile_names=None):
    """Derive a public item from an existing published page, without rewriting it."""
    parts = path.split("/")
    if len(parts) != 3 or parts[0] != "digest" or not parts[2].endswith(".md"):
        return None
    issue = ISSUE_RE.fullmatch(parts[1])
    slug = parts[2][:-3]
    if not issue or issue[2] != "ru" or not SLUG_RE.fullmatch(slug):
        return None
    date.fromisoformat(issue[1])
    profile = re.sub(r"-\d+$", "", slug)
    heading = re.search(r"(?m)^#\s+(.+)$", body)
    explicit = meta.get("dashboard")
    if explicit is not None:
        if not isinstance(explicit, dict) or explicit.get("schema_version") != 1:
            raise ValueError("Unsupported dashboard metadata")
        values = metadata(**{key: explicit.get(key) for key in (
            "title", "teaser", "profile_id", "profile_name", "score", "tags", "source_url"
        )})
    else:
        legacy = parse_summary(body, issue[1], "ru", page_base="digest")
        old = next((d for d in legacy if d["id"] == f"{parts[1]}-{slug}"), None)
        lede = re.search(r"\n\n([^\n]+)\n\{:\s*\.hz-lede\}", body)
        badge = re.search(r'class="hz-score[^"\n]*"[^>]*>([\d.]+)', body)
        source = re.search(r'<a\b[^>]*class="hz-source"[^>]*href="([^"]+)"', body)
        tags = re.findall(r'class="hz-tag"[^>]*>([^<]+)</a>', body)
        if not heading and not old:
            raise ValueError("Published article has no recognized title")
        values = metadata(
            title=meta.get("title") or (old["title"] if old else heading[1]),
            teaser=old["lead"] if old else (lede[1] if lede else ""),
            profile_id=profile, profile_name=(profile_names or {}).get(profile, profile),
            score=old["score"] if old else (badge[1] if badge else None),
            tags=old["tags"] if old else tags,
            source_url=old["url"] if old else (html.unescape(source[1]) if source else ""),
        )
    if not values["title"]:
        raise ValueError("Published article has empty title")
    identifier = f"{parts[1]}-{slug}"
    public = {k: v for k, v in values.items() if k not in {"schema_version", "source_url"}}
    # The attached player is the publication signal; loose synthesis files are not.
    audio = bool(re.search(r'<audio\b(?=[^>]*class="[^"]*\bhz-narration\b)(?=[^>]*src="https?://)[^>]*>', body))
    public.update({
        "id": identifier, "page": f"digest/{parts[1]}/{slug}/", "date": issue[1],
        "language": "ru", "reading_minutes": max(1, round(len(plain(body, 100000).split()) / 200)),
        "audio_ready": audio, "cover_key": cover_key(values["profile_id"]),
        "cover_seed": int(hashlib.sha256(identifier.encode()).hexdigest()[:8], 16) % 4,
    })
    # Private source URL is used only for focus dedup, never serialized by catalog().
    public["_dedup"] = values["source_url"] or values["title"].casefold()
    return public


def newest(items):
    return sorted(items, key=lambda x: (x["date"], x["score"] if x["score"] is not None else -1, x["id"]), reverse=True)


def focus(items, count=5):
    if not items:
        return []
    latest = date.fromisoformat(max(x["date"] for x in items))
    ranked = sorted(items, key=lambda x: (-(x["score"] if x["score"] is not None else -1), -date.fromisoformat(x["date"]).toordinal(), x["id"]))
    candidates = []
    for days in (7, 30, None):
        seen = set()
        candidates = []
        for item in ranked:
            if days is not None and date.fromisoformat(item["date"]) <= latest - timedelta(days=days):
                continue
            key = item.get("_dedup") or item["title"].casefold()
            if key not in seen:
                seen.add(key)
                candidates.append(item)
        if len(candidates) >= count:
            break
    selected = []
    # Unknown-score candidates fill remaining slots only after scored ones.
    for pool in ([x for x in candidates if x["score"] is not None],
                 [x for x in candidates if x["score"] is None]):
        for cap in (1, 2, count):
            for item in pool:
                if item in selected:
                    continue
                if sum(x["profile_id"] == item["profile_id"] for x in selected) < cap:
                    selected.append(item)
                    if len(selected) == count:
                        return selected
    return selected


def catalog(items, generated_at):
    return {"schema_version": 1, "generated_at": generated_at,
            "focus_ids": [x["id"] for x in focus(items)],
            "items": [{k: v for k, v in x.items() if not k.startswith("_")} for x in newest(items)]}
