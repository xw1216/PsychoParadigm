from __future__ import annotations

from collections.abc import Callable, Sequence

import pyglet


def load_font_runtime_name(requested_name: str, *, size: int = 24) -> str | None:
    try:
        return getattr(pyglet.font.load(requested_name, size), "name", None)
    except Exception:
        return None


def is_unexpected_cjk_variant(requested_name: str, resolved_name: str | None) -> bool:
    requested = requested_name.casefold().strip()
    resolved = (resolved_name or "").casefold().strip()
    if not requested or not resolved:
        return False
    if any(tag in requested for tag in (" cjk sc", " sc", " cn", "source han", "wenquanyi", "simhei", "heiti", "uming", "ukai", "fangsong", "song")):
        return any(tag in resolved for tag in (" cjk jp", " jp", " cjk tc", " tc", " cjk hk", " hk", " cjk kr", " kr"))
    return False


def choose_text_font(
    *,
    preferred_font: str | None = None,
    fallback_fonts: Sequence[str] = (),
    font_loader: Callable[[str], str | None] | None = None,
) -> tuple[str, str | None]:
    loader = font_loader or load_font_runtime_name
    seen: set[str] = set()
    for candidate in (preferred_font, *fallback_fonts):
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        resolved_name = loader(candidate)
        if resolved_name is None:
            continue
        if is_unexpected_cjk_variant(candidate, resolved_name):
            continue
        return candidate, resolved_name
    return "", loader("")