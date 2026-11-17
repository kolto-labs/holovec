"""Conservative publication filter, not a copyright determination.

Plain-text conversion removes reliable section boundaries; hold whole records
with headings that may introduce third-party text pending individual review.
"""
import re
PATTERN=re.compile(r"(?im)^(?:publisher(?:'s|s’) summary|opening crawl|official description|publisher(?:'s|s’) description|back cover(?: (?:description|summary|blurb))?)\s*$")
def requires_review(text):
    return bool(PATTERN.search(text or ''))


def is_held_url(url):
    """Exclude a specifically held legacy source from snapshot reacquisition."""
    from urllib.parse import unquote
    return unquote(url or '').replace(' ', '_').casefold().rstrip('/') == (
        'https://starwars.fandom.com/wiki/star_wars:_knights_of_the_old_republic_(comic_series)'
    )
