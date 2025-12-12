import secrets
import string
from textwrap import wrap


def create_random_string(length=30, characters=(string.ascii_letters + string.digits + string.punctuation)):
    """Generates a random string"""
    return "".join(secrets.choice(characters) for x in range(length))


def lstrip_word(text, word):
    return text[len(word) :] if text[: len(word)] == word else text  # fmt: off


def rstrip_word(text, word):
    return text[: -len(word)] if text[-len(word) :] == word else text  # fmt: off


def is_true_string(value):
    true_strings = {"1", "true", "True", "yes", "Yes", "y", "Y", "t", "T", "on", "On"}
    return str(value).strip() in true_strings


def is_false_string(value):
    false_strings = {"0", "false", "False", "no", "No", "n", "N", "f", "F", "off", "Off"}
    return str(value).strip() in false_strings


def boolean_or_string_list(value: str) -> list[str] | bool | None:
    ret = None
    if is_true_string(value):
        ret = True
    elif is_false_string(value):
        ret = False
    elif isinstance(value, str):
        ret = [x.strip() for x in value.split(",")]
    return ret


def get_boxed_text(text, width=100):
    """Formats the provided text into a boxed layout with a border.

    Args:
        text (str): The input text to be formatted, which may contain
        multiple lines separated by newline characters.

    Returns:
        str: A string representing the boxed text layout, including
        the top and bottom borders.
    """
    wrapped_lines = []
    for line in text.split("\n"):
        wrapped_lines.extend(wrap(line, width=width) or [""])

    max_length = max(len(line) for line in wrapped_lines)
    border = "+" + "-" * (max_length + 2) + "+" + "\n"
    boxed = border

    for line in wrapped_lines:
        boxed += f"| {line.ljust(max_length)} |" + "\n"
    boxed += border
    return boxed
