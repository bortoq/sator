"""Series name matching: extract show name from query/title and verify match.

This module solves the problem of false positives when a tracker returns
results where the queried term appears in an *episode title* rather than
the *series name*. For example, searching for "Lost" should not return
"The Acolyte S01E01 Lost Found" — "Lost" is the episode title, not the show.

Usage:
    from sator.series_match import extract_series_name_from_title, series_name_matches

    result_series = extract_series_name_from_title(torrent_title)
    if result_series and not series_name_matches("Lost", result_series):
        # Result is for a different series — skip it
"""

import re

# Pattern to detect season/episode markers in torrent titles.
# Matches: S01, S01E01, S01E21, etc. with leading dots/spaces/hyphens.
_SEASON_EP_PATTERN = re.compile(
    r'(?:^|[\s.\-_,;:+\[\]])'
    r'S(?P<season>\d{2,})'
    r'(?:E(?P<episode>\d{2,}))?'
    r'(?=[\s.\-_,;:+\[\]]|$)',
    re.IGNORECASE,
)

# Pattern to strip season/ep suffix from a user query (appended by series.py).
_QUERY_SEASON_EP_SUFFIX = re.compile(
    r'\s+S\d{2,}(?:E\d{2,})?\s*$',
    re.IGNORECASE,
)

# Pattern to strip a trailing year (can be appended by TMDB enrich).
_QUERY_YEAR_SUFFIX = re.compile(r'\s+\d{4}\s*$')


def extract_series_name_from_query(query: str) -> str:
    """Extract the series name from a query string.

    Handles queries like:
        "Lost S02E21"       -> "Lost"
        "Lost 2004 S02"     -> "Lost"
        "The Office S05E14" -> "The Office"
        "Inception 2010"    -> "Inception"
        "SimpleQuery"       -> "SimpleQuery"

    Returns the cleaned series name, or an empty string if the result
    would be empty after stripping.
    """
    q = query.replace('_', ' ').replace('.', ' ').replace('-', ' ')
    # Remove season/ep marker suffix
    q = _QUERY_SEASON_EP_SUFFIX.sub('', q)
    # Remove trailing year (from TMDB enrich or user input)
    q = _QUERY_YEAR_SUFFIX.sub('', q)
    q = q.strip()
    # Remove multiple spaces
    q = re.sub(r'\s+', ' ', q)
    # If after stripping only a bare Sxx marker remains (e.g. query="S01"),
    # strip it as well — no series name could be extracted.
    q = re.sub(r'^S\d{2,}(?:E\d{2,})?$', '', q, flags=re.IGNORECASE)
    return q.strip()


def extract_series_name_from_title(title: str) -> str:
    """Extract the series name from a torrent/release title.

    Takes everything *before* the first season/episode marker (S01, S01E01).
    If no season marker is found (e.g., a movie), returns an empty string
    to indicate "cannot determine — pass through".

    Examples:
        "The.Acolyte.S01E01.Lost.Found.1080p.WEB-DL-GROUP"
            -> "The Acolyte"
        "Lost.S02E21.1080p.WEB-DL.GROUP.mkv"
            -> "Lost"
        "Show.Name.S01.COMPLETE.1080p.WEB-DL-GROUP"
            -> "Show Name"
        "Movie.2024.1080p.BluRay-GROUP"
            -> ""   (no season marker)
        "Show.Name[S01E01].1080p"
            -> "Show Name"
    """
    t = title.replace('_', ' ').replace('.', ' ').replace('-', ' ')
    # Remove common file extensions
    t = re.sub(
        r'\.(mkv|mp4|avi|m2ts|ts|m4v|mov|wmv|flv|webm|mp3|flac|m4a|torrent)$',
        '', t, flags=re.IGNORECASE,
    )
    # Find the first season/episode marker BEFORE stripping brackets,
    # so the marker position is preserved even if enclosed in brackets.
    m = _SEASON_EP_PATTERN.search(t)
    if m:
        t = t[:m.start()]
    else:
        # No season marker found — cannot determine the series name.
        # This typically means the result is a movie, or a complete-series pack
        # without individual season markers. Pass through.
        return ''

    # Strip bracket-enclosed content (e.g., [SubGroup])
    t = re.sub(r'\[.*?\]', ' ', t)
    t = re.sub(r'\(.*?\)', ' ', t)
    t = re.sub(r'\{.*?\}', ' ', t)
    # Collapse whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    # Remove leading/trailing separators
    t = re.sub(r'^[\s.\-_,;:+]+|[\s.\-_,;:+]+$', '', t)

    return t.strip()


def series_name_matches(query_series: str, result_series: str) -> bool:
    """Check whether the result series name matches the queried series.

    Returns *True* if the names match, *False* if they clearly don't.
    Returns *True* when either name is empty (cannot determine — pass
    through to avoid false negatives).

    Matching strategy (case-insensitive):
        1. Exact equality (after stripping articles like "the", "a", "an")
        2. One name contains the other
        3. All non-article query tokens appear in the result name
    """
    if not query_series or not result_series:
        return True  # Cannot determine — let the result pass

    q = query_series.lower().strip()
    r = result_series.lower().strip()

    # Strip common leading articles for comparison
    _articles = {'the ', 'a ', 'an '}
    q_stripped = q
    r_stripped = r
    for art in _articles:
        if q_stripped.startswith(art):
            q_stripped = q_stripped[len(art):]
        if r_stripped.startswith(art):
            r_stripped = r_stripped[len(art):]

    # 1. Exact match
    if q_stripped == r_stripped or q == r:
        return True

    # 2. Containment (one is a substring of the other)
    if q_stripped in r_stripped or r_stripped in q_stripped:
        return True

    # 3. Token overlap: all non-article query tokens must appear in result
    _stop = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'the'}
    q_tokens = {w for w in q.split() if w not in _stop}
    r_tokens = {w for w in r.split() if w not in _stop}

    if q_tokens and r_tokens and q_tokens.issubset(r_tokens):
        return True

    return False

