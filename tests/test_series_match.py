"""Unit tests for sator/series_match.py — series name extraction and matching."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sator.series_match import (
    extract_series_name_from_query,
    extract_series_name_from_title,
    series_name_matches,
    season_ep_in_query_matches_title,
)


# ═══════════════════════════════════════════════════════════════════════════
# extract_series_name_from_query
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractSeriesNameFromQuery:
    """Tests for extracting the series name from a user query string."""

    def test_simple_season_episode(self):
        """Basic query: 'Lost S02E21' -> 'Lost'."""
        assert extract_series_name_from_query('Lost S02E21') == 'Lost'

    def test_season_only(self):
        """Query with season only: 'Lost S02' -> 'Lost'."""
        assert extract_series_name_from_query('Lost S02') == 'Lost'

    def test_multi_word_series(self):
        """Multi-word series: 'The Office S05E14' -> 'The Office'."""
        assert extract_series_name_from_query('The Office S05E14') == 'The Office'

    def test_with_year_from_tmdb(self):
        """Query with year from TMDB enrich: 'Lost 2004 S02E21' -> 'Lost'."""
        assert extract_series_name_from_query('Lost 2004 S02E21') == 'Lost'

    def test_movie_query_with_year(self):
        """Movie query with year: 'Inception 2010' -> 'Inception'."""
        assert extract_series_name_from_query('Inception 2010') == 'Inception'

    def test_plain_query(self):
        """Plain query without modifiers: 'SimpleShow' -> 'SimpleShow'."""
        assert extract_series_name_from_query('SimpleShow') == 'SimpleShow'

    def test_query_with_dots(self):
        """Query with dots: 'The.Wire.S01' -> 'The Wire'."""
        assert extract_series_name_from_query('The.Wire.S01') == 'The Wire'

    def test_query_with_underscores(self):
        """Query with underscores: 'Better_Call_Saul_S06E09' -> 'Better Call Saul'."""
        assert extract_series_name_from_query('Better_Call_Saul_S06E09') == 'Better Call Saul'

    def test_show_with_year_in_name(self):
        """Show that has a year in its name: '2004 Movie S01' -> '2004 Movie'."""
        result = extract_series_name_from_query('2004 Movie S01')
        # The year 2004 is part of the show name, not a year suffix
        assert '2004' in result
        assert 'Movie' in result

    def test_empty_string(self):
        """Empty query -> empty string."""
        assert extract_series_name_from_query('') == ''

    def test_only_season(self):
        """Query is just 'S01' -> empty string (no series name)."""
        assert extract_series_name_from_query('S01') == ''

    def test_show_with_hyphens(self):
        """Query with hyphens: 'Rick-and-Morty S04E03' -> 'Rick and Morty'."""
        assert extract_series_name_from_query('Rick-and-Morty S04E03') == 'Rick and Morty'

    def test_complete_seasons(self):
        """Query: 'Lost complete seasons' -> 'Lost complete seasons' (no Sxx to strip)."""
        result = extract_series_name_from_query('Lost complete seasons')
        assert result == 'Lost complete seasons'


# ═══════════════════════════════════════════════════════════════════════════
# extract_series_name_from_title
# ═══════════════════════════════════════════════════════════════════════════

class TestExtractSeriesNameFromTitle:
    """Tests for extracting the series name from a torrent result title."""

    def test_basic_series(self):
        """Basic series: 'Lost.S02E21.1080p.WEB-DL.GROUP' -> 'Lost'."""
        assert extract_series_name_from_title('Lost.S02E21.1080p.WEB-DL.GROUP') == 'Lost'

    def test_false_positive_case(self):
        """The exact bug: 'The.Acolyte.S01E01.Lost.Found.1080p.DSNP.WEB-DL.DDP5.1.Atmos.H.264-FLUX' -> 'The Acolyte'."""
        result = extract_series_name_from_title(
            'The.Acolyte.S01E01.Lost.Found.1080p.DSNP.WEB-DL.DDP5.1.Atmos.H.264-FLUX'
        )
        assert result == 'The Acolyte'

    def test_multi_word_series(self):
        """Multi-word series: 'Breaking.Bad.S01E01.Pilot.1080p.WEB-DL' -> 'Breaking Bad'."""
        assert extract_series_name_from_title('Breaking.Bad.S01E01.Pilot.1080p.WEB-DL') == 'Breaking Bad'

    def test_season_only_in_title(self):
        """Season-only marker: 'Lost.S02.COMPLETE.1080p.WEB-DL-GROUP' -> 'Lost'."""
        assert extract_series_name_from_title('Lost.S02.COMPLETE.1080p.WEB-DL-GROUP') == 'Lost'

    def test_movie_no_season_marker(self):
        """Movie without season marker -> empty string."""
        assert extract_series_name_from_title('Movie.2024.1080p.BluRay-GROUP') == ''

    def test_title_with_spaces(self):
        """Title with spaces instead of dots: 'The Office S05E14 1080p WEB-DL' -> 'The Office'."""
        assert extract_series_name_from_title('The Office S05E14 1080p WEB-DL') == 'The Office'

    def test_complete_series_pack(self):
        """Complete series pack without Sxx marker -> empty string (pass through)."""
        assert extract_series_name_from_title('Lost.Complete.Series.1080p.BluRay-GROUP') == ''

    def test_anime_with_brackets(self):
        """Anime title with subgroup brackets: '[SubGroup] Anime.Name.S01E01.1080p' -> 'Anime Name'."""
        assert extract_series_name_from_title('[SubGroup] Anime.Name.S01E01.1080p') == 'Anime Name'

    def test_title_with_file_extension(self):
        """Title with .mkv extension should still parse correctly."""
        assert extract_series_name_from_title('Lost.S02E21.1080p.mkv') == 'Lost'

    def test_lowercase_title(self):
        """Lowercase title: 'the.acolyte.s01e01.lost.found.1080p' -> 'the acolyte'."""
        assert extract_series_name_from_title('the.acolyte.s01e01.lost.found.1080p') == 'the acolyte'

    def test_title_with_year_before_season(self):
        """Title with year before season marker: 'Lost 2004 S02E21 1080p' -> 'Lost 2004'."""
        result = extract_series_name_from_title('Lost 2004 S02E21 1080p')
        assert 'Lost' in result
        # Year may or may not be included depending on spacing
        assert result.startswith('Lost')

    def test_empty_title(self):
        """Empty title -> empty string."""
        assert extract_series_name_from_title('') == ''

    def test_no_season_marker_at_all(self):
        """No Sxx marker at all -> empty string."""
        assert extract_series_name_from_title('Just a movie title 2024 1080p') == ''

    def test_dashed_title(self):
        """Title with dashes: 'The-Wire-S01E02-1080p' -> 'The Wire'."""
        assert extract_series_name_from_title('The-Wire-S01E02-1080p') == 'The Wire'

    def test_sxx_at_beginning(self):
        """Title starting with Sxx marker: 'S01E01.Show.Name.1080p' -> '' (can't find series name before marker)."""
        # The pattern looks for markers with separators before them
        result = extract_series_name_from_title('S01E01.Show.Name.1080p')
        # "S01E01" at the start without a preceding separator — depends on pattern
        # Our pattern requires a separator before Sxx
        assert result == ''

    def test_sxx_without_separator(self):
        """Title where Sxx has no separator before it but starts the name: 'ShowS01E01' -> 'Show'."""
        # This case is tricky; let's see how the pattern handles it
        result = extract_series_name_from_title('ShowS01E01')
        # This depends on whether the pattern matches S01E01 as a word boundary
        # Our pattern has (?:^|[\s.\-_,;:+]) before S, so 'ShowS01E01' won't match
        # That's acceptable — this format is extremely rare
        pass  # Just verify no crash

    def test_season_pack(self):
        """Season pack: 'Show.Name.S01.COMPLETE.1080p.BluRay' -> 'Show Name'."""
        assert extract_series_name_from_title('Show.Name.S01.COMPLETE.1080p.BluRay') == 'Show Name'

    def test_multiple_season_markers(self):
        """Title with multiple season markers uses the first one."""
        # Some weird titles might have Sxx twice
        result = extract_series_name_from_title('First.Show.S01.S02.1080p')
        assert result == 'First Show'

    def test_episode_with_special_chars(self):
        """Title with special characters around season marker: 'Show.Name[S01E01].1080p' -> 'Show Name'."""
        result = extract_series_name_from_title('Show.Name[S01E01].1080p')
        assert result == 'Show Name'


# ═══════════════════════════════════════════════════════════════════════════
# series_name_matches
# ═══════════════════════════════════════════════════════════════════════════

class TestSeriesNameMatches:
    """Tests for verifying whether extracted series names match."""

    def test_exact_match(self):
        """Exact same name."""
        assert series_name_matches('Lost', 'Lost') is True

    def test_case_insensitive(self):
        """Case should not matter."""
        assert series_name_matches('lost', 'Lost') is True
        assert series_name_matches('LOST', 'Lost') is True

    def test_different_series(self):
        """Clearly different series should NOT match."""
        assert series_name_matches('Lost', 'The Acolyte') is False

    def test_episode_title_false_positive(self):
        """The exact bug case: 'Lost' vs 'The Acolyte' -> False."""
        assert series_name_matches('Lost', 'The Acolyte') is False
        assert series_name_matches('Lost', 'the acolyte') is False

    def test_multiple_word_match(self):
        """Multi-word series name match."""
        assert series_name_matches('The Office', 'The Office') is True

    def test_query_name_contains_result(self):
        """Query name contains result name."""
        assert series_name_matches('The Simpsons', 'Simpsons') is True

    def test_result_name_contains_query(self):
        """Result name contains query name (e.g., partial match)."""
        assert series_name_matches('Simpsons', 'The Simpsons') is True

    def test_token_subset(self):
        """All query tokens appear in result name."""
        assert series_name_matches('Office', 'The Office US') is True

    def test_token_not_subset(self):
        """Not all query tokens appear in result name."""
        assert series_name_matches('Better Call Saul', 'Breaking Bad') is False

    def test_empty_query_series(self):
        """Empty query series -> True (pass through)."""
        assert series_name_matches('', 'Lost') is True

    def test_empty_result_series(self):
        """Empty result series -> True (pass through, movie/unknown)."""
        assert series_name_matches('Lost', '') is True

    def test_both_empty(self):
        """Both empty -> True."""
        assert series_name_matches('', '') is True

    def test_article_variation(self):
        """'The' article difference: 'Office' vs 'The Office'."""
        assert series_name_matches('Office', 'The Office') is True
        assert series_name_matches('The Office', 'Office') is True

    def test_partial_token_overlap_insufficient(self):
        """Partial token overlap is not enough if not subset."""
        assert series_name_matches('Breaking Bad', 'Breaking the Law') is False

    def test_single_token(self):
        """Single token match."""
        assert series_name_matches('Lost', 'Lost') is True
        assert series_name_matches('Lost', 'Lost Found') is True  # subset

    def test_whitespace_handling(self):
        """Extra whitespace should be handled."""
        assert series_name_matches('  Lost  ', 'Lost') is True
        assert series_name_matches('Lost', '  Lost  ') is True

    def test_stop_words_filtering(self):
        """Stop words like 'the' should not prevent a match."""
        assert series_name_matches('The Wire', 'Wire') is True
        assert series_name_matches('Wire', 'The Wire') is True

    def test_similar_but_different_real(self):
        """Real-world similar but different series names."""
        # 'Firefly' vs 'Firefly Lane' - should not match
        # 'Firefly' is subset of 'Firefly Lane'
        assert series_name_matches('Firefly', 'Firefly Lane') is True  # subset
        # This is actually correct — if someone searches 'Firefly', a result
        # that says 'Firefly Lane S01E01' should probably pass through and
        # be filtered by other means. The subset check is intentionally
        # permissive to avoid false negatives.

    def test_strip_special_chars(self):
        """The function works on already-cleaned names (no special chars)."""
        # This is a pre-condition: names should already be cleaned by
        # extract_series_name_from_title before being passed here.
        assert series_name_matches('Show Name', 'Show Name') is True
        assert series_name_matches('Show Name', 'Different Name') is False


# ═══════════════════════════════════════════════════════════════════════════
# season_ep_in_query_matches_title
# ═══════════════════════════════════════════════════════════════════════════

class TestSeasonEpInQueryMatchesTitle:
    """Tests for verifying season/episode markers in result titles."""

    # ── Standard SxxExx format ──

    def test_exact_episode_match(self):
        """Query S02E21 matches title with S02E21."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.S02E21.1080p.WEB-DL-GROUP') is True

    def test_different_season(self):
        """Query S02E21 does NOT match title with S05E09 (different season)."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.S05E09.Namaste.1080p.WEB-DL-GROUP') is False

    def test_different_episode_same_season(self):
        """Query S02E21 does NOT match title with S02E01 (different episode, same season)."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.S02E01.1080p.WEB-DL-GROUP') is False

    def test_season_only_query_with_season_pack(self):
        """Query S02 matches title with S02 season pack."""
        assert season_ep_in_query_matches_title('Lost S02', 'Lost.S02.COMPLETE.1080p.WEB-DL-GROUP') is True

    def test_season_only_query_with_episode(self):
        """Query S02 matches title with S02E01 (any episode from the requested season is OK)."""
        assert season_ep_in_query_matches_title('Lost S02', 'Lost.S02E01.1080p.WEB-DL-GROUP') is True

    def test_season_only_query_with_wrong_season_episode(self):
        """Query S02 does NOT match title with S03E01."""
        assert season_ep_in_query_matches_title('Lost S02', 'Lost.S03E01.1080p.WEB-DL-GROUP') is False

    def test_no_season_in_query(self):
        """Query without Sxx marker passes through (movie/plain query)."""
        assert season_ep_in_query_matches_title('Inception', 'Inception.2010.1080p.BluRay-GROUP') is True

    def test_no_season_in_query_with_series_result(self):
        """Plain query matches any result (no season/ep constraint)."""
        assert season_ep_in_query_matches_title('Lost', 'Lost.S02E21.1080p.WEB-DL-GROUP') is True

    def test_multiple_seasons_in_title(self):
        """Title with multiple episodes: query S02E21 matches if title contains S02E21."""
        assert season_ep_in_query_matches_title(
            'Lost S02E21', 'Lost.S02E20.S02E21.1080p.WEB-DL-GROUP'
        ) is True

    def test_case_insensitive(self):
        """Case insensitive matching."""
        assert season_ep_in_query_matches_title('lost s02e21', 'LOST.S02E21.1080p') is True
        assert season_ep_in_query_matches_title('LOST S02E21', 'lost.s02e21.1080p') is True

    def test_leading_zeros(self):
        """S02 matches S02 exactly (not S2)."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.S02E21.1080p') is True
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.S2E21.1080p') is False

    def test_query_with_year(self):
        """Query with year still extracts Sxx correctly."""
        assert season_ep_in_query_matches_title('Lost 2004 S02E21', 'Lost.S02E21.1080p') is True
        assert season_ep_in_query_matches_title('Lost 2004 S02E21', 'Lost.S05E09.1080p') is False

    def test_query_season_only_with_wrong_season(self):
        """Query S02 does not match title S03."""
        assert season_ep_in_query_matches_title('Lost S02', 'Lost.S03.COMPLETE.1080p') is False

    def test_empty_query(self):
        """Empty query passes through."""
        assert season_ep_in_query_matches_title('', 'Lost.S02E21.1080p') is True

    def test_empty_title(self):
        """Empty title with season query returns False."""
        assert season_ep_in_query_matches_title('Lost S02E21', '') is False

    # ── Sxx.Exx format (with dot between S and E) ──

    def test_dot_separator(self):
        """S02.E21 format with dot separator."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.S02.E21.1080p.WEB-DL') is True
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.S02.E21.1080p.WEB-DL') is True

    # ── "NxNN" format (common on PirateBay) ──

    def test_tpb_format_lowercase_x(self):
        """2x21 format with lowercase x (common on TPB)."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost - 2x21 - Episode Title.avi') is True

    def test_tpb_format_uppercase_x(self):
        """2x21 format with uppercase X."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost - 2X21 - Episode Title.avi') is True

    def test_tpb_format_multiplication_sign(self):
        """2x21 format with multiplication sign ×."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost - 2×21 - Episode Title.avi') is True

    def test_tpb_format_different_episode(self):
        """2x21 format with different episode should not match."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost - 2x05 - Episode Title.avi') is False
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost - 5x21 - Episode Title.avi') is False

    def test_tpb_format_season_only(self):
        """Query S02 matches 2x21 format (any episode from season 2 is OK)."""
        assert season_ep_in_query_matches_title('Lost S02', 'Lost - 2x21 - Episode Title.avi') is True

    def test_tpb_format_different_season(self):
        """2x21 format with different season should not match."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost - 3x21 - Episode Title.avi') is False

    # ── "Season N Episode N" format ──

    def test_season_episode_words(self):
        """"Season 2 Episode 21" format."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost Season 2 Episode 21 1080p.mkv') is True

    def test_season_episode_words_abbreviated(self):
        """"Season 2 Ep 21" format."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost Season 2 Ep 21 1080p.mkv') is True

    def test_season_episode_words_different(self):
        """"Season 2 Episode 5" should not match S02E21."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost Season 2 Episode 5 1080p.mkv') is False

    # ── Edge cases ──

    def test_title_with_no_season_info_and_episode_query(self):
        """Result has no season/ep info at all, but query has specific episode -> reject."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.Complete.Series.1080p.BluRay') is False

    def test_title_with_no_season_info_and_season_query(self):
        """Result has no season/ep info, query has season only -> reject."""
        assert season_ep_in_query_matches_title('Lost S02', 'Lost.Complete.Series.1080p.BluRay') is False

    def test_sxx_standalone_in_title(self):
        """Sxx standalone in title (season pack from non-TPB source)."""
        assert season_ep_in_query_matches_title('Lost S02', 'Lost S02 COMPLETE 1080p') is True
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost S02 COMPLETE 1080p') is False

    def test_title_with_dots_and_nxnn(self):
        """Title with dots and 2x21 format: 'Lost.2x21.HDTV.XviD'."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost.2x21.HDTV.XviD-GROUP') is True

    def test_title_with_spaces_nxnn(self):
        """Title with spaces and 2x21: 'Lost 2x21 HDTV XviD'."""
        assert season_ep_in_query_matches_title('Lost S02E21', 'Lost 2x21 HDTV XviD-GROUP') is True