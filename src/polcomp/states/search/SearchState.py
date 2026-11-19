import enum


class SearchState(enum.Enum):
    START = enum.auto()

    # Empirical Jacobian SEARCH.
    JACOBIAN_PROBE_MOVE = enum.auto()
    JACOBIAN_PROBE_MEASURE = enum.auto()
    JACOBIAN_PROBE_RETURN = enum.auto()
    JACOBIAN_APPLY = enum.auto()
    JACOBIAN_LINE_MOVE = enum.auto()
    JACOBIAN_LINE_MEASURE = enum.auto()
    JACOBIAN_LINE_RETURN = enum.auto()

    # Existing rolling-jog SEARCH, retained as a fallback.
    JOG_POSITIVE = enum.auto()
    RETURN_FROM_POSITIVE = enum.auto()
    JOG_NEGATIVE = enum.auto()
    RETURN_TO_BEST = enum.auto()
    RETURN_TO_LOCK = enum.auto()