def season_ep_in_query_matches_title(query: str, title: str) -> bool:
    """Check if the result title contains the expected season/episode from query.

    Supports multiple season/episode formats found on trackers:
        S02E21 / S02.E21     -> season 2, episode 21
        2x21 / 2×21         -> season 2, episode 21  (common on TPB)
        Season 2 Episode 21  -> season 2, episode 21
        S02                  -> season 2 only (season pack)

    Returns True if:
      - Query has no season marker (movies/plain queries pass through)
      - Query has specific episode (S02E21) and result matches that episode
      - Query has season only (S02) and result is from that season
        (any episode or season pack from the matching season is acceptable)
    Returns False otherwise.
    """
    # ── Extract expected season/episode numbers from query ──
    qm = re.search(r'S(?P<qs>\d{2,})(?:E(?P<qe>\d{2,}))?', query, re.IGNORECASE)
    if not qm:
        return True  # No season constraint in query — pass through

    q_season = int(qm.group('qs'))
    q_episode = int(qm.group('qe')) if qm.group('qe') else None

    # ── Normalize result title ──
    title_norm = title.replace('_', ' ').replace('.', ' ').replace('-', ' ')

    # Helper: check if any occurrence of a pattern matches the expected season/ep
    def _check_episode(season: int, episode: int) -> bool:
        if q_episode is not None:
            return q_season == season and q_episode == episode
        return q_season == season  # season-only: any episode from the right season is OK

    # 1. Standard SxxExx / Sxx.Exx format
    for rm in re.finditer(r'S(\d{2,})\s*[. ]?\s*E(\d{2,})', title_norm, re.IGNORECASE):
        if _check_episode(int(rm.group(1)), int(rm.group(2))):
            return True

    # 2. NxNN format (common on PirateBay: 2x21, 2x21, 2×21)
    for rm in re.finditer(r'(?:^|\D)(\d{1,2})\s*[xX×]\s*(\d{1,2})(?:\D|$)', title_norm):
        if _check_episode(int(rm.group(1)), int(rm.group(2))):
            return True

    # 3. "Season N Episode N" / "Season N Ep N" format
    for rm in re.finditer(r'Season\s+(\d{1,2})\s+E[pisode]*\.?\s*(\d{1,2})',
                          title_norm, re.IGNORECASE):
        if _check_episode(int(rm.group(1)), int(rm.group(2))):
            return True

    # 4. Standalone Sxx (season pack, no episode) — only acceptable for season-only query
    if q_episode is None:
        rm = re.search(r'S(\d{2,})(?:\s|$|\Z)', title_norm, re.IGNORECASE)
        if rm and q_season == int(rm.group(1)):
            return True

    # No matching format found
    return False

    # ── Season-only query (q_episode is None) ──
    # If the title contains any specific episode markers (SxxExx, NxNN, words),
    # it's not a season pack — reject (unless we already returned True above).
    if has_sxx_exx or has_nxnn or has_season_ep:
        return False

    # Try standalone Sxx (season pack, no episode number)
    rm = re.search(r'S(\d{2,})(?:\s|$|\Z)', title_norm, re.IGNORECASE)
    if rm:
        r_season = int(rm.group(1))
        return q_season == r_season

    # No recognizable season/ep format found in result title
    return False

    # Try standalone Sxx (season pack, no episode)
    rm = re.search(r'S(\d{2,})(?:\s|$|\Z)', title_norm, re.IGNORECASE)
    if rm:
        r_season = int(rm.group(1))
        if q_episode is not None:
            return False  # Season pack doesn't contain the specific episode
        return q_season == r_season

    # Try "NxNN" format (2x21, 2x21, 2×21) — common on PirateBay and other indexers
    rm = re.search(r'(?:^|\D)(\d{1,2})\s*[xX×]\s*(\d{1,2})(?:\D|$)', title_norm)
    if rm:
        r_season = int(rm.group(1))
        r_episode = int(rm.group(2))
        if q_episode is not None:
            return q_season == r_season and q_episode == r_episode
        return q_season == r_season

    # Try "Season N Episode N" / "Season N Ep N" format
    rm = re.search(r'Season\s+(\d{1,2})\s+E[pisode]*\.?\s*(\d{1,2})', title_norm, re.IGNORECASE)
    if rm:
        r_season = int(rm.group(1))
        r_episode = int(rm.group(2))
        if q_episode is not None:
            return q_season == r_season and q_episode == r_episode
        return q_season == r_season

    # No recognizable season/ep format found in result title.
    # If query specified a specific episode, reject (mismatch).
    # If query only specified season, could be a non-standard format — reject.
    # If query had no constraints (shouldn't reach here), pass through.
    return False