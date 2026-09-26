"""
generate_dashboard.py

Pulls live data from the GitHub API and builds two custom, self-owned SVGs:
  1. assets/orbit_stats.svg   - an original radial stats visual (not a copied badge template)
  2. Updates the chapter tracker section inside README.md by scanning the
     DataScienceBy-Hanish repo's real folder/file structure.

Runs inside GitHub Actions, authenticated with the built-in GITHUB_TOKEN.
"""

import os
import re
import math
import requests

USERNAME = "Hanish-commits"
DIARY_REPO = "DataScienceBy-Hanish"
TOKEN = os.environ["GH_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def fetch_user_stats():
    """Pull real numbers straight from the GitHub API - no third-party service."""
    user = requests.get(f"https://api.github.com/users/{USERNAME}", headers=HEADERS).json()
    repos = requests.get(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=100", headers=HEADERS
    ).json()

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_repos = user.get("public_repos", len(repos))
    followers = user.get("followers", 0)

    # Contribution count via GraphQL (more accurate than REST for commit totals)
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
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
    total_contributions = (
        gql.get("data", {})
        .get("user", {})
        .get("contributionsCollection", {})
        .get("contributionCalendar", {})
        .get("totalContributions", 0)
    )

    return {
        "repos": total_repos,
        "stars": total_stars,
        "followers": followers,
        "contributions": total_contributions,
    }

def build_orbit_svg(stats):
    """
    'Signal Pulse' design: glowing animated bars growing in on load,
    bold gradient numbers, pulsing accent dots. Built for visual punch.
    """
    metrics = [
        ("CONTRIBUTIONS", stats["contributions"], "#00F5D4", "#00B8D9"),
        ("REPOSITORIES", stats["repos"], "#7C5CFC", "#B18CFF"),
        ("STARS EARNED", stats["stars"], "#FF6B9D", "#FFB3C6"),
        ("FOLLOWERS", stats["followers"], "#FFD166", "#FFE8A3"),
    ]

    width, height = 900, 420
    max_val = max((m[1] for m in metrics), default=1) or 1

    svg_parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        "<defs>",
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">',
        '<feGaussianBlur stdDeviation="6" result="blur"/>',
        '<feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>',
        "</filter>",
    ]
    for i, (label, value, c1, c2) in enumerate(metrics):
        svg_parts.append(
            f'<linearGradient id="grad{i}" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0%" stop-color="{c1}"/><stop offset="100%" stop-color="{c2}"/>'
            f"</linearGradient>"
        )
    svg_parts.append("</defs>")

    svg_parts.append(f'<rect width="{width}" height="{height}" rx="16" fill="#0a0e14"/>')
    svg_parts.append(
        f'<text x="40" y="55" font-family="Fira Code, monospace" font-size="22" '
        f'font-weight="700" fill="#E6EDF3">Hanish — Live Signal</text>'
    )
    svg_parts.append(
        '<circle cx="850" cy="47" r="6" fill="#00F5D4" filter="url(#glow)">'
        '<animate attributeName="opacity" values="1;0.3;1" dur="1.6s" repeatCount="indefinite"/>'
        "</circle>"
    )

    bar_x = 220
    bar_max_w = 600
    bar_h = 34
    gap = 78
    start_y = 100

    for i, (label, value, c1, c2) in enumerate(metrics):
        y = start_y + i * gap
        target_w = max(20, (value / max_val) * bar_max_w)

        svg_parts.append(
            f'<text x="40" y="{y + bar_h/2 + 5}" font-family="Fira Code, monospace" font-size="13" '
            f'fill="#8B949E" letter-spacing="1">{label}</text>'
        )
        svg_parts.append(
            f'<rect x="{bar_x}" y="{y}" width="{bar_max_w}" height="{bar_h}" rx="8" fill="#161b22"/>'
        )
        bar = (
            f'<rect x="{bar_x}" y="{y}" width="0" height="{bar_h}" rx="8" '
            f'fill="url(#grad{i})" filter="url(#glow)">'
            f'<animate attributeName="width" from="0" to="{target_w:.1f}" '
            f'dur="1.2s" begin="{i*0.15}s" fill="freeze" calcMode="spline" '
            f'keySplines="0.16 1 0.3 1"/>'
            f"</rect>"
        )
        svg_parts.append(bar)
        svg_parts.append(
            f'<text x="{bar_x + bar_max_w + 20}" y="{y + bar_h/2 + 6}" '
            f'font-family="Fira Code, monospace" font-size="20" font-weight="700" '
            f'fill="{c1}">{value}</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)

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


if __name__ == "__main__":
    stats = fetch_user_stats()
    svg = build_orbit_svg(stats)
    os.makedirs("assets", exist_ok=True)
    with open("assets/orbit_stats.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    topics = fetch_diary_structure()
    tracker_md = build_tracker_markdown(topics)
    update_readme(tracker_md)

    print("Dashboard updated:", stats, topics)