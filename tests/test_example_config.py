"""Keeps config/example.yaml (the public-facing documentation example)
honest: it must load, and its own fixture must actually parse."""
from pathlib import Path

from gleaner.adapters import get_adapter
from gleaner.config import load_config

REPO_ROOT = Path(__file__).parent.parent


def test_public_example_config_loads_and_fixture_parses():
    config = load_config(REPO_ROOT / "config")
    source = config.source_by_id("example-statistics-feed")
    adapter = get_adapter(source.adapter)
    content = (REPO_ROOT / source.fixture).read_text()

    items = adapter.parse(content, source)

    assert len(items) == 1
    assert items[0].fields["title"] == "Quarterly price index released"
