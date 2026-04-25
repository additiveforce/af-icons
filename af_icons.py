"""
af_icons.py
-----------
Fetches AF icon SVGs from the GitHub repository at runtime.
Returns clean SVG strings ready for injection into PPTX, HTML, or any other output.

Repository: https://github.com/additiveforce/af-icons
Naming: kebab-case, e.g. "ai-chip", "focus-group", "arrow-long-right"

Usage
-----
Single icon:
    from af_icons import get_icon
    svg = get_icon("ai-chip")                      # currentColor fill
    svg = get_icon("ai-chip", color="#2563eb")     # explicit hex fill

Multiple icons:
    from af_icons import get_icons
    icons = get_icons(["ai-chip", "ai-llm", "focus-group"])

List all available icons (requires GITHUB_TOKEN env var, or pass token):
    from af_icons import list_icons
    names = list_icons()
    names = list_icons(filter_term="arrow")

CLI:
    python af_icons.py ai-chip
    python af_icons.py ai-chip ai-llm focus-group
    python af_icons.py --color "#2563eb" ai-chip ai-llm
    python af_icons.py --list
    python af_icons.py --list --filter arrow
"""

import os
import re
import sys
import requests
from typing import Optional

REPO_BASE = "https://raw.githubusercontent.com/additiveforce/af-icons/main"
REPO_API  = "https://api.github.com/repos/additiveforce/af-icons/contents/"

_cache: dict[str, str] = {}


def _normalize_fill(svg: str, color: Optional[str] = None) -> str:
    """
    Ensure SVG has an explicit fill attribute.

    Repo SVGs export without fill — they inherit from CSS parent.
    For PPTX and standalone use, fill must be explicit.

    color provided  → fill set to that hex value
    color None      → fill set to "currentColor" (correct for HTML/CSS)
    """
    fill_value = color if color else "currentColor"

    if "fill=" in svg:
        svg = re.sub(r'fill="[^"]*"', f'fill="{fill_value}"', svg)
        svg = re.sub(r"fill='[^']*'", f"fill='{fill_value}'", svg)
        return svg

    # No fill present — add to root <svg> element, cascades to all paths
    svg = re.sub(
        r"(<svg\b[^>]*?)(>)",
        lambda m: m.group(1) + f' fill="{fill_value}"' + m.group(2),
        svg,
        count=1
    )
    return svg


def get_icon(name: str, color: Optional[str] = None, normalize: bool = True) -> str:
    """
    Fetch a single icon SVG by name.

    Parameters
    ----------
    name : str
        Icon filename without extension. kebab-case, e.g. "ai-chip".
    color : str, optional
        Hex fill color e.g. "#2563eb". None = currentColor.
    normalize : bool
        True (default) = ensure fill attribute present.
        False = return raw repo SVG unchanged.

    Returns
    -------
    str
        SVG string ready to inline or write to file.

    Raises
    ------
    ValueError  — icon not found in repo
    requests.RequestException  — network failure
    """
    name = name.lower().strip()

    if name not in _cache:
        url = f"{REPO_BASE}/{name}.svg"
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            raise ValueError(
                f"Icon '{name}' not found. "
                f"Check names at: https://github.com/additiveforce/af-icons"
            )
        response.raise_for_status()
        _cache[name] = response.text

    svg = _cache[name]

    if normalize or color:
        svg = _normalize_fill(svg, color=color)

    return svg


def get_icons(
    names: list[str],
    color: Optional[str] = None,
    normalize: bool = True
) -> dict[str, str]:
    """
    Fetch multiple icons. Returns {name: svg_string}.
    Failed fetches are logged to stderr and excluded from result.
    """
    results = {}
    for name in names:
        try:
            results[name] = get_icon(name, color=color, normalize=normalize)
        except (ValueError, requests.RequestException) as e:
            print(f"Warning: {e}", file=sys.stderr)
    return results


def list_icons(
    filter_term: Optional[str] = None,
    github_token: Optional[str] = None
) -> list[str]:
    """
    Return all available icon names from the repository.
    Requires a GitHub token to avoid API rate limits.
    Token read from GITHUB_TOKEN env var or passed directly.
    """
    token = github_token or os.environ.get("GITHUB_TOKEN")
    headers = {"Authorization": f"token {token}"} if token else {}

    response = requests.get(REPO_API, headers=headers, timeout=10)

    if response.status_code == 403:
        raise PermissionError(
            "GitHub API rate limit hit. Set GITHUB_TOKEN env var or pass github_token=. "
            "Generate a token at: https://github.com/settings/tokens"
        )
    response.raise_for_status()

    files = response.json()
    names = sorted(
        f["name"].replace(".svg", "")
        for f in files
        if isinstance(f, dict) and f.get("name", "").endswith(".svg")
    )

    if filter_term:
        names = [n for n in names if filter_term.lower() in n]

    return names


def save_icon(name: str, path: str, color: Optional[str] = None) -> None:
    """Fetch an icon and write it to a .svg file."""
    svg = get_icon(name, color=color)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    # Parse --color
    color = None
    if "--color" in args:
        idx = args.index("--color")
        if idx + 1 < len(args):
            color = args[idx + 1]
            args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]

    # --list mode
    if "--list" in args:
        filter_term = None
        if "--filter" in args:
            idx = args.index("--filter")
            if idx + 1 < len(args):
                filter_term = args[idx + 1]
        try:
            icons = list_icons(filter_term=filter_term)
            print(f"\n{len(icons)} icons available:\n")
            for name in icons:
                print(f"  {name}")
        except PermissionError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Fetch one or more icons
    names = [a for a in args if not a.startswith("--")]
    for name in names:
        try:
            svg = get_icon(name, color=color)
            if len(names) > 1:
                print(f"\n<!-- {name} -->")
            print(svg)
        except (ValueError, requests.RequestException) as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
