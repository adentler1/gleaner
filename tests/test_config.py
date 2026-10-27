from pathlib import Path

import pytest

from gleaner.config import Config, Source, Watch, load_config

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "config"


def test_load_config_reads_watches_and_sources():
    config = load_config(FIXTURE_DIR)
    assert {w.id for w in config.watches} == {"example-watch"}
    assert {s.id for s in config.sources} == {
        "example-html-source", "example-rss-source", "example-api-source",
    }

    watch = config.watch_by_id("example-watch")
    assert watch.pattern == "stream"
    assert watch.sources == ["example-html-source", "example-rss-source"]

    source = config.source_by_id("example-html-source")
    assert source.adapter == "html"
    assert source.extract.item == "div.job"
    assert source.extract.fields["url"] == "a@href"
    assert source.required_fields == ["title", "url"]


def test_watch_referencing_unknown_source_rejected():
    with pytest.raises(ValueError, match="unknown sources"):
        Config(
            watches=[Watch(id="w1", pattern="stream", description="x", sources=["missing"])],
            sources=[],
        )


def test_duplicate_source_ids_rejected():
    with pytest.raises(ValueError, match="duplicate source ids"):
        Config(
            watches=[],
            sources=[
                Source(id="dup", adapter="html", url="https://example.invalid"),
                Source(id="dup", adapter="rss", url="https://example.invalid/feed"),
            ],
        )


def test_missing_config_dir_raises(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        load_config(empty_dir)
