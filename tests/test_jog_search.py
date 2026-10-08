from polcomp.config import JogSearchConfig
from polcomp.jog_search import (
    JogSearch,
    JogSearchState
)


def test_initial_state():
    search = JogSearch(
        JogSearchConfig()
    )

    assert search.state == JogSearchState()