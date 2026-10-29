#!/usr/bin/env python3
"""Run the fixture-test health check against a config directory.

Usage: python scripts/check_fixtures.py <private_root>

<private_root> must contain a config/ subdirectory (watches/sources YAML)
and have fixture paths declared relative to itself, e.g. a source with
`fixture: fixtures/example.html` resolves to <private_root>/fixtures/example.html.
This is what SPEC.md calls blocking deployment of a change: run this before
a source goes live, and after every adapter repair.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gleaner.config import load_config
from gleaner.pipeline.fixtures import check_sources


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <private_root>", file=sys.stderr)
        return 2

    private_root = Path(sys.argv[1])
    config = load_config(private_root / "config")
    failures = check_sources(config, base_dir=private_root)

    if failures:
        print(f"FAIL: {len(failures)} problem(s)")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(f"OK: {len(config.sources)} source(s) checked, all fixtures pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
