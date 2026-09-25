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
    Original design: four stat 'planets' orbiting a central core,
    at alternating orbit distances. Nothing templated - hand-built layout.
    """
    metrics = [
        ("Contributions", stats["contributions"], "#00F5D4"),
        ("Repositories", stats["repos"], "#00B8D9"),
        ("Stars Earned", stats["stars"], "#7C5CFC"),
        ("Followers", stats["followers"], "#FF6B9D"),
    ]

    cx, cy = 450, 220
    radius_base = 90
    svg_parts = [
        f'<svg width="900" height="440" viewBox="0 0 900 440" xmlns="http://www.w3.org/2000/svg">',
        '<rect width="900" height="440" rx="16" fill="#0d1117"/>',
        f'<circle cx="{cx}" cy="{cy}" r="34" fill="#161b22" stroke="#00F5D4" stroke-width="2"/>',
        f'<text x="{cx}" y="{cy+6}" font-family="Fira Code, monospace" font-size="13" '
        f'fill="#E6EDF3" text-anchor="middle">Hanish</text>',
    ]

    n = len(metrics)
    for i, (label, value, color) in enumerate(metrics):
        angle = (2 * math.pi / n) * i - math.pi / 2
        orbit_r = radius_base + (i % 2) * 40
        x = cx + orbit_r * math.cos(angle)
        y = cy + orbit_r * math.sin(angle)

        svg_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{orbit_r}" fill="none" '
            f'stroke="{color}" stroke-width="1" opacity="0.25" stroke-dasharray="4 4"/>'
        )
        svg_parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="30" fill="{color}" opacity="0.15"/>')
        svg_parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="30" fill="none" stroke="{color}" stroke-width="2"/>'
        )
        svg_parts.append(
            f'<text x="{x:.1f}" y="{y+5:.1f}" font-family="Fira Code, monospace" font-size="16" '
            f'font-weight="700" fill="{color}" text-anchor="middle">{value}</text>'
        )
        label_y = y + 50 if y > cy else y - 45
        svg_parts.append(
            f'<text x="{x:.1f}" y="{label_y:.1f}" font-family="Fira Code, monospace" font-size="12" '
            f'fill="#8B949E" text-anchor="middle">{label}</text>'
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