from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "siteid",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
    "yptr",
}


def canonicalize_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
            if key.lower() not in TRACKING_QUERY_PARAMS
        ]
    )

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if scheme in {"http", "https"}:
        return urlunsplit((scheme, netloc, parsed.path, query, ""))

    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))
