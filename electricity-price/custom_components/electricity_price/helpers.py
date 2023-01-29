"""
Helper functions for integration setup
"""
from typing import Any
import voluptuous as vol


def number(value: Any) -> float:
    try:
        return float(value)
    except ValueError:
        raise vol.Invalid('You should input a number in DKK. Either a whole number (integer) or decimal number (float)')


def percentage(value: Any) -> float:
    try:
        return float(value)
    except ValueError:
        raise vol.Invalid('You should input a number in percentage, e.g. "25" for 25 %.')
