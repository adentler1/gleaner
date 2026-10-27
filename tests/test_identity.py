from gleaner.pipeline.identity import (
    compute_cluster_key,
    compute_content_hash,
    compute_item_id,
    normalize_url,
)


def test_normalize_url_lowercases_and_strips_tracking():
    url = "HTTPS://Example.ORG/Jobs/42/?utm_source=newsletter&ref=abc&id=42#section"
    assert normalize_url(url) == "https://example.org/Jobs/42?id=42"


def test_normalize_url_drops_trailing_slash_but_keeps_root():
    assert normalize_url("https://example.org/path/") == "https://example.org/path"
    assert normalize_url("https://example.org/") == "https://example.org/"


def test_normalize_url_is_stable_regardless_of_param_order():
    a = normalize_url("https://example.org/x?b=2&a=1")
    b = normalize_url("https://example.org/x?a=1&b=2")
    assert a == b


def test_compute_item_id_prefers_source_item_id():
    item_id = compute_item_id(source_id="src", source_item_id="123", canonical_url="https://x/y")
    assert item_id == "src:123"


def test_compute_item_id_falls_back_to_url():
    item_id = compute_item_id(source_id="src", source_item_id=None, canonical_url="https://x/y")
    assert item_id == "src:url:https://x/y"


def test_content_hash_ignores_undeclared_noise():
    h1 = compute_content_hash({"title": "Professor of Economics", "deadline": "2026-12-01"})
    h2 = compute_content_hash({"title": "Professor of Economics", "deadline": "2026-12-01"})
    assert h1 == h2


def test_content_hash_changes_on_declared_field_change():
    h1 = compute_content_hash({"title": "Professor of Economics", "deadline": "2026-12-01"})
    h2 = compute_content_hash({"title": "Professor of Economics", "deadline": "2026-12-15"})
    assert h1 != h2


def test_cluster_key_normalizes_case_and_punctuation():
    k1 = compute_cluster_key(title="Professor of Economics!", employer_or_deadline="LSE")
    k2 = compute_cluster_key(title="professor of economics", employer_or_deadline="lse")
    assert k1 == k2


def test_cluster_key_none_without_title():
    assert compute_cluster_key(title=None, employer_or_deadline="LSE") is None
    assert compute_cluster_key(title="", employer_or_deadline="LSE") is None
