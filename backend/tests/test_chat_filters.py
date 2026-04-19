from app.api.routes.chat import build_search_filter, normalize_sources


def test_build_search_filter_global():
    result = build_search_filter("tenant123:user123", "global")
    assert result == "scope eq 'global'"


def test_build_search_filter_private():
    result = build_search_filter("tenant123:user123", "private")
    assert result == "scope eq 'private' and owner_user_id eq 'tenant123:user123'"


def test_build_search_filter_all():
    result = build_search_filter("tenant123:user123", "all")
    assert result == "(scope eq 'global') or (scope eq 'private' and owner_user_id eq 'tenant123:user123')"


def test_build_search_filter_invalid():
    result = build_search_filter("tenant123:user123", "unknown")
    assert result is None


def test_normalize_sources_adds_who_prefix():
    raw_sources = [
        {
            "title": "Mpox article",
            "excerpt": "Symptoms and treatment",
            "source_type": "who",
        }
    ]

    out = normalize_sources(raw_sources)

    assert len(out) == 1
    assert out[0].title == "[WHO] Mpox article"
    assert out[0].excerpt == "Symptoms and treatment"


def test_normalize_sources_adds_private_prefix():
    raw_sources = [
        {
            "title": "private_notes.md",
            "excerpt": "Internal note",
            "source_type": "user_upload",
        }
    ]

    out = normalize_sources(raw_sources)

    assert len(out) == 1
    assert out[0].title == "[Privé] private_notes.md"
    assert out[0].excerpt == "Internal note"


def test_normalize_sources_fallback_values():
    raw_sources = [{}]

    out = normalize_sources(raw_sources)

    assert len(out) == 1
    assert out[0].title == "Source inconnue"
    assert out[0].excerpt == ""