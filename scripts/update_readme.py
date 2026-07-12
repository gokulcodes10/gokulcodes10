#!/usr/bin/env python3
"""Regenerate the "Featured Projects" section of README.md.

Reads:
  featured.json  - curated project cards, in display order
  repos.json     - cached list of known repo names

Fetches the live repo list from the GitHub API, appends a placeholder
card for every repo not yet in the cache (private repos get a
"case study coming soon" note instead of being skipped), rewrites the
block between the FEATURED markers, and updates the cache.

Auth: set GH_TOKEN (or GITHUB_TOKEN). A classic PAT with `repo` scope
is required to see private repos; the default Actions token only sees
public ones.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

USER = "gokulcodes10"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(ROOT, "README.md")
CACHE_PATH = os.path.join(ROOT, "repos.json")
FEATURED_PATH = os.path.join(ROOT, "featured.json")
START_MARK = "<!-- FEATURED:START -->"
END_MARK = "<!-- FEATURED:END -->"

# simple-icons slugs for shields.io; techs missing here render without a logo
BADGE_SLUGS = {
    "Python": "python",
    "JavaScript": "javascript",
    "Java": "openjdk",
    "React": "react",
    "Next.js": "nextdotjs",
    "Vite": "vite",
    "FastAPI": "fastapi",
    "Spring Boot": "springboot",
    "LangChain": "langchain",
    "Ollama": "ollama",
    "Streamlit": "streamlit",
    "Docker": "docker",
    "PostgreSQL": "postgresql",
    "Redis": "redis",
    "GitHub Actions": "githubactions",
    "Vercel": "vercel",
    "Gemini": "googlegemini",
    "Arduino": "arduino",
    "Tailwind CSS": "tailwindcss",
}


def badge(tech):
    slug = BADGE_SLUGS.get(tech, "")
    label = urllib.parse.quote(tech.replace("-", "--").replace("_", "__"))
    logo = "&logo=%s&logoColor=white" % slug if slug else ""
    return "![%s](https://img.shields.io/badge/-%s-05122A?style=flat%s)" % (tech, label, logo)


def fetch_repos():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

    def get(url):
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER,
        }
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)

    # /user/repos includes private repos when the token is a PAT with
    # `repo` scope; fall back to the public listing for other tokens.
    bases = [
        "https://api.github.com/user/repos?affiliation=owner&per_page=100",
        "https://api.github.com/users/%s/repos?per_page=100" % USER,
    ]
    for base in bases:
        try:
            repos, page = [], 1
            while True:
                batch = get("%s&page=%d" % (base, page))
                repos.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
            if repos:
                return repos
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            print("warn: %s failed: %s" % (base.split("?")[0], exc), file=sys.stderr)
    return []


def render_card(entry):
    lock = "\U0001f512 " if entry.get("private") else ""
    title = entry.get("title") or entry["name"]
    link = entry.get("link")
    if not link and not entry.get("private"):
        link = "https://github.com/%s/%s" % (USER, entry["name"])
    # private entries without a case-study link get no heading link:
    # pointing at the private repo would 404 for visitors
    heading = "#### %s[%s](%s)" % (lock, title, link) if link else "#### %s%s" % (lock, title)
    lines = [heading, ""]
    if entry.get("blurb"):
        lines += [entry["blurb"], ""]
    if entry.get("stack"):
        lines += [" ".join(badge(t) for t in entry["stack"]), ""]
    if entry.get("private"):
        if link:
            lines += [
                "\U0001f512 **Private repo** — architecture & demo available in the [case study](%s)." % link,
                "",
            ]
        else:
            lines += ["\U0001f512 **Private project — case study coming soon.**", ""]
    return "\n".join(lines)


def main():
    with open(FEATURED_PATH, encoding="utf-8") as f:
        featured = json.load(f)
    with open(CACHE_PATH, encoding="utf-8") as f:
        known = set(json.load(f))

    live = fetch_repos()
    if not live:
        print("error: could not fetch any repos; leaving README unchanged", file=sys.stderr)
        return 1

    live_names = {r["name"] for r in live}
    new_repos = [r for r in live if r["name"] not in known]
    for repo in sorted(new_repos, key=lambda r: r.get("created_at") or ""):
        entry = {
            "name": repo["name"],
            "title": repo["name"].strip("-_").replace("-", " ").replace("_", " "),
            "private": bool(repo.get("private")),
            "auto": True,
        }
        if not repo.get("private"):
            entry["blurb"] = repo.get("description") or ""
            entry["link"] = repo.get("html_url")
            if repo.get("language"):
                entry["stack"] = [repo["language"]]
        featured.append(entry)
        print("new repo detected: %s" % repo["name"])

    # drop auto entries whose repo has since been deleted or renamed
    featured = [
        e for e in featured
        if not (e.get("auto") and e["name"] not in live_names)
    ]

    block = "\n".join(render_card(e) for e in featured).rstrip() + "\n"

    with open(README_PATH, encoding="utf-8") as f:
        readme = f.read()
    try:
        head, rest = readme.split(START_MARK, 1)
        _, tail = rest.split(END_MARK, 1)
    except ValueError:
        print("error: FEATURED markers missing from README.md", file=sys.stderr)
        return 1
    readme = head + START_MARK + "\n\n" + block + "\n" + END_MARK + tail

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(readme)
    with open(FEATURED_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(featured, f, indent=2, ensure_ascii=False)
        f.write("\n")
    with open(CACHE_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sorted(live_names), f, indent=2)
        f.write("\n")
    print("README regenerated (%d cards, %d new)" % (len(featured), len(new_repos)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
