#!/usr/bin/env python3
import json
import asyncio
from src.http_service import HttpService
from src.logger import logger
from src.utils import escape_chars_in_str

CHARS_TO_ESCAPE = ["(", '-', '+', "_", "*", "[", "]", "`", ".", ')', "{", "}"]

SERVICE_PREFIX = f"""```
{escape_chars_in_str(input_str='[ gitlab ]',chars_to_escape=CHARS_TO_ESCAPE)}```"""


def format_user_note_message(mr=None, note=None):
    title_escaped = escape_chars_in_str(
        input_str=mr['title'], chars_to_escape=CHARS_TO_ESCAPE)

    body_escaped = escape_chars_in_str(
        input_str=note['body'], chars_to_escape=CHARS_TO_ESCAPE)

    note_url = f"{mr['web_url']}#note_{note['id']}"
    url_formatted = f"[{title_escaped}]({note_url})"

    title = f"{SERVICE_PREFIX}new comment on MR:\n{url_formatted}"
    body = f"_{body_escaped}_"
    footer = f"🗒 by {note['author']['name']}"

    return f"{title}\n\n{body}\n\n{footer}"


def format_approved_mr_note_message(mr=None, note=None):
    title_escaped = escape_chars_in_str(
        input_str=mr['title'], chars_to_escape=CHARS_TO_ESCAPE)

    url_formatted = f"[{title_escaped}]({mr['web_url']})"

    title = f"{SERVICE_PREFIX}MR was approved:\n{url_formatted}"
    footer = f"🗒 by {note['author']['name']}"

    return f"{title}\n\n{footer}"


def format_ask_to_unassign_from_mr_message(mr=None):
    title_escaped = escape_chars_in_str(
        input_str=mr['title'], chars_to_escape=CHARS_TO_ESCAPE)

    url_formatted = f"[{title_escaped}]({mr['web_url']})"

    title = f"{SERVICE_PREFIX}Unassign user from MR?\n{url_formatted}"
    footer = f"Created by {mr['author']['name']}"

    return f"{title}\n\n{footer}"


def format_unassigned_success():
    return f"{SERVICE_PREFIX}Unassigned ✅"


def format_system_note_message(mr=None, note=None):
    title_escaped = escape_chars_in_str(
        input_str=mr['title'], chars_to_escape=CHARS_TO_ESCAPE)

    body_escaped = escape_chars_in_str(
        input_str=note['body'], chars_to_escape=CHARS_TO_ESCAPE)

    url_formatted = f"[{title_escaped}]({mr['web_url']})"

    title = f"{SERVICE_PREFIX}🤖 event: \n{url_formatted}"
    body = f"_{body_escaped}_"
    footer = f"🗒 by {note['author']['name']}"

    return f"{title}\n\n{body}\n\n{footer}"


class TelegramService:
    def __init__(self, chat_id=None, token=None, unassign_from_mr_callback=None):
        self.chat_id = chat_id
        self.token = token

        self.http_service = HttpService()

        self.unassign_from_mr_callback = unassign_from_mr_callback

        asyncio.ensure_future(self._run_updates_loop())

    async def send_user_note(self, note=None, mr=None):
        note_body = format_user_note_message(note=note, mr=mr)
        await self._send_message(body=note_body)

    async def send_system_note_message(self, note=None, mr=None):
        note_body = format_system_note_message(note=note, mr=mr)

        await self._send_message(body=note_body)

    async def send_mr_approved_note_message(self, note=None, mr=None):
        note_body = format_approved_mr_note_message(note=note, mr=mr)

        await self._send_message(body=note_body)

    async def _send_message(self, body=None, **kwargs):
        url = f"https://api.telegram.org/{self.token}/sendMessage"
        json_payload = {
            "text": body,
            "chat_id": self.chat_id,
            "parse_mode": "MarkdownV2",
            **kwargs
        }

        logger.debug(json.dumps(json_payload, indent=2))

        try:
            res = await self.http_service.post(url=url, json_body=json_payload)
            logger.debug(res)
        except Exception as e:
            logger.error(e)

    async def remove_reply_markup_from_message(self, message_id=None):
        url = f"https://api.telegram.org/{self.token}/editMessageReplyMarkup"
        json_payload = {
            "chat_id": self.chat_id,
            "message_id": message_id,
            "reply_markup": {
                "inline_keyboard": []}
        }

        logger.debug(json.dumps(json_payload, indent=2))

        try:
            res = await self.http_service.post(url=url, json_body=json_payload)
            logger.debug(res)
        except Exception as e:
            logger.error(e)

    async def ask_to_unassign_from_mr(self, mr=None):
        body = format_ask_to_unassign_from_mr_message(mr=mr)

        markup = {"inline_keyboard": [
            [{
                "text": 'Yes',
                "callback_data": json.dumps({"mr_id": mr["iid"], "project_id":mr["project_id"], "decision":True})
            }],
            [{
                "text": 'No',
                "callback_data": json.dumps({"mr_id": mr["iid"], "project_id":mr["project_id"], "decision":False})
            }],
        ]}
        return await self._send_message(body=body, reply_markup=markup)

    async def _get_updates(self, time_out=0, offset=0):
        url = f"https://api.telegram.org/{self.token}/getUpdates"
        query_params = {"timeout": time_out, "offset": offset}

        try:
            res = await self.http_service.get(url=url, query_params=query_params)
            logger.debug(res)
            return res
        except Exception as e:
            logger.error(e)

    async def unassign_from_mr_success(self, message_id=None):
        await self._send_message(body=format_unassigned_success(), reply_to_message_id=message_id)

    async def _run_updates_loop(self):
        poll_timeout = 20
        logger.info(
            f"Polling getUpdates for updates with timeout: {poll_timeout}")

        offset = 0
        while True:
            new_updates = await self._get_updates(time_out=poll_timeout, offset=offset)

            if new_updates:
                for update in new_updates["result"]:
                    offset = max(offset, update["update_id"]+1)

                await self._process_updates(new_updates["result"])

    async def _process_updates(self, updates=[]):
        for update in updates:
            logger.info(f"Received new update: {update['update_id']}")

            try:
                data = json.loads(update["callback_query"]["data"])

                if "mr_id" in data and "project_id" in data and "decision" in data:
                    await self.unassign_from_mr_callback(
                        mr_id=data["mr_id"], project_id=data["project_id"], decision=data['decision'], message=update["callback_query"]["message"])

            except Exception as e:
                logger.error(e)
