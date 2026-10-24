from entity_resolver.steps.cache import BoundedTTLCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _cache(clock: FakeClock, max_bytes: int = 10, ttl: float = 60) -> BoundedTTLCache[str, str]:
    return BoundedTTLCache(max_bytes, ttl, lambda key, value: len(key) + len(value), clock)


def test_entries_expire_after_ttl() -> None:
    clock = FakeClock()
    cache = _cache(clock)
    cache.put("a", "1")
    clock.now = 59
    assert cache.get("a") == "1"
    clock.now = 60
    assert cache.get("a") is None


def test_least_recently_used_entry_is_evicted_when_full() -> None:
    cache = _cache(FakeClock(), max_bytes=6)
    cache.put("a", "11")
    cache.put("b", "22")
    assert cache.get("a") == "11"  # "b" is now least recently used
    cache.put("c", "33")
    assert cache.get("b") is None
    assert cache.get("a") == "11"
    assert cache.get("c") == "33"


def test_entry_larger_than_cache_is_not_stored() -> None:
    cache = _cache(FakeClock(), max_bytes=4)
    cache.put("a", "toolong")
    assert cache.get("a") is None


def test_replacing_a_key_keeps_size_accounting() -> None:
    cache = _cache(FakeClock(), max_bytes=4)
    cache.put("a", "1")
    cache.put("a", "2")
    cache.put("b", "3")
    assert cache.get("a") == "2"
    assert cache.get("b") == "3"
