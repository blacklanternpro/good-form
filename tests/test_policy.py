from policy import accept_url, is_blacklisted, normalize_host, whitelist_bias


def test_pinterest_and_amazon_are_blocked():
    assert is_blacklisted("www.pinterest.com")
    assert is_blacklisted("uk.pinterest.com")
    assert is_blacklisted("amazon.com")
    assert is_blacklisted("smile.amazon.com")
    assert accept_url("https://www.etsy.com/listing/1") is None
    assert accept_url("https://reddit.com/r/something") is None
    assert accept_url("https://nytimes.com/style") is None
    assert accept_url("https://yahoo.com/news") is None


def test_tumblr_apex_blocked_but_subdomain_kept():
    assert is_blacklisted("tumblr.com")
    assert not is_blacklisted("cool-scans.tumblr.com")
    assert accept_url("https://cool-scans.tumblr.com/post/1") == "cool-scans.tumblr.com"


def test_whitelist_bias_ranks_archives_higher():
    assert whitelist_bias("neon.neocities.org") > whitelist_bias("random-personal.example")
    assert whitelist_bias("someone.tumblr.com") > 0
    assert whitelist_bias("are.na") > 0
    assert whitelist_bias("notes.substack.com") > 0
    assert whitelist_bias("user.github.io") > 0


def test_normalize_strips_www_and_requires_http():
    assert normalize_host("https://www.Example.com/path") == "example.com"
    assert normalize_host("ftp://x.com") is None
    assert normalize_host("") is None
