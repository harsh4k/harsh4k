"""Draws every image the profile README shows, into assets/.

    python3 scripts/build.py

With GITHUB_TOKEN set it first refreshes assets/github.json (contribution
calendar, repos, stars, languages) from the GitHub API; without one it redraws
from the saved file. The daily workflow (.github/workflows/refresh.yml) runs
it with a token. Needs fontTools and brotli (pip install fonttools brotli).

Text is drawn as outlines from the fonts in src/fonts, so it renders the same
for everyone. Animation is CSS that switches off under prefers-reduced-motion.
"""
import datetime as dt
import html
import json
import math
import os
import re
import urllib.request

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
ASSETS = os.path.join(ROOT, "assets")
DATA = os.path.join(ASSETS, "github.json")
USER = "harsh4k"

RED, INK, CREAM = "#F40C3F", "#160000", "#FFF0EB"
W = 1280

THEMES = {
    "dark": dict(bg="#0d1117", cell="#161b22", fg="#f0ece6", dim="#8b949e", edge="#262c36", empty="#1d232c"),
    "light": dict(bg="#ffffff", cell="#f6f3ef", fg="#16110f", dim="#6e6a65", edge="#e7e1da", empty="#ece6df"),
}
# GitHub's 0-4 activity levels, in the site's red.
LEVELS = ["", "#5c1020", "#8f1430", "#c80f39", RED]
LEVELS_LIGHT = ["", "#fcc5d1", "#f98aa3", "#f64a70", RED]

# What the cards say. Stars come from the API; everything else is written here.
PROJECTS = [
    dict(slug="getcited", name="GetCited", repo="Getcited", url="https://github.com/harsh4k/Getcited",
         line="AI search visibility audits for websites", tag="Hackathon top 17", stack="Next.js · Supabase · CLIP"),
    dict(slug="bunny-os", name="Bunny OS", repo="Bunny-OS", url="https://github.com/harsh4k/Bunny-OS",
         line="Local voice assistant for Windows and macOS", tag="Desktop app", stack="Tauri · Rust · Python"),
    dict(slug="velsaro", name="Velsaro", repo=None, url="https://www.velsaro.in/",
         line="E-commerce store for an Indian attar house", tag="Live store", stack="React · TypeScript · Razorpay"),
    dict(slug="late-apex", name="Late Apex", repo="apexfr", url="https://github.com/harsh4k/apexfr",
         line="Studio site with scroll-driven night footage", tag="Motion design", stack="HTML · CSS · JS · Playwright"),
    dict(slug="rudo", name="Rudo", repo="rudo", url="https://github.com/harsh4k/rudo",
         line="AI assistant that lives in your terminal", tag="Local AI", stack="Python · Ollama · RAG"),
    dict(slug="nexcart", name="Nexcart", repo="nexcart", url="https://github.com/harsh4k/nexcart",
         line="Storefront for audio gear", tag="E-commerce", stack="React · TypeScript · Vite"),
    dict(slug="shipd", name="Shipd", repo="shipd", url="https://github.com/harsh4k/shipd",
         line="Daily dev report for Windows, all local", tag="CLI", stack="PowerShell · zero deps"),
    dict(slug="loom", name="Loom", repo="loom", url="https://github.com/harsh4k/loom",
         line="Local automation hub that runs on Ollama", tag="Automation", stack="Node.js · Electron · Ollama"),
]
STACK = ["React", "Next.js", "TypeScript", "Node.js", ".NET", "Python", "Flask", "SQL", "REST APIs", "LLMs", "Three.js", "Tauri"]
INTERESTS = ["gaming", "anime", "Marvel", "sci-fi", "football", "volleyball",
             "Ghost of Tsushima", "space visuals"]
STATUS_LINES = ["web apps people use", "WebGL scroll sites", "local-first AI tools", "fast, tested UIs"]


# ---------------------------------------------------------------- data

