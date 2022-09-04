#!/usr/bin/env python3
import json
from src.http_service import HttpService
from src.logger import logger
from src.utils import escape_chars_in_str


def format_note_message(mr=None, note=None):
    title_escaped = escape_chars_in_str(
        input_str=mr['title'], chars_to_escape=['-', '+', "_", "*", "[", "`", "."])

    body_escaped = escape_chars_in_str(
        input_str=note['body'], chars_to_escape=['-', '+', "_", "*", "[", "`", "."])

    note_url = f"{mr['web_url']}#note_{note['id']}"
    url_formatted = f"[{title_escaped}]({note_url})"

    title = f"[ gitlab ]: new comment on MR:\n{url_formatted}"
    body = f"_{body_escaped}_"
    footer = f"🗒 by {note['author']['name']}"

    return f"{title}\n\n{body}\n\n{footer}"


class TelegramService:
    def __init__(self, chat_id=None, token=None):
        self.chat_id = chat_id
        self.token = token

        self.http_service = HttpService()

    async def send_note_notify(self, note=None, mr=None):
        url = f"https://api.telegram.org/{self.token}/sendMessage"
        json_payload = {
            "text": format_note_message(note=note, mr=mr),
            "chat_id": self.chat_id,
            "parse_mode": "MarkdownV2"
        }

        logger.debug(json.dumps(json_payload, indent=2))

        try:
            res = await self.http_service.post(url=url, json_body=json_payload)
            logger.debug(res)
        except Exception as e:
            logger.error(e)
