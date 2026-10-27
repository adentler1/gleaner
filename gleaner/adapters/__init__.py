from gleaner.adapters import api, html, rss

REGISTRY = {
    "api": api,
    "rss": rss,
    "html": html,
}


def get_adapter(adapter_name: str):
    try:
        return REGISTRY[adapter_name]
    except KeyError:
        raise NotImplementedError(
            f"adapter {adapter_name!r} is valid config but not implemented yet "
            f"(implemented: {sorted(REGISTRY)})"
        )
