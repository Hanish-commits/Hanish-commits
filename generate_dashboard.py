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
    Terminal-window design: a mock macOS-style terminal printing
    live stats as command output. Matches the Fira Code typing header.
    """
    lines = [
        ("$ whoami", "#8B949E"),
        ("Hanish", "#E6EDF3"),
        ("", ""),
        ("$ git log --oneline --all | wc -l", "#8B949E"),
        (f"{stats['contributions']} contributions", "#00F5D4"),
        ("", ""),
        ("$ ls repos/ | wc -l", "#8B949E"),
        (f"{stats['repos']} repositories", "#00B8D9"),
        ("", ""),
        ("$ git shortlog -s | grep stars", "#8B949E"),
        (f"{stats['stars']} stars earned", "#7C5CFC"),
        ("", ""),
        ("$ curl api.github.com/followers", "#8B949E"),
        (f"{stats['followers']} followers", "#FF6B9D"),
    ]

    width, height = 900, 420
    svg_parts = [
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{width}" height="{height}" rx="12" fill="#0d1117" stroke="#30363d" stroke-width="1"/>',
        f'<rect width="{width}" height="40" rx="12" fill="#161b22"/>',
        f'<rect y="28" width="{width}" height="12" fill="#161b22"/>',
        '<circle cx="28" cy="20" r="7" fill="#FF5F56"/>',
        '<circle cx="52" cy="20" r="7" fill="#FFBD2E"/>',
        '<circle cx="76" cy="20" r="7" fill="#27C93F"/>',
        f'<text x="{width/2}" y="25" font-family="Fira Code, monospace" font-size="13" '
        f'fill="#8B949E" text-anchor="middle">hanish@github: ~/dashboard</text>',
    ]

    y = 80
    for text, color in lines:
        if text:
            svg_parts.append(
                f'<text x="40" y="{y}" font-family="Fira Code, monospace" font-size="17" '
                f'fill="{color}">{text}</text>'
            )
        y += 26

    svg_parts.append(
        f'<rect x="40" y="{y-18}" width="10" height="20" fill="#00F5D4">'
        f'<animate attributeName="opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/>'
        f'</rect>'
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