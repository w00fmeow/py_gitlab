#!/usr/bin/env python3
import re
import hashlib
import asyncio
from functools import wraps
from typing import List
from src.logger import logger


def escape_char_in_str(input_str=None, char_to_escape=None, escape_with="\\"):
    return re.sub(f"\{char_to_escape}", f'{escape_with}{char_to_escape}', input_str)


def escape_chars_in_str(input_str='', chars_to_escape=[], escape_with="\\"):
    result = input_str

    for char_to_escape in chars_to_escape:
        result = escape_char_in_str(
            input_str=result, char_to_escape=char_to_escape, escape_with=escape_with)

    return result


def retry_on_fail(func):
    @wraps(func)
    async def wrapper_func(*args, **kwargs):
        result = None
        succeeded = False

        loop_iter_count = 0

        while not succeeded:
            try:
                result = await func(*args, **kwargs)
                succeeded = True
            except Exception as e:
                logger.error(e)
                await asyncio.sleep(3)

            loop_iter_count += 1

        return result
    return wrapper_func


def string_contains_user_mention(note_body: str, user_name: str) -> bool:
    try:
        pattern = f".*@{user_name}.*"
        return bool(re.match(pattern, note_body))
    except Exception as e:
        logger.error(e)
    return False


def parse_string_of_integers_to_list(input: str) -> List[int]:
    try:
        return [int(x) for x in input.split(',')]
    except Exception as e:
        logger.error(e)


def parse_string_of_strings_to_list(input: str) -> List[str]:
    try:
        return input.split(',')
    except Exception as e:
        logger.error(e)


def parse_string_to_domain(input: str) -> str:
    try:
        pattern = "(?:http(s)?://)?(?P<domain>\w+\.\w+)((/)?.*)?"
        result = re.match(pattern, input)
        return result.group("domain")
    except Exception as e:
        logger.error(e)


def get_notes_hash(notes=[]):
    hasher = hashlib.md5()

    for note in notes:
        buf = str(note["id"]).encode()
        hasher.update(buf)

    return hasher.hexdigest()
