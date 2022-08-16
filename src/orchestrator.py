import json
import re
import asyncio
import hashlib
from random import randint
from src.logger import logger
from src.utils import escape_char_in_str, retry_on_fail, string_contains_user_mention
from src.http_service import HttpService
from src.gitlab_api import GitlabApi


DEFAULT_LABELS = [
    "Self Service Squad"
]


def get_notes_hash(notes=[]):
    notes_hashes = []

    for note in notes:
        hash = str(note['id'])

        notes_hashes.append(hash)

    blueprint = "".join(notes_hashes)
    md5_hash = hashlib.md5(blueprint.encode()).hexdigest()

    return md5_hash


def format_note_message(mr=None, note=None):
    title_escaped = escape_char_in_str(
        input_str=mr['title'], char_to_escape='-')
    url_formatted = f"[{title_escaped}]({mr['web_url']})"
    title = f"[ gitlab ]: new comment on MR:\n{url_formatted}"
    body = f"_{note['body']}_"
    footer = f"🗒 by {note['author']['name']}"
    return f"{title}\n\n{body}\n\n{footer}"


class Orchestrator:
    def __init__(self, gitlab_token=None, telegram_chat_id=None, telegram_token=None):
        self.gitlab_api = GitlabApi(token=gitlab_token)
        # TODO refactor telegram calls
        self.telegram_chat_id = telegram_chat_id
        self.telegram_token = telegram_token
        self.http_service = HttpService()

    def get_changed_notes(self, new_mr={}, old_mr={"note_groups": {}}):
        diffs = []
        logger.debug("get_changed_notes")

        for group_key in new_mr["note_groups"].keys():
            if group_key not in old_mr["note_groups"]:
                diffs.extend(new_mr["note_groups"][group_key])
            else:
                for note in new_mr["note_groups"][group_key]:
                    logger.debug(note["body"])
                    if note["id"] not in old_mr["ids_set"]:
                        diffs.append(note)

        filtered_notes = [
            note for note in diffs if note["author"]["id"] != self.gitlab_api.current_user["id"]]

        return filtered_notes

    def get_diff_notes(self, old_lookup_table={}, new_lookup_table={}):
        diffs = []

        for mr_key in new_lookup_table.keys():
            if mr_key in old_lookup_table:
                hash_changed = mr_key not in old_lookup_table or old_lookup_table[
                    mr_key]["hash"] != new_lookup_table[mr_key]["hash"]

                if hash_changed:
                    diff_notes = self.get_changed_notes(
                        new_mr=new_lookup_table[mr_key],
                        old_mr=old_lookup_table[mr_key]
                    )

                    if diff_notes:
                        logger.debug(
                            f"mr notes changed: {new_lookup_table[mr_key]}")

                        diffs.append(
                            {
                                "mr": new_lookup_table[mr_key]['original_data'],
                                "notes": diff_notes
                            })
            else:
                diff_notes = self.get_changed_notes(
                    new_mr=new_lookup_table[mr_key],
                )

                if diff_notes:
                    logger.debug(
                        f"mr notes changed: {new_lookup_table[mr_key]}")
                    diffs.append(
                        {
                            "mr": new_lookup_table[mr_key]['original_data'],
                            "notes": diff_notes
                        })

        return diffs

    async def telegram_notify_note(self, note=None, mr=None):
        url = f"https://api.telegram.org/{self.telegram_token}/sendMessage"
        json_payload = {
            "text": format_note_message(note=note, mr=mr),
            "chat_id": self.telegram_chat_id,
            "parse_mode": "MarkdownV2"
        }

        logger.debug(json.dumps(json_payload, indent=2))

        try:
            res = await self.http_service.post(url=url, json_body=json_payload)
            logger.debug(res)
        except Exception as e:
            logger.error(e)

    async def log_merge_requests_without_comments(self):
        all_merge_requests = await self.gitlab_api.get_merge_requests()
        merge_requests_without_comments = [
            mr for mr in all_merge_requests if mr["user_notes_count"] == 0]

        for mr in merge_requests_without_comments:
            logger.debug(f"{mr['title']} - {mr['web_url']}")

    async def build_notes_lookup(self, merge_requests=[]):
        mr_lookup = {}

        logger.debug("build_notes_lookup")
        for mr in merge_requests:
            if mr["user_notes_count"]:
                mr_id = mr["iid"]

                if mr_id not in mr_lookup:
                    mr_lookup[mr_id] = {
                        "original_data": mr,
                        "note_groups": {},
                        "ids_set": set(),
                        "hash": None
                    }
                notes = await self.gitlab_api.get_merge_request_notes(id=mr_id, project_id=mr["source_project_id"])

                diff_notes = [note for note in notes if not note["system"]]
                for note in diff_notes:

                    note_position = note["position"]["base_sha"] if note["type"] == 'DiffNote' else note["noteable_id"]

                    if note_position not in mr_lookup[mr_id]["note_groups"]:
                        mr_lookup[mr_id]["note_groups"][note_position] = []

                    mr_lookup[mr_id]["note_groups"][note_position].append(note)
                    mr_lookup[mr_id]["ids_set"].add(note["id"])

                group_hash = get_notes_hash(notes=diff_notes)

                mr_lookup[mr_id]["hash"] = group_hash

        return mr_lookup

    async def telegram_notify_notes(self, diffs=None):
        for diff in diffs:
            mr = diff["mr"]
            notes = diff["notes"]

            for note in notes:
                await self.telegram_notify_note(note=note, mr=mr)

    @retry_on_fail
    async def wait_for_comments(self, project_ids=[], chat_id=None):
        current_user = await self.gitlab_api.get_current_user()

        all_merge_requests = await self.gitlab_api.get_merge_requests_relevant_to_user(project_ids=project_ids)

        prev_mrs_lookup = await self.build_notes_lookup(merge_requests=all_merge_requests)

        should_stop = False

        while not should_stop:
            try:
                new_merge_requests = await self.gitlab_api.get_merge_requests_relevant_to_user(project_ids=project_ids)

                fresh_mr_lookup = await self.build_notes_lookup(merge_requests=new_merge_requests)

                diff_notes = self.get_diff_notes(
                    new_lookup_table=fresh_mr_lookup, old_lookup_table=prev_mrs_lookup)
                if diff_notes:
                    logger.info(f"Got {len(diff_notes)} new comments")

                    await self.telegram_notify_notes(diffs=diff_notes)

                prev_mrs_lookup = fresh_mr_lookup

                sleep_in_sec = randint(5, 15)

                logger.debug(
                    f"Sleeping in wait_for_comments for : {sleep_in_sec} sec")

                await asyncio.sleep(sleep_in_sec)
            except Exception as e:
                logger.error(e)

    @retry_on_fail
    async def ensure_default_labels_exist_on_mrs(self):
        logger.debug("Checking if all mrs have default labels")
        mrs = await self.gitlab_api.get_merge_requests()
        for mr in mrs:
            missing_labels = []

            if "labels" not in mr:
                missing_labels = DEFAULT_LABELS
            else:
                missing_labels = [
                    default_label for default_label in DEFAULT_LABELS if default_label not in mr["labels"]]

            if missing_labels:
                logger.info(
                    f"Merge request {mr['title']} is missing labels: {missing_labels}. Updating")
                labels_for_update = list(set(mr['labels'] + missing_labels))
                await self.gitlab_api.update_mr_labels(labels=labels_for_update, iid=mr["iid"], project_id=mr["project_id"])

    async def ensure_default_labels_loop(self):
        while True:
            await self.ensure_default_labels_exist_on_mrs()
            sleep_in_sec = randint(50, 120)

            logger.debug(
                f"Sleeping in ensure_default_labels_loop for : {sleep_in_sec} sec")

            await asyncio.sleep(sleep_in_sec)