def graphql(query, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": USER},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        body = json.load(res)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def refresh(token):
    q = """{ user(login: "%s") {
      contributionsCollection { contributionCalendar { totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } } } }
      repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) { totalCount
        nodes { name stargazerCount
          languages(first: 8, orderBy: {field: SIZE, direction: DESC}) { edges { size node { name color } } } } } } }""" % USER
    user = graphql(q, token)["user"]
    level = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
    cal = user["contributionsCollection"]["contributionCalendar"]
    days = [[d["date"], d["contributionCount"], level[d["contributionLevel"]]]
            for w in cal["weeks"] for d in w["contributionDays"]]
    langs, stars = {}, {}
    for r in user["repositories"]["nodes"]:
        stars[r["name"]] = r["stargazerCount"]
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or "#888"])[0] += e["size"]
    data = dict(updated=dt.date.today().isoformat(), total=cal["totalContributions"], days=days,
                repos=user["repositories"]["totalCount"], stars=stars,
                languages=sorted(([k, v[0], v[1]] for k, v in langs.items()), key=lambda x: -x[1]))
    with open(DATA, "w") as f:
        json.dump(data, f, indent=1)
    return data


def load():
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        try:
            return refresh(token)
        except Exception as error:
            # In the workflow, fail loudly rather than quietly keep stale data.
            if os.environ.get("CI"):
                raise
            print(f"refresh failed, drawing from the saved data: {error}")
    with open(DATA) as f:
        return json.load(f)


def streaks(days):
    """Current streak (today may still be empty) and longest streak, in days."""
    longest = run = 0
    for _, count, _ in days:
        run = run + 1 if count else 0
        longest = max(longest, run)
    current, i = 0, len(days) - 1
    if i >= 0 and days[i][1] == 0:
        i -= 1
    while i >= 0 and days[i][1]:
        current, i = current + 1, i - 1
    return current, longest


# ---------------------------------------------------------------- drawing helpers

class Face:
    """One font, drawn as outlines. Text in an <img>-loaded SVG can come out
    blank when the browser rasterises before an embedded font is ready, so no
    text is left as text: every string becomes a path."""

    def __init__(self, file):
        self.font = TTFont(os.path.join(SRC, "fonts", file))
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm
        self.hmtx = self.font["hmtx"]

    def path(self, s, size, spacing):
        """Path data for s with its baseline at y=0 starting at x=0, and its width."""
        k = size / self.upm
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        x, extra = 0.0, []
        for i, ch in enumerate(s):
            if ch in SYMBOLS:
                pts = " ".join(f"{x + px * size / 1000:.1f},{-py * size / 1000:.1f}" for px, py in SYMBOLS[ch])
                extra.append(f"M{pts}Z")
                advance = 760 * size / 1000
            else:
                name = self.cmap.get(ord(ch)) or self.cmap.get(ord("?"))
                self.glyphs[name].draw(TransformPen(pen, (k, 0, 0, -k, x, 0)))
                advance = self.hmtx[name][0] * k
            x += advance + (spacing if i < len(s) - 1 else 0)
        return pen.getCommands() + "".join(extra), x


def _star():
    pts = []
    for i in range(10):
        r = 360 if i % 2 == 0 else 150
        a = math.pi / 2 + i * math.pi / 5
        pts.append((380 + r * math.cos(a), 300 + r * math.sin(a)))
    return pts


# Characters the fonts lack, as polygons in a 1000-unit em with y up.
SYMBOLS = {
    "★": _star(),
    # A north-east arrow: shaft and head as one outline.
    "↗": [(130, 60), (480, 410), (480, 230), (570, 230), (570, 570), (230, 570), (230, 480), (410, 480), (60, 130)],
}

FACES = {
    "WM": "Audiowide-Regular.woff2",
    "Disp": "BigShouldersDisplay-Bold.woff2",
    "Mono": "IBMPlexMono-Regular.woff2",
    "MonoB": "IBMPlexMono-Bold.woff2",
}
_loaded = {}
REDUCED = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


def svg(h, body, css, w=W, title=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img">'
            f"<title>{html.escape(title)}</title><style>{css}{REDUCED}</style>{body}</svg>")


def esc(s):
    return html.escape(str(s))


