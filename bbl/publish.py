#!/usr/bin/env python3
"""Publish a generated report package to a configured webhook.

Discord webhooks support both a message and file attachments. Other platforms
can consume the generated caption/text files through a generic JSON webhook.
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import urllib.request
from pathlib import Path


def post_discord(url: str, report_dir: Path, caption: str) -> None:
    weekly = report_dir / "Weekly Analyst Report.png"
    images = [weekly] if weekly.exists() else [
        report_dir / "Top 10 Performances.png",
        report_dir / "Top 10 Worst Performances.png",
    ]
    boundary = "----BBLReportBoundary"
    parts = []
    payload = json.dumps({"content": caption[:1900]}).encode()
    parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
                  f'Content-Type: application/json\r\n\r\n').encode() + payload + b"\r\n")
    index = 0
    for image in images:
        if not image.exists():
            continue
        data = image.read_bytes()
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="files[{index}]"; '
                      f'filename="{image.name}"\r\nContent-Type: image/png\r\n\r\n').encode()
                     + data + b"\r\n")
        index += 1
    body = b"".join(parts) + f"--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 300:
            raise RuntimeError(f"Discord webhook returned HTTP {response.status}")


def post_generic(url: str, report_dir: Path, caption: str) -> None:
    payload = json.dumps({
        "date": report_dir.name,
        "caption": caption,
        "text": (report_dir / "Weekly Analyst Report.md").read_text(encoding="utf-8")
        if (report_dir / "Weekly Analyst Report.md").exists()
        else ((report_dir / "Best & Worst - Text.txt").read_text(encoding="utf-8")
              if (report_dir / "Best & Worst - Text.txt").exists() else ""),
        "report_url": str(report_dir / "Weekly Analyst Report.md")
        if (report_dir / "Weekly Analyst Report.md").exists()
        else str(report_dir / "Best & Worst.html"),
        "image_paths": [str(p) for p in report_dir.glob("*.png")],
    }).encode()
    request = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"},
                                     method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status >= 300:
            raise RuntimeError(f"Generic webhook returned HTTP {response.status}")


def publish(report_dir: Path) -> None:
    caption_file = report_dir / "caption.txt"
    caption = caption_file.read_text(encoding="utf-8") if caption_file.exists() else \
        (report_dir / "Best & Worst - Text.txt").read_text(encoding="utf-8")
    discord = os.environ.get("BBL_DISCORD_WEBHOOK_URL")
    generic = os.environ.get("BBL_PUBLISH_WEBHOOK_URL")
    if not discord and not generic:
        print("Publishing skipped: no webhook configured")
        return
    if discord:
        post_discord(discord, report_dir, caption)
        print("Published to Discord")
    if generic:
        post_generic(generic, report_dir, caption)
        print("Published to generic webhook")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python3 bbl/publish.py REPORT_DIRECTORY")
    publish(Path(sys.argv[1]).resolve())
