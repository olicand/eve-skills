#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MACHONET_ROOT = Path(
    "/Users/ocrand/Library/Application Support/CCP/EVE/"
    "_users_ocrand_library_application_support_eve_frontier_sharedcache_utopia_eve.app_contents_resources_build_utopia.servers.evefrontier.com/"
    "cache/MachoNet/198.18.0.64/489"
)
DEFAULT_OUTPUT_PATH = Path(
    "/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/reports/machonet_activity_watch.json"
)


@dataclass
class CacheEntry:
    relative_path: str
    size: int
    mtime_ns: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Snapshot or watch Utopia MachoNet cache activity.")
    parser.add_argument(
        "--machonet-root",
        type=Path,
        default=DEFAULT_MACHONET_ROOT,
        help="Path to the MachoNet cache root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Where to write the JSON activity report.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=1.0,
        help="Polling interval when watch mode is enabled.",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=30.0,
        help="How long to watch for updates.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Poll for file changes over time instead of taking a single snapshot.",
    )
    return parser.parse_args()


def collect_entries(root: Path) -> dict[str, CacheEntry]:
    entries: dict[str, CacheEntry] = {}
    for path in sorted(root.rglob("*.cache")):
        stat = path.stat()
        rel = str(path.relative_to(root))
        entries[rel] = CacheEntry(relative_path=rel, size=stat.st_size, mtime_ns=stat.st_mtime_ns)
    return entries


def decode_method_call_details(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("latin-1", errors="ignore")

    # These files consistently embed service and method names in a compact binary header.
    # We keep the parser deliberately conservative: split on control bytes and return
    # printable segments so follow-up analysis can be done without assuming a full schema.
    segments = [segment for segment in "".join(ch if ch.isprintable() else "\n" for ch in text).splitlines() if segment]
    filtered = [segment for segment in segments if any(char.isalpha() for char in segment)]

    service = None
    method = None
    metadata: list[str] = []

    if filtered:
        service = filtered[0]
    if len(filtered) > 1:
        method = filtered[1]
    if len(filtered) > 2:
        metadata = filtered[2:]

    return {
        "service": service,
        "method": method,
        "metadata": metadata,
    }


def build_snapshot(root: Path) -> dict[str, Any]:
    entries = collect_entries(root)
    detail_entries = []
    for rel, entry in entries.items():
        payload: dict[str, Any] = {
            "path": rel,
            "size": entry.size,
            "mtime_ns": entry.mtime_ns,
        }
        if rel.startswith("MethodCallCachingDetails/"):
            payload["decoded"] = decode_method_call_details(root / rel)
        detail_entries.append(payload)
    return {
        "machonet_root": str(root),
        "entry_count": len(detail_entries),
        "entries": detail_entries,
    }


def diff_snapshots(previous: dict[str, CacheEntry], current: dict[str, CacheEntry], root: Path) -> dict[str, Any]:
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    changed = sorted(
        rel
        for rel in set(current) & set(previous)
        if current[rel].mtime_ns != previous[rel].mtime_ns or current[rel].size != previous[rel].size
    )

    interesting = []
    for rel in added + changed:
        entry = current[rel]
        payload: dict[str, Any] = {
            "path": rel,
            "size": entry.size,
            "mtime_ns": entry.mtime_ns,
        }
        if rel.startswith("MethodCallCachingDetails/"):
            payload["decoded"] = decode_method_call_details(root / rel)
        interesting.append(payload)

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "interesting": interesting,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")


def run_watch(root: Path, interval_seconds: float, duration_seconds: float) -> dict[str, Any]:
    started_at = time.time()
    baseline = collect_entries(root)
    observations = []
    while time.time() - started_at < duration_seconds:
        time.sleep(interval_seconds)
        current = collect_entries(root)
        diff = diff_snapshots(baseline, current, root)
        if diff["added"] or diff["removed"] or diff["changed"]:
            observations.append(
                {
                    "observed_at_unix": time.time(),
                    **diff,
                }
            )
            baseline = current
    return {
        "mode": "watch",
        "machonet_root": str(root),
        "interval_seconds": interval_seconds,
        "duration_seconds": duration_seconds,
        "observations": observations,
    }


def main() -> int:
    args = parse_args()
    root = args.machonet_root.expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"MachoNet root does not exist: {root}")

    if args.watch:
        payload = run_watch(root, args.interval_seconds, args.duration_seconds)
    else:
        payload = {
            "mode": "snapshot",
            **build_snapshot(root),
        }

    write_json(args.output.expanduser().resolve(), payload)
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
