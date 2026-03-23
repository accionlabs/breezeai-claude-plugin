#!/usr/bin/env python3
"""
Pre-process Markdown to render mermaid diagram blocks as PNG images.

Converts ```mermaid code blocks to PNG images using @mermaid-js/mermaid-cli (mmdc),
then replaces the blocks with image references so pandoc can embed them in DOCX/PDF.

Usage:
    python3 render-mermaid.py <input.md> <output.md> [--output-dir <dir>]

Requires:
    - npx (Node.js)
    - @mermaid-js/mermaid-cli (auto-installed via npx --yes)
    - Chromium or Google Chrome (headless rendering)

If mmdc or a browser is unavailable, mermaid blocks are left as-is with a warning.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


# Regex to match ```mermaid ... ``` blocks
MERMAID_BLOCK_RE = re.compile(
    r"```mermaid\s*\n(.*?)```",
    re.DOTALL,
)

# Browser binary names to search for, in priority order
BROWSER_CANDIDATES = [
    "chromium-browser",
    "chromium",
    "google-chrome",
    "google-chrome-stable",
]

# Standard paths to search beyond $PATH
BROWSER_SEARCH_PATHS = [
    "/usr/bin",
    "/usr/local/bin",
    "/snap/bin",
    "/usr/lib/chromium-browser",
    "/usr/lib/chromium",
]


def find_browser():
    """Auto-detect a Chromium/Chrome binary on the system."""
    for name in BROWSER_CANDIDATES:
        # Check $PATH first
        path = shutil.which(name)
        if path:
            return path
        # Check standard locations
        for search_dir in BROWSER_SEARCH_PATHS:
            candidate = os.path.join(search_dir, name)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return None


def check_npx():
    """Check if npx is available."""
    return shutil.which("npx") is not None


def create_puppeteer_config(browser_path, config_dir):
    """Create a puppeteer config for headless Chromium in WSL/Linux."""
    config = {
        "executablePath": browser_path,
        "args": [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ],
    }
    config_path = os.path.join(config_dir, "puppeteer-config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)
    return config_path


def render_mermaid_to_png(mermaid_code, output_path, puppeteer_config):
    """Render a single mermaid diagram to PNG using mmdc via npx."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".mmd", delete=False
    ) as mmd_file:
        mmd_file.write(mermaid_code)
        mmd_path = mmd_file.name

    try:
        cmd = [
            "npx", "--yes", "@mermaid-js/mermaid-cli",
            "-i", mmd_path,
            "-o", output_path,
            "-b", "white",
            "--scale", "2",
        ]
        if puppeteer_config:
            cmd.extend(["-p", puppeteer_config])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"  Warning: mmdc failed: {result.stderr.strip()}", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  Warning: mmdc timed out after 60s", file=sys.stderr)
        return False
    except FileNotFoundError:
        print("  Warning: npx not found", file=sys.stderr)
        return False
    finally:
        os.unlink(mmd_path)


def process_markdown(input_path, output_path, image_dir):
    """Read markdown, render mermaid blocks to PNG, write updated markdown."""
    with open(input_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all mermaid blocks
    blocks = list(MERMAID_BLOCK_RE.finditer(content))

    if not blocks:
        print("No mermaid blocks found — no rendering needed.")
        return False  # Signal: no mermaid blocks found

    print(f"Found {len(blocks)} mermaid diagram(s).")

    # Check prerequisites
    if not check_npx():
        print(
            "Warning: npx not found. Mermaid diagrams will remain as code blocks.",
            file=sys.stderr,
        )
        return False

    browser_path = find_browser()
    if not browser_path:
        print(
            "Warning: No Chromium/Chrome browser found. "
            "Mermaid diagrams will remain as code blocks.\n"
            "Install with: sudo apt install chromium-browser",
            file=sys.stderr,
        )
        return False

    print(f"Using browser: {browser_path}")

    # Create image output directory
    os.makedirs(image_dir, exist_ok=True)

    # Create puppeteer config
    puppeteer_config = create_puppeteer_config(browser_path, image_dir)

    # Process blocks in reverse order to preserve positions
    new_content = content
    rendered_count = 0

    for i, match in enumerate(reversed(blocks), 1):
        idx = len(blocks) - i  # Original index (0-based)
        mermaid_code = match.group(1).strip()
        image_filename = f"mermaid-diagram-{idx + 1}.png"
        image_path = os.path.join(image_dir, image_filename)
        rel_image_path = os.path.join(os.path.basename(image_dir), image_filename)

        print(f"  Rendering diagram {idx + 1}/{len(blocks)}...", end=" ")

        if render_mermaid_to_png(mermaid_code, image_path, puppeteer_config):
            # Replace the mermaid block with an image reference
            replacement = f"![Diagram {idx + 1}]({rel_image_path})"
            new_content = (
                new_content[: match.start()]
                + replacement
                + new_content[match.end() :]
            )
            rendered_count += 1
            print("OK")
        else:
            print("SKIPPED (left as code block)")

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"\nRendered {rendered_count}/{len(blocks)} diagrams.")
    return rendered_count > 0


def main():
    if len(sys.argv) < 3:
        print(
            "Usage: python3 render-mermaid.py <input.md> <output.md> "
            "[--output-dir <dir>]",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2]

    # Parse --output-dir
    image_dir = "_mermaid_images"
    if "--output-dir" in sys.argv:
        idx = sys.argv.index("--output-dir")
        if idx + 1 < len(sys.argv):
            image_dir = sys.argv[idx + 1]

    if not os.path.isfile(input_path):
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    had_mermaid = process_markdown(input_path, output_path, image_dir)

    if had_mermaid:
        print(f"Written to {output_path}")
        print(f"Images in {image_dir}/")
    else:
        # No rendering happened — copy input as-is if paths differ
        if os.path.abspath(input_path) != os.path.abspath(output_path):
            shutil.copy2(input_path, output_path)
        print(f"Output: {output_path} (unchanged)")


if __name__ == "__main__":
    main()
