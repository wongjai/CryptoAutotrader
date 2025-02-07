"""
Configuration file. Must be version-controlled.

"""

from enum import Enum


class Color(Enum):
    """Colors to alter console output"""

    PURPLE: str = "\033[95m"
    CYAN: str = "\033[96m"
    DARK_CYAN: str = "\033[36m"
    BLUE: str = "\033[94m"
    GREEN: str = "\033[92m"
    YELLOW: str = "\033[93m"
    RED: str = "\033[91m"
    BOLD: str = "\033[1m"
    ITALIC: str = "\x1B[3m"
    UNDERLINE: str = "\033[4m"
    END: str = "\033[0m"
