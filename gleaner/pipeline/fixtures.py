"""Fixture-test health check (SPEC.md: "Adapter no longer extracts the
saved sample correctly -> Blocks deployment of the change"). Shared by the
public repo's own tests (against invented fixtures) and by an operator
running it against the private config's real, saved snapshots before a
source goes live or after an adapter repair.
"""
from __future__ import annotations

from pathlib import Path

from gleaner.adapters import get_adapter
from gleaner.config import Config


def check_sources(config: Config, base_dir: Path) -> list[str]:
    """Returns a list of failure messages, one per problem found. An empty
    list means every source with a fixture extracted at least one item with
    every required_field populated."""
    base_dir = Path(base_dir)
    failures: list[str] = []

    for source in config.sources:
        if not source.fixture:
            continue

        fixture_path = base_dir / source.fixture
        if not fixture_path.exists():
            failures.append(f"{source.id}: fixture file not found at {fixture_path}")
            continue

        try:
            adapter = get_adapter(source.adapter)
        except NotImplementedError as exc:
            failures.append(f"{source.id}: {exc}")
            continue

        content = fixture_path.read_text(encoding="utf-8")
        try:
            items = adapter.parse(content, source)
        except Exception as exc:
            failures.append(f"{source.id}: fixture failed to parse: {exc}")
            continue

        if not items:
            failures.append(f"{source.id}: fixture produced zero items")
            continue

        for item in items:
            missing = [f for f in source.required_fields if not item.fields.get(f)]
            if missing:
                failures.append(
                    f"{source.id}: item missing required fields {missing}: {item.fields}"
                )

    return failures
