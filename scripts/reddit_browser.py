#!/usr/bin/env python3
"""Read subreddits through a real Firefox and save each one as a local RSS file.

Reddit ended RSS on 13 Nov 2026. This drives Firefox (headless, its own profile)
over Firefox's built-in Marionette port, reads the posts off the page, and writes
data/reddit/<sub>.xml. Standard library only; no Selenium or geckodriver.

    python3 scripts/reddit_browser.py LocalLLaMA comfyui ukpolitics
    python3 scripts/reddit_browser.py --login     # visible window, sign in once
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "data" / "firefox-reddit"
OUT = ROOT / "data" / "reddit"
FIREFOX = "/Applications/Firefox.app/Contents/MacOS/firefox"
PORT = 2829          # not the default 2828, so it never clashes with another Firefox
WANT = 25           # posts per subreddit
PAGE_GAP = 15        # seconds between subreddits: a person's pace, not a crawler's

# Runs in the page: new Reddit renders each post as a <shreddit-post> element.
EXTRACT = """
const out = [];
for (const p of document.querySelectorAll('shreddit-post')) {
  const body = p.querySelector('[slot="text-body"]');
  out.push({
    title: p.getAttribute('post-title') || '',
    link: 'https://www.reddit.com' + (p.getAttribute('permalink') || ''),
    url: p.getAttribute('content-href') || '',
    author: p.getAttribute('author') || '',
    created: p.getAttribute('created-timestamp') || '',
    score: p.getAttribute('score') || '',
    comments: p.getAttribute('comment-count') || '',
    text: body ? body.innerText.trim().slice(0, 4000) : '',
  });
}
return out;
"""


class Marionette:
    """Minimal client for Firefox's Marionette protocol: length-prefixed JSON over TCP."""

    def __init__(self, port: int):
        for _ in range(60):
            try:
                self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
                break
            except OSError:
                time.sleep(0.5)
        else:
            raise RuntimeError("Firefox did not open its Marionette port")
        self.buf = b""
        self.n = 0
        self._read()  # server hello
        self.cmd("WebDriver:NewSession", {"capabilities": {"pageLoadStrategy": "normal"}})

    def _read(self):
        while b":" not in self.buf:
            self.buf += self.s.recv(65536)
        size, _, rest = self.buf.partition(b":")
        size = int(size)
        while len(rest) < size:
            rest += self.s.recv(65536)
        msg, self.buf = rest[:size], rest[size:]
        return json.loads(msg)

    def cmd(self, name: str, params: dict | None = None):
        self.n += 1
        data = json.dumps([0, self.n, name, params or {}]).encode()
        self.s.sendall(str(len(data)).encode() + b":" + data)
        _, _, err, result = self._read()
        if err:
            raise RuntimeError(f"{name}: {err.get('error')}: {err.get('message')}")
        return result.get("value") if isinstance(result, dict) else result


def launch(headless: bool) -> subprocess.Popen:
    PROFILE.mkdir(parents=True, exist_ok=True)
    (PROFILE / "user.js").write_text(f'user_pref("marionette.port", {PORT});\n')
    args = [FIREFOX, "--marionette", "--no-remote", "--profile", str(PROFILE)]
    if headless:
        args.append("--headless")
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def read_sub(m: Marionette, sub: str) -> list[dict]:
    m.cmd("WebDriver:Navigate", {"url": f"https://www.reddit.com/r/{sub}/new/"})
    for _ in range(20):  # posts render after load; wait up to ~10s
        posts = m.cmd("WebDriver:ExecuteScript", {"script": EXTRACT, "args": []})
        if posts:
            break
        time.sleep(0.5)
    else:
        title = m.cmd("WebDriver:GetTitle")
        raise RuntimeError(f"no posts found on r/{sub} (page title: {title!r})")
    # Reddit loads more posts as you scroll; scroll like a reader until we have enough.
    for _ in range(8):
        if len(posts) >= WANT:
            break
        m.cmd("WebDriver:ExecuteScript", {"script": "window.scrollTo(0, document.body.scrollHeight)", "args": []})
        time.sleep(2)
        more = m.cmd("WebDriver:ExecuteScript", {"script": EXTRACT, "args": []})
        if len(more) <= len(posts):
            break
        posts = more
    return posts[:WANT]


def to_rss(sub: str, posts: list[dict]) -> str:
    items = []
    for p in posts:
        try:
            when = format_datetime(datetime.fromisoformat(p["created"].replace("Z", "+00:00")))
        except ValueError:
            when = ""
        desc = p["text"] or p["url"]
        extra = f'\n\n{p["score"]} points, {p["comments"]} comments, by u/{p["author"]}'
        items.append(
            f"<item><title>{escape(p['title'])}</title><link>{escape(p['link'])}</link>"
            f"<guid>{escape(p['link'])}</guid><pubDate>{when}</pubDate>"
            f"<description>{escape(desc + extra)}</description></item>")
    now = format_datetime(datetime.now(timezone.utc))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>r/{escape(sub)}</title><link>https://www.reddit.com/r/{escape(sub)}/new/</link>"
            f"<description>Read from the page by reddit_browser.py</description><lastBuildDate>{now}</lastBuildDate>\n"
            + "\n".join(items) + "\n</channel></rss>\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subs", nargs="*")
    ap.add_argument("--login", action="store_true", help="open a visible window to sign in once")
    a = ap.parse_args(argv)

    if a.login:
        launch(headless=False).wait()
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    ff = launch(headless=True)
    failed = 0
    try:
        m = Marionette(PORT)
        for i, sub in enumerate(a.subs):
            if i:
                time.sleep(PAGE_GAP)
            try:
                posts = read_sub(m, sub)
                (OUT / f"{sub}.xml").write_text(to_rss(sub, posts))
                print(f"[reddit] r/{sub}: {len(posts)} posts")
            except Exception as ex:  # one bad sub must not stop the rest
                failed += 1
                print(f"[reddit] r/{sub}: FAILED {ex}", file=sys.stderr)
        try:
            m.cmd("Marionette:Quit")
        except Exception:
            pass
    finally:
        try:
            ff.wait(timeout=15)
        except subprocess.TimeoutExpired:
            ff.kill()
    return 1 if failed and failed == len(a.subs) else 0


if __name__ == "__main__":
    sys.exit(main())
