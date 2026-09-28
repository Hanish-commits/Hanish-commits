"""
generate_dashboard.py

Pulls live data from the GitHub API and builds a KPI-hub style dashboard SVG
(assets/orbit_stats.svg), plus updates the chapter tracker section inside
README.md by scanning the DataScienceBy-Hanish repo's real folder structure.

Every number on the dashboard is real, pulled live from the GitHub API -
no placeholder or fabricated metrics.

Runs inside GitHub Actions, authenticated with the built-in GITHUB_TOKEN.
"""

import os
import re
import math
import base64
from html import escape
import requests
from datetime import datetime

USERNAME = "Hanish-commits"
DIARY_REPO = "DataScienceBy-Hanish"
TOKEN = os.environ["GH_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

PALETTE = {
    "bg": "#0a0e14",
    "panel": "#131922",
    "border": "#1f2733",
    "text": "#E6EDF3",
    "muted": "#8B949E",
    "accent": "#00F5D4",
    "accent2": "#7C5CFC",
    "accent3": "#FFD166",
    "accent4": "#DD865F",
}
FONT_HEAD = "'Segoe UI', -apple-system, system-ui, sans-serif"
FONT_MONO = "'JetBrains Mono', 'Fira Code', monospace"


def xml(value):
    """Escape live GitHub values before adding them to SVG markup."""
    return escape(str(value), quote=True)


def portrait_data_uri():
    """Embed the profile portrait so README SVGs remain self-contained."""
    with open("assets/hanish-profile.jpg", "rb") as photo:
        encoded = base64.b64encode(photo.read()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def fetch_user_stats():
    """Pull real numbers straight from the GitHub API - no third-party service."""
    user = requests.get(f"https://api.github.com/users/{USERNAME}", headers=HEADERS).json()
    repos = requests.get(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=100", headers=HEADERS
    ).json()

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_repos = user.get("public_repos", len(repos))
    followers = user.get("followers", 0)

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { contributionCount }
            }
          }
        }
      }
    }
    """
    gql = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {"login": USERNAME}},
        headers=HEADERS,
    ).json()
    calendar = (
        gql.get("data", {})
        .get("user", {})
        .get("contributionsCollection", {})
        .get("contributionCalendar", {})
    )
    total_contributions = calendar.get("totalContributions", 0)

    # Last 12 weeks of contribution totals, for the activity bar chart
    weeks = calendar.get("weeks", [])
    weekly_totals = [
        sum(day["contributionCount"] for day in w["contributionDays"])
        for w in weeks
    ][-12:]

    # Language mix across public repos, for the pie chart
    lang_counts = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

    # Most recently updated repos, for the activity table
    recent = sorted(repos, key=lambda r: r.get("updated_at", ""), reverse=True)[:5]
    recent_rows = [
        {
            "name": r["name"],
            "language": r.get("language") or "-",
            "stars": r.get("stargazers_count", 0),
            "updated": r.get("updated_at", "")[:10],
        }
        for r in recent
    ]

    return {
        "repos": total_repos,
        "stars": total_stars,
        "followers": followers,
        "contributions": total_contributions,
        "weekly": weekly_totals,
        "languages": lang_counts,
        "recent": recent_rows,
    }


def fetch_diary_structure():
    """Recursively scan DataScienceBy-Hanish for real chapter progress."""
    url = f"https://api.github.com/repos/{USERNAME}/{DIARY_REPO}/git/trees/main?recursive=1"
    tree = requests.get(url, headers=HEADERS).json().get("tree", [])

    topics = {}
    for item in tree:
        if item["type"] != "blob":
            continue
        path = item["path"]
        parts = path.split("/")
        if len(parts) >= 2 and (path.endswith(".py") or path.endswith(".md")):
            topic = parts[-2]
            topics.setdefault(topic, 0)
            topics[topic] += 1

    return topics


def build_tracker_markdown(topics):
    if not topics:
        return "_No chapters detected yet - keep building!_"

    max_count = max(topics.values())
    lines = []
    for topic, count in sorted(topics.items()):
        filled = round((count / max_count) * 20)
        bar = "█" * filled + "░" * (20 - filled)
        clean_name = re.sub(r"^\d+[_ ]*", "", topic).replace("_", " ")
        lines.append(f"`{bar}` **{clean_name}** ({count} files)")

    return "\n\n".join(lines)


def update_readme(tracker_md):
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    new_section = (
        "<!-- CHAPTER-TRACKER-START -->\n"
        f"{tracker_md}\n"
        "<!-- CHAPTER-TRACKER-END -->"
    )
    content = re.sub(
        r"<!-- CHAPTER-TRACKER-START -->.*?<!-- CHAPTER-TRACKER-END -->",
        new_section,
        content,
        flags=re.DOTALL,
    )

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# SVG dashboard
# ---------------------------------------------------------------------------

def build_portfolio_hero_svg(theme="dark", portrait_uri=None):
    """Create the portrait-led, self-contained hero used in the profile README."""
    portrait_uri = portrait_uri or portrait_data_uri()
    if theme == "light":
        bg, fg, muted, overlay = "#eeece6", "#181916", "#5f625d", "#eeece6"
    else:
        bg, fg, muted, overlay = "#111210", "#f2f0e9", "#c0beb5", "#111210"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="330" viewBox="0 0 1200 330">
<defs><linearGradient id="fade" x1="0" y1="0" x2="1" y2="0"><stop stop-color="{overlay}"/><stop offset=".42" stop-color="{overlay}" stop-opacity=".96"/><stop offset=".76" stop-color="{overlay}" stop-opacity=".20"/><stop offset="1" stop-color="{overlay}" stop-opacity=".05"/></linearGradient><linearGradient id="bottom" x1="0" y1="0" x2="0" y2="1"><stop offset=".45" stop-color="{bg}" stop-opacity="0"/><stop offset="1" stop-color="{bg}" stop-opacity=".45"/></linearGradient></defs>
<rect width="1200" height="330" rx="12" fill="{bg}"/><image href="{portrait_uri}" x="520" y="0" width="680" height="330" preserveAspectRatio="xMidYMid slice"/><rect width="1200" height="330" rx="12" fill="url(#fade)"/><rect width="1200" height="330" rx="12" fill="url(#bottom)"/><path d="M1 50H1199" stroke="{fg}" stroke-opacity=".16"/>
<rect x="28" y="16" width="19" height="19" fill="{fg}"/><text x="33" y="31" font-family="Georgia,serif" font-size="15" fill="{bg}">H</text><text x="775" y="31" font-family="monospace" font-size="9" letter-spacing="2" fill="{fg}">HOME</text><text x="856" y="31" font-family="monospace" font-size="9" letter-spacing="2" fill="{fg}">WORK</text><text x="940" y="31" font-family="monospace" font-size="9" letter-spacing="2" fill="{fg}">ABOUT</text><text x="1031" y="31" font-family="monospace" font-size="9" letter-spacing="2" fill="{fg}">GITHUB ↗</text>
<text x="64" y="113" font-family="monospace" font-size="10" letter-spacing="2.5" fill="{PALETTE['accent4']}">PORTFOLIO / DATA SCIENCE</text><text x="60" y="178" font-family="Georgia,serif" font-size="47" fill="{fg}">Learning in public.</text><text x="60" y="231" font-family="Georgia,serif" font-size="47" fill="{fg}">Building with data.</text><text x="64" y="273" font-family="monospace" font-size="10" letter-spacing="2" fill="{muted}">HANISH SHARMA · PYTHON &amp; DATA SCIENCE</text><text x="65" y="310" font-family="Arial,sans-serif" font-size="20" fill="{fg}">↓</text></svg>'''


def _kpi_card(x, y, w, h, label, value, color):
    return f'''
<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
<text x="{x + w/2}" y="{y + 32}" font-family="{FONT_HEAD}" font-size="12" font-weight="600"
      fill="{PALETTE['muted']}" text-anchor="middle" letter-spacing="0.5">{xml(label)}</text>
<text x="{x + w/2}" y="{y + 65}" font-family="{FONT_MONO}" font-size="30"
      font-weight="700" fill="{color}" text-anchor="middle">{xml(value)}</text>
'''


def _panel_frame(x, y, w, h, title):
    return f'''
<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{PALETTE['panel']}" stroke="{PALETTE['border']}"/>
<text x="{x + 20}" y="{y + 32}" font-family="{FONT_HEAD}" font-size="14"
      font-weight="600" fill="{PALETTE['text']}" letter-spacing="0.3">{xml(title)}</text>
'''


def _progress_panel(x, y, w, h, topics):
    parts = [_panel_frame(x, y, w, h, "LEARNING PIPELINE")]
    if not topics:
        parts.append(
            f'<text x="{x+20}" y="{y+60}" font-family="Fira Code, monospace" '
            f'font-size="13" fill="{PALETTE["muted"]}">No chapters detected yet</text>'
        )
        return "".join(parts)

    max_count = max(topics.values())
    row_h = min(46, (h - 60) / max(len(topics), 1))
    for i, (topic, count) in enumerate(sorted(topics.items())):
        row_y = y + 55 + i * row_h
        clean_name = re.sub(r"^\d+[_ ]*", "", topic).replace("_", " ").title()
        bar_w = (w - 140) * (count / max_count)
        parts.append(
            f'<text x="{x+20}" y="{row_y}" font-family="Fira Code, monospace" '
            f'font-size="12" fill="{PALETTE["text"]}">{xml(clean_name)}</text>'
        )
        parts.append(
            f'<rect x="{x+20}" y="{row_y+8}" width="{w-140}" height="8" rx="4" fill="{PALETTE["border"]}"/>'
        )
        parts.append(
            f'<rect x="{x+20}" y="{row_y+8}" width="{bar_w:.1f}" height="8" rx="4" fill="{PALETTE["accent"]}"/>'
        )
        parts.append(
            f'<text x="{x+w-20}" y="{row_y}" font-family="Fira Code, monospace" '
            f'font-size="12" fill="{PALETTE["muted"]}" text-anchor="end">{count}</text>'
        )
    return "".join(parts)


def _weekly_bar_panel(x, y, w, h, weekly):
    parts = [_panel_frame(x, y, w, h, "WEEKLY CONTRIBUTIONS (LAST 12 WEEKS)")]
    if not weekly:
        return "".join(parts)

    chart_x, chart_y = x + 20, y + 50
    chart_w, chart_h = w - 40, h - 80
    max_val = max(weekly) or 1
    bar_gap = 8
    bar_w = (chart_w - bar_gap * (len(weekly) - 1)) / len(weekly)

    for i, val in enumerate(weekly):
        bar_h = (val / max_val) * chart_h
        bx = chart_x + i * (bar_w + bar_gap)
        by = chart_y + chart_h - bar_h
        parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'rx="3" fill="{PALETTE["accent"]}" opacity="0.85"/>'
        )
    parts.append(
        f'<line x1="{chart_x}" y1="{chart_y+chart_h}" x2="{chart_x+chart_w}" '
        f'y2="{chart_y+chart_h}" stroke="{PALETTE["border"]}"/>'
    )
    return "".join(parts)


def _language_pie_panel(x, y, w, h, languages):
    parts = [_panel_frame(x, y, w, h, "LANGUAGE MIX")]
    if not languages:
        parts.append(
            f'<text x="{x+20}" y="{y+60}" font-family="Fira Code, monospace" '
            f'font-size="13" fill="{PALETTE["muted"]}">No language data yet</text>'
        )
        return "".join(parts)

    colors = [PALETTE["accent"], PALETTE["accent2"], PALETTE["accent3"], PALETTE["accent4"], "#5BC0EB"]
    total = sum(languages.values())
    cx, cy, r = x + w * 0.30, y + h / 2 + 14, min(w, h) / 4.6

    start_angle = 0
    legend_y = y + 58
    top5 = sorted(languages.items(), key=lambda kv: -kv[1])[:5]

    for i, (lang, count) in enumerate(top5):
        frac = count / total
        end_angle = start_angle + frac * 360
        large_arc = 1 if (end_angle - start_angle) > 180 else 0

        x1 = cx + r * math.cos(math.radians(start_angle - 90))
        y1 = cy + r * math.sin(math.radians(start_angle - 90))
        x2 = cx + r * math.cos(math.radians(end_angle - 90))
        y2 = cy + r * math.sin(math.radians(end_angle - 90))
        color = colors[i % len(colors)]

        # Draw the wedge itself (this was missing before - only the legend
        # was ever rendered, so no pie shape actually appeared).
        if len(top5) == 1:
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/>')
        else:
            parts.append(
                f'<path d="M {cx},{cy} L {x1:.2f},{y1:.2f} '
                f'A {r},{r} 0 {large_arc} 1 {x2:.2f},{y2:.2f} Z" '
                f'fill="{color}" stroke="{PALETTE["bg"]}" stroke-width="1.5"/>'
            )

        # Legend
        parts.append(
            f'<rect x="{x+w*0.58}" y="{legend_y-11}" width="10" height="10" rx="2" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{x+w*0.58+18}" y="{legend_y}" font-family="{FONT_HEAD}" '
            f'font-size="12" font-weight="500" fill="{PALETTE["text"]}">{xml(lang)}</text>'
        )
        parts.append(
            f'<text x="{x+w-16}" y="{legend_y}" font-family="{FONT_MONO}" '
            f'font-size="12" fill="{PALETTE["muted"]}" text-anchor="end">{count}</text>'
        )
        legend_y += 24
        start_angle = end_angle

    return "".join(parts)


def _recent_table_panel(x, y, w, h, rows):
    parts = [_panel_frame(x, y, w, h, "RECENT ACTIVITY")]
    header_y = y + 48
    cols = [("REPO", x + 20), ("LANG", x + w * 0.45), ("STARS", x + w * 0.65), ("UPDATED", x + w * 0.8)]
    for label, cx in cols:
        parts.append(
            f'<text x="{cx}" y="{header_y}" font-family="Fira Code, monospace" '
            f'font-size="11" fill="{PALETTE["muted"]}">{label}</text>'
        )
    for i, row in enumerate(rows):
        ry = header_y + 26 + i * 24
        name = row["name"] if len(row["name"]) <= 20 else row["name"][:18] + "…"
        parts.append(
            f'<text x="{x+20}" y="{ry}" font-family="Fira Code, monospace" '
            f'font-size="12" fill="{PALETTE["text"]}">{xml(name)}</text>'
        )
        parts.append(
            f'<text x="{x+w*0.45}" y="{ry}" font-family="Fira Code, monospace" '
            f'font-size="12" fill="{PALETTE["accent"]}">{xml(row["language"])}</text>'
        )
        parts.append(
            f'<text x="{x+w*0.65}" y="{ry}" font-family="Fira Code, monospace" '
            f'font-size="12" fill="{PALETTE["text"]}">{xml(row["stars"])}</text>'
        )
        parts.append(
            f'<text x="{x+w*0.8}" y="{ry}" font-family="Fira Code, monospace" '
            f'font-size="12" fill="{PALETTE["muted"]}">{xml(row["updated"])}</text>'
        )
    return "".join(parts)


def build_dashboard_svg(stats, topics, portrait_uri=None):
    width, height = 1200, 830
    portrait_uri = portrait_uri or portrait_data_uri()
    parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">',
        f'''<defs><linearGradient id="page" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#111210"/><stop offset="1" stop-color="#0b0e14"/></linearGradient><linearGradient id="teal" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#52cdb1"/><stop offset="1" stop-color="#70d8b3"/></linearGradient><clipPath id="portraitClip"><circle cx="1090" cy="86" r="36"/></clipPath></defs><rect width="{width}" height="{height}" rx="14" fill="url(#page)"/>''',
    ]

    # Editorial masthead with the profile portrait
    parts.append(
        f'<rect x="28" y="25" width="1144" height="122" rx="9" fill="#171815" stroke="#343431"/>'
        f'<image href="{portrait_uri}" x="758" y="25" width="414" height="122" preserveAspectRatio="xMidYMid slice" opacity="0.80"/>'
        f'<path d="M700 25H1172V147H700Z" fill="#111210" opacity="0.36"/>'
        f'<text x="58" y="65" font-family="{FONT_MONO}" font-size="10" letter-spacing="2" fill="{PALETTE["accent4"]}">PORTFOLIO / DATA SCIENCE</text>'
        f'<text x="58" y="103" font-family="Georgia, serif" font-size="31" fill="{PALETTE["text"]}">Learning in public.</text>'
        f'<text x="58" y="132" font-family="Georgia, serif" font-size="25" fill="{PALETTE["text"]}">Building with data.</text>'
        f'<circle cx="1090" cy="86" r="38" fill="#131922" stroke="#52cdb1" stroke-width="2"/>'
        f'<image href="{portrait_uri}" x="1054" y="50" width="72" height="72" preserveAspectRatio="xMidYMid slice" clip-path="url(#portraitClip)"/>'
    )

    # KPI row
    kpi_y = 164
    kpi_w = (width - 40 * 2 - 3 * 16) / 4
    kpis = [
        ("REPOSITORIES", stats["repos"], PALETTE["accent"]),
        ("TOTAL STARS", stats["stars"], PALETTE["accent3"]),
        ("FOLLOWERS", stats["followers"], PALETTE["accent2"]),
        ("CONTRIBUTIONS", stats["contributions"], PALETTE["accent4"]),
    ]
    for i, (label, value, color) in enumerate(kpis):
        kx = 40 + i * (kpi_w + 16)
        parts.append(_kpi_card(kx, kpi_y, kpi_w, 90, label, value, color))

    row2_y = kpi_y + 90 + 16
    row2_h = 292

    # Left: learning pipeline
    left_w = 350
    parts.append(_progress_panel(40, row2_y, left_w, row2_h, topics))

    # Middle: weekly bar chart
    mid_x = 40 + left_w + 16
    mid_w = 470
    parts.append(_weekly_bar_panel(mid_x, row2_y, mid_w, row2_h, stats["weekly"]))

    # Right: language pie
    right_x = mid_x + mid_w + 16
    right_w = width - right_x - 40
    parts.append(_language_pie_panel(right_x, row2_y, right_w, row2_h, stats["languages"]))

    # Bottom: recent activity table
    row3_y = row2_y + row2_h + 16
    row3_h = height - row3_y - 55
    parts.append(_recent_table_panel(40, row3_y, width - 80, row3_h, stats["recent"]))

    # Footer
    parts.append(
        f'<text x="40" y="{height-20}" font-family="Fira Code, monospace" font-size="11" '
        f'fill="{PALETTE["muted"]}">HANISH SHARMA · LIVE GITHUB DASHBOARD · {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    stats = fetch_user_stats()
    topics = fetch_diary_structure()

    svg = build_dashboard_svg(stats, topics)
    os.makedirs("assets", exist_ok=True)
    with open("assets/orbit_stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    for theme in ("dark", "light"):
        with open(f"assets/portfolio-hero-{theme}.svg", "w", encoding="utf-8") as f:
            f.write(build_portfolio_hero_svg(theme))

    tracker_md = build_tracker_markdown(topics)
    update_readme(tracker_md)

    print("Dashboard updated:", {k: v for k, v in stats.items() if k not in ("recent",)})
