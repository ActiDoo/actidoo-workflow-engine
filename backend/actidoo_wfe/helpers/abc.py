from enum import Enum


class AutoName(Enum):
    """Autoname enum, so the value is set based on the name

    class Directions(AutoEnum):
        UP = auto()
        DOWN = auto()

    """

    def _generate_next_value_(name, start, count, last_values):
        return name
