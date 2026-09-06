from categorizer import tag_text


def test_multi_tag_from_title_and_url():
    tags = tag_text("Vaporwave Zine scans", "https://example.neocities.org/posts")
    assert "vaporwave" in tags
    assert "zine" in tags
    assert "neocities" in tags
    assert "scan" in tags
    assert "Unsorted" not in tags


def test_unsorted_when_nothing_matches():
    assert tag_text("Hello World", "https://quiet.example/about") == ["Unsorted"]


def test_scan_does_not_match_scandinavia():
    tags = tag_text("Scandinavia travel notes", "https://north.example/journal")
    assert "scan" not in tags


def test_arena_from_are_na_host():
    tags = tag_text("channel", "https://www.are.na/user/block")
    assert "arena" in tags
