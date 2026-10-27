from pathlib import Path

from gleaner.adapters import api, html, rss
from gleaner.config import load_config

CONFIG_DIR = Path(__file__).parent / "fixtures" / "config"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _source(source_id: str):
    return load_config(CONFIG_DIR).source_by_id(source_id)


def test_html_adapter_parses_fixture():
    source = _source("example-html-source")
    content = (FIXTURES_DIR / "html" / "example-html-source.html").read_text()
    items = html.parse(content, source)

    assert len(items) == 3
    assert items[0].fields["title"] == "Lecturer in Invented Economics"
    assert items[0].fields["url"] == "/jobs/101"
    assert items[0].fields["deadline"] == "2026-12-01"
    # third item has no deadline span — must be None, not crash
    assert items[2].fields["deadline"] is None


def test_rss_adapter_parses_fixture():
    source = _source("example-rss-source")
    content = (FIXTURES_DIR / "rss" / "example-rss-source.xml").read_text()
    items = rss.parse(content, source)

    assert len(items) == 2
    assert items[0].source_item_id == "https://example.invalid/jobs/201"
    assert items[0].fields["title"] == "Assistant Professor, Example Department"
    assert items[0].fields["url"] == "https://example.invalid/jobs/201"


def test_api_adapter_parses_fixture():
    source = _source("example-api-source")
    content = (FIXTURES_DIR / "api" / "example-api-source.json").read_text()
    items = api.parse(content, source)

    assert len(items) == 2
    assert items[0].source_item_id == "301"
    assert items[0].fields["title"] == "Chair in Example Studies"
    assert items[0].fields["deadline"] == "2026-12-20"


def test_all_configured_sources_pass_their_fixture():
    """Generic fixture-test runner (SPEC.md: Fixture test health check) —
    every source with a fixture must extract at least one item with every
    required_field populated. A broken selector/path must fail this test,
    not reach deployment."""
    from gleaner.adapters import get_adapter

    config = load_config(CONFIG_DIR)
    repo_root = Path(__file__).parent.parent

    for source in config.sources:
        if not source.fixture:
            continue
        adapter = get_adapter(source.adapter)
        content = (repo_root / source.fixture).read_text()
        items = adapter.parse(content, source)

        assert items, f"{source.id}: fixture produced zero items"
        for item in items:
            missing = [f for f in source.required_fields if not item.fields.get(f)]
            assert not missing, f"{source.id}: item missing required fields {missing}: {item.fields}"
