"""A personal Pinterest connection for Claude: read boards and pins, make boards, pin images.

Uses Pinterest's official API (v5) with the owner's own access token, kept in .env beside this file:

    PINTEREST_ACCESS_TOKEN=...
    PINTEREST_API_BASE=https://api.pinterest.com/v5      (optional; this is the default)

The token is never printed or returned by any tool.
"""
import base64
import mimetypes
import os
from pathlib import Path

import httpx
from mcp.server.mcpserver import MCPServer

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = "https://api.pinterest.com/v5"


def _settings():
    vals = {}
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    token = os.environ.get("PINTEREST_ACCESS_TOKEN") or vals.get("PINTEREST_ACCESS_TOKEN", "")
    base = os.environ.get("PINTEREST_API_BASE") or vals.get("PINTEREST_API_BASE") or DEFAULT_BASE
    return token, base.rstrip("/")


class PinterestError(Exception):
    pass


def _call(method, path, params=None, body=None):
    token, base = _settings()
    if not token or token.startswith("paste"):
        raise PinterestError(
            "No Pinterest token yet. Paste it into "
            f"{HERE / '.env'} as PINTEREST_ACCESS_TOKEN=..., then restart Claude.")
    params = {k: v for k, v in (params or {}).items() if v is not None}
    with httpx.Client(timeout=60) as c:
        r = c.request(method, base + path, params=params, json=body,
                      headers={"Authorization": f"Bearer {token}"})
    if r.status_code >= 400:
        try:
            msg = r.json().get("message", r.text[:300])
        except Exception:
            msg = r.text[:300]
        hint = {401: " (the token is wrong or has expired: make a new one on the app page)",
                403: " (the token is missing a permission, or this needs a higher access tier)",
                429: " (too many requests today: Trial access allows 1,000 a day)"}.get(r.status_code, "")
        if "consumer type" in msg.lower():
            hint = " (Pinterest has not approved the app's Trial access yet; check the app page)"
        raise PinterestError(f"Pinterest said {r.status_code}: {msg}{hint}")
    return r.json() if r.content else {}


def _image_url(pin):
    imgs = (pin.get("media") or {}).get("images") or {}
    for size in ("originals", "1200x", "600x", "400x300", "150x150"):
        if size in imgs and imgs[size].get("url"):
            return imgs[size]["url"]
    return None


def _pin_short(p):
    return {"id": p.get("id"), "title": p.get("title"), "description": p.get("description"),
            "link": p.get("link"), "board_id": p.get("board_id"), "image": _image_url(p),
            "created": p.get("created_at")}


def _board_short(b):
    return {"id": b.get("id"), "name": b.get("name"), "description": b.get("description"),
            "privacy": b.get("privacy"), "pins": b.get("pin_count")}


server = MCPServer(
    name="pinterest",
    instructions=("The owner's Pinterest account. Read their boards and pins, make boards, and pin images. "
                  "Only pin or make boards when the owner asked for that specific pin or board."),
)


@server.tool(description="Check the connection: the Pinterest account this token belongs to.")
def whoami() -> dict:
    u = _call("GET", "/user_account")
    return {"username": u.get("username"), "account_type": u.get("account_type"),
            "boards": u.get("board_count"), "pins": u.get("pin_count")}


@server.tool(description="List the owner's boards. Pass 'bookmark' from a previous call to get the next page.")
def list_boards(page_size: int = 50, bookmark: str | None = None) -> dict:
    r = _call("GET", "/boards", {"page_size": min(max(page_size, 1), 250), "bookmark": bookmark})
    return {"boards": [_board_short(b) for b in r.get("items", [])], "bookmark": r.get("bookmark")}


@server.tool(description="List the pins on one board, with image links. Pass 'bookmark' for the next page.")
def list_board_pins(board_id: str, page_size: int = 50, bookmark: str | None = None) -> dict:
    r = _call("GET", f"/boards/{board_id}/pins",
              {"page_size": min(max(page_size, 1), 250), "bookmark": bookmark})
    return {"pins": [_pin_short(p) for p in r.get("items", [])], "bookmark": r.get("bookmark")}


@server.tool(description="Get one pin, with its image link.")
def get_pin(pin_id: str) -> dict:
    return _pin_short(_call("GET", f"/pins/{pin_id}"))


@server.tool(description="Save a pin's image to a local folder. Returns the saved file path.")
def save_pin_image(pin_id: str, folder: str) -> str:
    pin = _call("GET", f"/pins/{pin_id}")
    url = _image_url(pin)
    if not url:
        raise PinterestError("This pin has no image to save (it may be a video or a carousel).")
    d = Path(folder)
    d.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
    safe = "".join(ch for ch in (pin.get("title") or "pin") if ch not in '<>:"/\\|?*').strip()[:60] or "pin"
    dest = d / f"{safe} (pin {pin_id}){ext}"
    with httpx.Client(timeout=60, follow_redirects=True) as c:
        r = c.get(url)
        r.raise_for_status()
    dest.write_bytes(r.content)
    return str(dest)


@server.tool(description="Make a new board. privacy is PUBLIC or SECRET (default SECRET).")
def create_board(name: str, description: str = "", privacy: str = "SECRET") -> dict:
    return _board_short(_call("POST", "/boards",
                              body={"name": name, "description": description, "privacy": privacy.upper()}))


@server.tool(description=("Pin an image to a board. 'image' is a web address (https://...) or a file on "
                          "this computer (jpg/png, under 10 MB). title, description, link and alt_text are optional."))
def create_pin(board_id: str, image: str, title: str = "", description: str = "",
               link: str = "", alt_text: str = "") -> dict:
    if image.lower().startswith(("http://", "https://")):
        media = {"source_type": "image_url", "url": image}
    else:
        p = Path(image)
        if not p.is_file():
            raise PinterestError(f"No file at {image}")
        if p.stat().st_size > 10 * 1024 * 1024:
            raise PinterestError("That file is over 10 MB; make a smaller copy first.")
        ctype = mimetypes.guess_type(p.name)[0] or "image/jpeg"
        if ctype not in ("image/jpeg", "image/png"):
            raise PinterestError("Pinterest takes jpg or png files here.")
        media = {"source_type": "image_base64", "content_type": ctype,
                 "data": base64.b64encode(p.read_bytes()).decode("ascii")}
    body = {"board_id": board_id, "media_source": media}
    for k, v in (("title", title), ("description", description), ("link", link), ("alt_text", alt_text)):
        if v:
            body[k] = v
    return _pin_short(_call("POST", "/pins", body=body))


if __name__ == "__main__":
    server.run()
