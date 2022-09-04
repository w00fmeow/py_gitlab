#!/usr/bin/env python3
import asyncio
import json
from datetime import datetime
from random import randint
from src.logger import logger
from src.utils import retry_on_fail, get_notes_hash
from src.gitlab_api import GitlabApi
from src.telegram_service import TelegramService
from src.config import PROJECT_DIR


class Orchestrator:
    MRS_DB_PATH = f'{PROJECT_DIR}/db'

    def __init__(self,
                 gitlab_token=None,
                 telegram_chat_id=None,
                 telegram_token=None,
                 merge_requests_labels=[],
                 gitlab_domain=None):
        self.gitlab_api = GitlabApi(token=gitlab_token, domain=gitlab_domain)

        self.telegram_service = TelegramService(
            chat_id=telegram_chat_id, token=telegram_token)

        self.merge_requests_labels = merge_requests_labels

    def get_changed_notes(self, new_mr={}, old_mr={"notes_map": {}}):
        diffs = []
        logger.debug("get_changed_notes")

        for note_id in new_mr["notes_map"].keys():
            if note_id not in old_mr["notes_map"]:
                diffs.append(new_mr["notes_map"][note_id])
            else:
                for note in new_mr["notes_map"][note_id]:
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

    @retry_on_fail
    async def log_merge_requests_without_comments(self):
        all_merge_requests = await self.gitlab_api.get_merge_requests()
        merge_requests_without_comments = [
            mr for mr in all_merge_requests if mr["user_notes_count"] == 0]

        for mr in merge_requests_without_comments:
            logger.debug(f"{mr['title']} - {mr['web_url']}")

    def build_notes_lookup(self, merge_requests=[]):
        mr_lookup = {}

        logger.debug("build_notes_lookup")
        for mr in merge_requests:
            if mr["user_notes_count"]:
                mr_id = mr["iid"]

                if mr_id not in mr_lookup:
                    mr_lookup[mr_id] = {
                        "original_data": mr,
                        "notes_map": {},
                        "ids_set": set(),
                        "hash": None
                    }
                non_system_notes = [note for note in mr['notes']
                                    if not note["system"]]
                for note in non_system_notes:

                    # note_position = note["position"]["base_sha"] if note["type"] == 'DiffNote' else note["noteable_id"]

                    # if note_position not in mr_lookup[mr_id]["note_groups"]:
                    #     mr_lookup[mr_id]["note_groups"][note_position] = []

                    mr_lookup[mr_id]["notes_map"][note['id']] = note
                    mr_lookup[mr_id]["ids_set"].add(note["id"])

                group_hash = get_notes_hash(notes=non_system_notes)

                mr_lookup[mr_id]["hash"] = group_hash

        return mr_lookup

    async def telegram_notify_notes(self, diffs=None):
        for diff in diffs:
            mr = diff["mr"]
            notes = diff["notes"]

            for note in notes:
                await self.telegram_service.send_note_notify(note=note, mr=mr)

    async def fetch_and_save_relevant_merge_requests(self, project_ids=None):
        merge_requests = await self.gitlab_api.get_merge_requests_relevant_to_user(project_ids=project_ids)

        db_object = {
            "project_ids": project_ids,
            "merge_requests": merge_requests,
            "date": str(datetime.now())
        }

        with open(self.MRS_DB_PATH, '+w', encoding="utf-8") as f:
            f.write(json.dumps(db_object))
            logger.info(f"Saved mrs to {self.MRS_DB_PATH} file")

        return merge_requests

    async def load_relevant_merge_requests_with_fallback(self, project_ids=None):
        merge_requests = None
        try:
            last_loaded_merge_requests_dump = json.loads(
                open(self.MRS_DB_PATH, 'r', encoding="utf-8").read())

            if all([project_id in set(last_loaded_merge_requests_dump["project_ids"]) for project_id in project_ids]):
                logger.info(
                    f"Using merge requests loaded from {last_loaded_merge_requests_dump['date']}")

                merge_requests = last_loaded_merge_requests_dump["merge_requests"]
        except Exception as e:
            logger.error(e)

        if not merge_requests:
            logger.debug(
                "Failed to load previously loaded merge requests. Fetching from API again")

            return await self.gitlab_api.get_merge_requests_relevant_to_user(project_ids=project_ids)

        return merge_requests

    @retry_on_fail
    async def wait_for_comments(self, project_ids=[]):
        await self.gitlab_api.get_current_user()

        all_merge_requests = await self.load_relevant_merge_requests_with_fallback(
            project_ids=project_ids)

        prev_mrs_lookup = self.build_notes_lookup(
            merge_requests=all_merge_requests)

        should_stop = False

        while not should_stop:
            try:
                new_merge_requests = await self.fetch_and_save_relevant_merge_requests(project_ids=project_ids)

                fresh_mr_lookup = self.build_notes_lookup(
                    merge_requests=new_merge_requests)

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

    async def ensure_default_labels_exist_on_mrs(self):
        logger.debug("Checking if all mrs have default labels")
        mrs = await self.gitlab_api.get_merge_requests()
        for mr in mrs:
            missing_labels = []

            if "labels" not in mr:
                missing_labels = self.merge_requests_labels
            else:
                missing_labels = [
                    default_label for default_label in self.merge_requests_labels if default_label not in mr["labels"]]

            if missing_labels:
                logger.info(
                    f"Merge request {mr['title']} is missing labels: {missing_labels}. Updating")
                labels_for_update = list(set(mr['labels'] + missing_labels))
                await self.gitlab_api.update_mr_labels(labels=labels_for_update, iid=mr["iid"], project_id=mr["project_id"])

    @retry_on_fail
    async def ensure_default_labels_loop(self):
        while True:
            await self.ensure_default_labels_exist_on_mrs()
            sleep_in_sec = randint(50, 120)

            logger.debug(
                f"Sleeping in ensure_default_labels_loop for : {sleep_in_sec} sec")

            await asyncio.sleep(sleep_in_sec)

    async def unassign_from_mrs(self, project_ids=[], current_user=None):
        logger.debug(
            "Checking if user is assigned to not relevant merge requests")

        mrs = await self.gitlab_api.get_merge_requests_relevant_to_user(project_ids=project_ids)

        for mr in mrs:
            if len(mr["assignees"]) > 1:
                assignees_ids_set = set([assignee['id']
                                        for assignee in mr["assignees"]])
                if current_user['id'] in assignees_ids_set and not self.gitlab_api.user_has_notes_in_mr(mr=mr, user=current_user):
                    logger.debug(
                        f"Removing current user from mr assignees: {mr['title']}")

                    assignees_ids_set.remove(current_user['id'])

                    updated_assignees_ids = list(assignees_ids_set)

                    await self.gitlab_api.update_mr_assignee_ids(iid=mr["iid"], project_id=mr["project_id"], assignee_ids=updated_assignees_ids)
                    await self.gitlab_api.unsubscribe_from_mr(iid=mr["iid"], project_id=mr["project_id"])

    @retry_on_fail
    async def unassign_from_mrs_loop(self, project_ids=[]):
        current_user = await self.gitlab_api.get_current_user()

        while True:
            await self.unassign_from_mrs(project_ids=project_ids, current_user=current_user)
            sleep_in_sec = randint(50, 120)

            logger.debug(
                f"Sleeping in unassign_from_mrs_loop for : {sleep_in_sec} sec")

            await asyncio.sleep(sleep_in_sec)