def text(x, y, s, size, family="Mono", fill=None, anchor=None, cls=None, spacing=None):
    face = _loaded.get(family) or _loaded.setdefault(family, Face(FACES[family]))
    gap = float(spacing.rstrip("em")) * size if spacing else 0
    d, width = face.path(str(s), size, gap)
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    c = f' class="{cls}"' if cls else ""
    f = f' fill="{fill}"' if fill else ""
    return f'<path transform="translate({x:.1f} {y:.1f})"{c}{f} d="{d}"/>'


def cell(x, y, w, h, t, fill=None):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="{fill or t["cell"]}" '
            f'stroke="{t["edge"] if not fill else fill}" stroke-width="1.5"/>')


def label(x, y, s, t):
    return text(x, y, s.upper(), 13, fill=t["dim"], spacing=".16em")


def face(x, y, size):
    """The mascot face, winking every few seconds. Black and white on any background."""
    def inner(name, suffix):
        with open(os.path.join(SRC, "faces", name)) as f:
            s = f.read()
        s = re.sub(r"^<svg[^>]*>", "", s).rsplit("</svg>", 1)[0]
        s = re.sub(r"<title>.*?</title>", "", s)
        return s.replace('id="ink"', f'id="ink{suffix}"').replace("url(#ink)", f"url(#ink{suffix})")
    box = f'x="{x}" y="{y}" width="{size}" height="{size}" viewBox="400 330 640 640"'
    return (f'<g class="bob"><svg {box} class="open">{inner("face.svg", "a")}</svg>'
            f'<svg {box} class="wink">{inner("face-wink.svg", "b")}</svg></g>')


FACE_CSS = (".wink{opacity:0;animation:wink 5s infinite}.open{animation:open 5s infinite}"
            "@keyframes wink{0%,86%,96%,100%{opacity:0}88%,94%{opacity:1}}"
            "@keyframes open{0%,86%,96%,100%{opacity:1}88%,94%{opacity:0}}"
            ".bob{animation:bob 4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}"
            "@keyframes bob{0%,100%{transform:translateY(0) rotate(-3deg)}50%{transform:translateY(-6px) rotate(3deg)}}")


def terrain(w, h, y0, rows=12, cols=48, amp=30, color=INK, opacity=0.45):
    """Wire terrain lines, the portfolio hero's motif."""
    out = []
    for r in range(rows):
        z = 1 + r * 0.55
        pts = []
        for c in range(cols + 1):
            u = c / cols * 2 - 1
            x3 = u * 9
            hgt = math.sin(x3 * 0.9 + r * 0.45) * 0.6 + math.sin(x3 * 0.37 - r * 0.8) * 0.8 + math.cos(x3 * 1.7 + r * 0.3) * 0.25
            px = w / 2 + (u * w * 1.1) / (z * 0.35 + 0.65)
            py = y0 + (h - y0) * (1 - 1 / z) * 1.25 - hgt * math.exp(-((u * 1.4) ** 2)) * amp / z
            pts.append(f"{px:.1f},{py:.1f}")
        out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
                   f'stroke-width="{1.4 / (1 + r * 0.08):.2f}" opacity="{opacity * (1 - r / rows * 0.75):.2f}"/>')
    return f'<g class="drift">{"".join(out)}</g>'


# ---------------------------------------------------------------- the bento

# Real logos (Simple Icons, CC0) and a few line icons for generic things (Lucide, ISC),
# vendored by name in src/icons/icons.json so the build needs no network.
with open(os.path.join(ROOT, "src", "icons", "icons.json")) as f:
    LOGOS = json.load(f)


def _luma(color):
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _readable(color, t):
    """The brand colour, or the theme's text colour when the brand colour would vanish on the card."""
    a, b = sorted((_luma(color), _luma(t["cell"])))
    return color if (b + 0.05) / (a + 0.05) >= 2.2 else t["fg"]


