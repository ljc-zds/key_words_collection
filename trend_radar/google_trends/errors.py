class TrendsRateLimited(RuntimeError):
    """An explicit HTTP rate/access restriction; do not try another backend."""


class MissingTrendsData(Exception):
    """Partial page success; defer missing data without immediate retries."""