def logo(x, y, size, name, t, fallback=None):
    """The tool's real logo, size px square at x, y. Unknown names get a dot in the fallback colour."""
    icon = LOGOS.get(name)
    k = size / 24
    if icon is None:
        return f'<circle cx="{x + size / 2}" cy="{y + size / 2}" r="{size / 3}" fill="{fallback or t["dim"]}"/>'
    if icon["kind"] == "brand":
        return (f'<path transform="translate({x} {y}) scale({k:.3f})" fill="{_readable(icon["hex"], t)}" '
                f'd="{icon["path"]}"/>')
    return (f'<g transform="translate({x} {y}) scale({k:.3f})" fill="none" stroke="{t["fg"]}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{icon["inner"]}</g>')


def bento(mode, data):
    t = THEMES[mode]
    current, longest = streaks(data["days"])
    css = (FACE_CSS +
           ".drift{animation:drift 9s ease-in-out infinite alternate}"
           "@keyframes drift{from{transform:translateX(-30px)}to{transform:translateX(30px)}}"
           ".rot{opacity:0;animation:rot 12s infinite}"
           "@keyframes rot{0%{opacity:0;transform:translateY(14px)}3%,22%{opacity:1;transform:none}25%,100%{opacity:0;transform:translateY(-14px)}}"
           ".pop{opacity:0;animation:pop .6s ease-out forwards;transform-box:fill-box;transform-origin:left center}"
           "@keyframes pop{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}"
           ".grow{transform:scaleX(0);transform-box:fill-box;transform-origin:left;animation:grow 1.2s cubic-bezier(.2,.8,.2,1) .3s forwards}"
           "@keyframes grow{to{transform:scaleX(1)}}"
           ".shine{animation:shine 3.5s ease-in-out infinite}"
           "@keyframes shine{0%,60%{transform:translateX(-300px)}100%{transform:translateX(420px)}}"
           ".marq{animation:marq 28s linear infinite}@keyframes marq{to{transform:translateX(-50%)}}")
    b = []
    # Row 1: hello (red) | latest push + hackathon
    b.append(cell(0, 0, 820, 400, t, RED))
    b.append('<clipPath id="hero"><rect width="820" height="400" rx="22"/></clipPath>')
    b.append(f'<g clip-path="url(#hero)">{terrain(820, 400, 230)}</g>')
    b.append(face(36, 32, 132))
    b.append(text(40, 248, "HEY, I'M HARSHIT", 104, "Disp", INK))
    b.append(text(42, 298, "Software developer from Mumbai, India.", 22, "Mono", INK))
    b.append(text(42, 352, "I build", 22, "MonoB", INK))
    for i, s in enumerate(STATUS_LINES):
        b.append(f'<g class="rot" style="animation-delay:{i * 3}s">{text(150, 352, s, 22, "MonoB", INK)}</g>')

    b.append(cell(840, 0, 440, 190, t))
    b.append(label(870, 42, "Words I code by", t))
    b.append(text(868, 96, "SOMETIMES YOU GOTTA RUN", 37, "Disp", t["fg"]))
    b.append(text(868, 138, "BEFORE YOU CAN WALK.", 37, "Disp", RED))
    b.append(text(870, 172, "Tony Stark, Iron Man (2008)", 16, "Mono", t["dim"]))

    b.append(cell(840, 210, 440, 190, t))
    b.append('<clipPath id="hk"><rect x="840" y="210" width="440" height="190" rx="22"/></clipPath>')
    b.append(f'<g clip-path="url(#hk)"><rect class="shine" x="840" y="210" width="90" height="190" fill="{RED}" opacity=".12" transform="skewX(-20)"/></g>')
    b.append(label(870, 252, "NamasteDev Hackathon 2026", t))
    b.append(text(866, 336, "TOP 17", 84, "Disp", RED))
    b.append(text(1100, 336, "winner", 22, "Mono", t["dim"]))

    # Row 2: numbers | languages | studying
    y = 420
    b.append(cell(0, y, 410, 300, t))
    b.append(label(30, y + 42, "On GitHub", t))
    stats = [(data["total"], "contributions this year"), (current, "day streak now"), (longest, "day best streak"),
             (data["repos"], "public repos")]
    for i, (n, what) in enumerate(stats):
        yy = y + 100 + i * 56
        b.append(f'<g class="pop" style="animation-delay:{.15 * i:.2f}s">'
                 + text(30, yy, f"{n:,}", 44, "Disp", RED if i == 0 else t["fg"])
                 + text(150, yy - 6, what, 18, "Mono", t["dim"]) + "</g>")

    b.append(cell(430, y, 430, 300, t))
    b.append(label(460, y + 42, "Languages in my repos", t))
    langs = data["languages"][:6]
    total = sum(x[1] for x in langs) or 1
    bx, bar = 460, ""
    for name, size, color in langs:
        wdt = 370 * size / total
        bar += f'<rect x="{bx:.1f}" y="{y + 66}" width="{max(wdt - 3, 1):.1f}" height="16" rx="3" fill="{color}"/>'
        bx += wdt
    b.append(f'<g class="grow">{bar}</g>')
    for i, (name, size, color) in enumerate(langs):
        lx, ly = 460 + (i % 2) * 190, y + 106 + (i // 2) * 60
        b.append(f'<g class="pop" style="animation-delay:{.6 + .1 * i:.2f}s">' + logo(lx + 4, ly + 4, 34, name, t, color)
                 + text(lx + 54, ly + 19, name, 18, "Mono", t["fg"])
                 + text(lx + 54, ly + 40, f"{100 * size / total:.0f}%", 14, "Mono", t["dim"]) + "</g>")

    b.append(cell(880, y, 400, 300, t))
    b.append(label(910, y + 42, "Studying", t))
    b.append(text(906, y + 118, "B.TECH", 64, "Disp", t["fg"]))
    b.append(text(906, y + 178, "COMPUTER ENGG.", 50, "Disp", t["fg"]))
    b.append(text(910, y + 222, "NMIMS Mumbai", 20, "Mono", t["dim"]))
    b.append(text(910, y + 268, "building since 2024", 16, "Mono", t["dim"]))

    # Row 3: stack chips, appearing one by one
    y = 740
    b.append(cell(0, y, W, 170, t))
    b.append(label(30, y + 42, "What I build with", t))
    x, yy = 30, y + 70
    for i, s in enumerate(STACK):
        wdt = 58 + len(s) * 10.6
        if x + wdt > W - 30:
            x, yy = 30, yy + 52
        b.append(f'<g class="pop" style="animation-delay:{.08 * i:.2f}s">'
                 f'<rect x="{x}" y="{yy}" width="{wdt}" height="40" rx="20" fill="none" stroke="{t["fg"]}" stroke-opacity=".35" stroke-width="1.5"/>'
                 + logo(x + 16, yy + 11, 18, s, t)
                 + text(x + 42, yy + 26, s, 17, "Mono", t["fg"]) + "</g>")
        x += wdt + 10

    # Row 4: interests marquee | portfolio
    y = 930
    b.append(cell(0, y, 820, 150, t))
    b.append(label(30, y + 42, "Off the clock", t))
    b.append(f'<clipPath id="mq"><rect x="1" y="{y + 60}" width="818" height="60"/></clipPath>')
    line = "  ·  ".join(INTERESTS) + "  ·  "
    b.append(f'<g clip-path="url(#mq)"><g class="marq">'
             + text(30, y + 102, line + line, 24, "Mono", t["fg"]) + "</g></g>")
    b.append(cell(840, y, 440, 150, t))
    b.append(label(870, y + 42, "Portfolio", t))
    b.append(text(868, y + 104, "harshh.pages.dev ↗", 34, "WM", RED))
    return svg(1096, "".join(b), css, title="Harshit Chauhan, software developer")


# ---------------------------------------------------------------- contribution calendar

def activity(mode, data):
    t = THEMES[mode]
    levels = LEVELS if mode == "dark" else LEVELS_LIGHT
    days = data["days"][-371:]
    size, gap, x0, y0 = 18, 4, 30, 96
    first = dt.date.fromisoformat(days[0][0])
    offset = (first.weekday() + 1) % 7  # weeks start on Sunday, like GitHub
    cells = []
    for i, (date, count, level) in enumerate(days):
        k = i + offset
        col, row = divmod(k, 7)
        x, y = x0 + col * (size + gap), y0 + row * (size + gap)
        fill = levels[level] or t["empty"]
        delay = (col + row) * 0.02
        cells.append(f'<rect class="d" style="animation-delay:{delay:.2f}s" x="{x}" y="{y}" width="{size}" height="{size}" rx="4" fill="{fill}">'
                     f'<title>{count} on {date}</title></rect>')
    css = (".d{opacity:0;animation:in .4s ease-out forwards;transform-box:fill-box;transform-origin:center}"
           "@keyframes in{from{opacity:0;transform:scale(.3)}to{opacity:1;transform:none}}")
    width = x0 * 2 + 53 * (size + gap)
    legend = "".join(f'<rect x="{width - 30 - (5 - i) * 24}" y="34" width="18" height="18" rx="4" fill="{levels[i] or t["empty"]}"/>' for i in range(5))
    body = (cell(0, 0, W, 280, t) + label(30, 48, f"{data['total']:,} contributions in the last year", t)
            + text(width - 160, 48, "less", 13, "Mono", t["dim"], "end") + legend
            + text(width - 22, 48, "more", 13, "Mono", t["dim"])
            + f'<g transform="translate({(W - width) / 2:.0f} 0)">{"".join(cells)}</g>'
            + text(30, 268, "Sample data until the first refresh" if data["updated"] == "sample" else f"Updated {data['updated']}", 12, "Mono", t["dim"]))
    return svg(296, body, css, title=f"{data['total']} contributions in the last year")


# ---------------------------------------------------------------- project icons

ICONS = {
    # 64x64 line drawings, each with one small idle motion.
    "getcited": ('<path d="M10 14h44a6 6 0 0 1 6 6v22a6 6 0 0 1-6 6H30l-12 10V48h-8a6 6 0 0 1-6-6V20a6 6 0 0 1 6-6z"/>'
                 '<g class="a1"><path d="M22 36c0-6 2-9 6-11M34 36c0-6 2-9 6-11"/><circle cx="24" cy="36" r="3"/><circle cx="36" cy="36" r="3"/></g>',
                 ".a1{animation:nod 2.4s ease-in-out infinite}@keyframes nod{50%{transform:translateY(-3px)}}"),
    "bunny-os": ('<g class="earL"><path d="M24 30C18 18 18 6 23 4s9 10 8 24"/></g><g class="earR"><path d="M40 30c6-12 6-24 1-26s-9 10-8 24"/></g>'
                 '<ellipse cx="32" cy="44" rx="16" ry="14"/><circle cx="26" cy="42" r="2" fill="currentColor"/><circle cx="38" cy="42" r="2" fill="currentColor"/><path d="M30 49q2 2 4 0"/>',
                 ".earL{animation:ear 3s ease-in-out infinite;transform-origin:28px 30px}.earR{animation:ear 3s ease-in-out .3s infinite;transform-origin:36px 30px}"
                 "@keyframes ear{0%,70%,100%{transform:none}80%{transform:rotate(-12deg)}90%{transform:rotate(8deg)}}"),
    "velsaro": ('<rect x="18" y="26" width="28" height="32" rx="7"/><path d="M26 26v-6h12v6M28 20v-6h8v6"/><path d="M24 42h16"/>'
                '<g class="mist"><circle cx="50" cy="12" r="2"/><circle cx="56" cy="8" r="1.5"/><circle cx="56" cy="16" r="1.5"/></g>',
                ".mist{animation:mist 2.4s ease-out infinite}@keyframes mist{0%{opacity:0;transform:translate(-6px,4px)}40%{opacity:1}100%{opacity:0;transform:translate(4px,-4px)}}"),
    "late-apex": ('<path d="M6 12h52M24 12L12 58M40 12l12 46"/><path class="lane" d="M32 14v42" stroke-dasharray="6 6"/>',
                  ".lane{animation:lane .6s linear infinite}@keyframes lane{to{stroke-dashoffset:-12}}"),
    "rudo": ('<rect x="6" y="10" width="52" height="44" rx="6"/><path d="M6 20h52"/><path d="M16 32l8 6-8 6"/>'
             '<rect class="cur" x="30" y="42" width="12" height="4" fill="currentColor" stroke="none"/>',
             ".cur{animation:cur 1s steps(1) infinite}@keyframes cur{50%{opacity:0}}"),
    "nexcart": ('<path d="M12 38v-6a20 20 0 0 1 40 0v6"/><rect x="8" y="36" width="10" height="18" rx="4"/><rect x="46" y="36" width="10" height="18" rx="4"/>'
                '<g class="note"><path d="M30 30v-10l8-2v10"/><circle cx="28" cy="30" r="3"/><circle cx="36" cy="28" r="3"/></g>',
                ".note{animation:note 2s ease-in-out infinite}@keyframes note{50%{transform:translateY(-4px) rotate(-6deg)}}"),
    "shipd": ('<g class="rk"><path d="M32 6c10 8 12 22 8 34H24C20 28 22 14 32 6z"/><circle cx="32" cy="22" r="4"/><path d="M24 34l-8 8 8 2M40 34l8 8-8 2"/></g>'
              '<path class="fl" d="M28 46l4 12 4-12"/>',
              ".rk{animation:rk 1.8s ease-in-out infinite}@keyframes rk{50%{transform:translateY(-3px)}}"
              ".fl{animation:fl .4s ease-in-out infinite alternate;transform-origin:32px 46px}@keyframes fl{to{transform:scaleY(.6)}}"),
    "loom": ('<rect x="8" y="10" width="48" height="44" rx="6"/><path d="M16 10v44M24 10v44M32 10v44M40 10v44M48 10v44M8 44h48"/>'
             '<g class="sh"><rect x="10" y="24" width="20" height="8" rx="4" fill="currentColor"/></g>',
             ".sh{animation:sh 2.4s ease-in-out infinite alternate}@keyframes sh{to{transform:translateX(24px)}}"),
}


def card(mode, p, data):
    t = THEMES[mode]
    draw, motion = ICONS[p["slug"]]
    stars = data["stars"].get(p["repo"]) if p["repo"] else None
    where = "repo ↗" if p["repo"] else "live site ↗"
    meta = f"★ {stars}  ·  {where}" if stars else where
    body = (cell(1, 1, 618, 218, t)
            + f'<rect x="28" y="28" width="104" height="104" rx="24" fill="{RED}"/>'
            + f'<g transform="translate(40 40) scale(1.25)" fill="none" stroke="{INK}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" color="{INK}">{draw}</g>'
            + text(156, 62, p["tag"].upper(), 13, "Mono", RED, spacing=".14em")
            + text(154, 118, p["name"].upper(), 56, "Disp", t["fg"])
            + text(30, 172, p["line"], 18, "Mono", t["fg"])
            + text(30, 200, p["stack"], 14, "Mono", t["dim"])
            + text(590, 200, meta, 14, "Mono", t["dim"], "end"))
    return svg(234, body, motion, w=620, title=f'{p["name"]}: {p["line"]}')


def footer(mode):
    t = THEMES[mode]
    body = (cell(0, 0, W, 120, t, INK) + face(40, 14, 92)
            + text(W / 2, 74, "HARSHIT CHAUHAN", 34, "WM", RED, "middle", spacing=".12em")
            + text(W - 40, 72, "thanks for stopping by", 16, "Mono", CREAM, "end"))
    return svg(120, body, FACE_CSS, title="Harshit Chauhan")


def main():
    data = load()
    os.makedirs(ASSETS, exist_ok=True)
    out = {}
    for mode in THEMES:
        out[f"bento-{mode}.svg"] = bento(mode, data)
        out[f"activity-{mode}.svg"] = activity(mode, data)
        out[f"footer-{mode}.svg"] = footer(mode)
        for p in PROJECTS:
            out[f"project-{p['slug']}-{mode}.svg"] = card(mode, p, data)
    for name, s in out.items():
        with open(os.path.join(ASSETS, name), "w") as f:
            f.write(s)
    print(f"wrote {len(out)} images, data from {data['updated']}")


if __name__ == "__main__":
    main()
