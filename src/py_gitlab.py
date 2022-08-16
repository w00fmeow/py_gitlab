import json
import re
import asyncio
import hashlib
from functools import wraps
from random import randint

import logging

logging.basicConfig(level=logging.DEBUG,
                    format='[ %(name)s ] - %(levelname)s : %(message)s')

logger = logging.getLogger("Gitlab")

file_handler = logging.FileHandler("/tmp/py_gitlab.log")
logger.addHandler(file_handler)


GITLAB_HOST = "https://gitlab.com"
GITLAB_BASE_URL = f"{GITLAB_HOST}/api/v4"

DEFAULT_LABELS = [
    "Self Service Squad"
]


def escape_char_in_str(input_str=None, char_to_escape=None, escape_with="\\"):
    return re.sub(char_to_escape, f'{escape_with}{char_to_escape}', input_str)


semaphore = asyncio.Semaphore(value=10)


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


def get_changed_notes(new_mr={}, old_mr={"note_groups": {}}, user=None):
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
        note for note in diffs if note["author"]["id"] != user["id"]]

    return filtered_notes


def get_diff_notes(old_lookup_table={}, new_lookup_table={}, user=None):
    diffs = []

    for mr_key in new_lookup_table.keys():
        if mr_key in old_lookup_table:
            hash_changed = mr_key not in old_lookup_table or old_lookup_table[
                mr_key]["hash"] != new_lookup_table[mr_key]["hash"]

            if hash_changed:
                diff_notes = get_changed_notes(
                    new_mr=new_lookup_table[mr_key],
                    old_mr=old_lookup_table[mr_key],
                    user=user)

                if diff_notes:
                    logger.debug(
                        f"mr notes changed: {new_lookup_table[mr_key]}")

                    diffs.append(
                        {
                            "mr": new_lookup_table[mr_key]['original_data'],
                            "notes": diff_notes
                        })
        else:
            diff_notes = get_changed_notes(
                new_mr=new_lookup_table[mr_key],
                user=user)

            if diff_notes:
                logger.debug(
                    f"mr notes changed: {new_lookup_table[mr_key]}")
                diffs.append(
                    {
                        "mr": new_lookup_table[mr_key]['original_data'],
                        "notes": diff_notes
                    })

    return diffs


def format_note_message(mr=None, note=None):
    title_escaped = escape_char_in_str(
        input_str=mr['title'], char_to_escape='-')
    url_formatted = f"[{title_escaped}]({mr['web_url']})"
    title = f"[ gitlab ]: new comment on MR:\n{url_formatted}"
    body = f"_{note['body']}_"
    footer = f"🗒 by {note['author']['name']}"

    return f"{title}\n\n{body}\n\n{footer}"


def get_notes_hash(notes=[]):
    notes_hashes = []

    for note in notes:
        hash = str(note['id'])

        notes_hashes.append(hash)

    blueprint = "".join(notes_hashes)
    md5_hash = hashlib.md5(blueprint.encode()).hexdigest()

    return md5_hash


async def request(session=None, url=None, params={}, json_body=None, method="GET"):
    await semaphore.acquire()
    result = None
    try:
        params_array = [(k, params[k]) for k in params.keys()]

        request_kargs = {
            "url": url,
            "params": params_array,
            "json": json_body
        }

        response = None
        if method == "GET":
            response = await session.get(**request_kargs)
        elif method == 'POST':
            response = await session.post(**request_kargs)
        elif method == 'PUT':
            response = await session.put(**request_kargs)
        else:
            raise Exception(f"Unkown request method: {method}")

        logger.debug(response.url)
        if response:
            result = await response.json()
        else:
            raise Exception("Got empty response")

    except Exception as e:
        logger.error(e)

    semaphore.release()
    return result


async def telegram_notify_note(session=None, note=None, mr=None, chat_id=None):
    url = f"https://api.telegram.org/{args.telegram_token}/sendMessage"
    json_payload = {
        "text": format_note_message(note=note, mr=mr),
        "chat_id": chat_id,
        "parse_mode": "MarkdownV2"
    }

    logger.debug(json.dumps(json_payload, indent=2))

    try:
        res = await request(session=session, url=url, method="POST", json_body=json_payload)
        logger.debug(res)
    except Exception as e:
        logger.error(e)


async def get_merge_requests(session=None, scope="created_by_me", project_id=None):
    url = f"{GITLAB_BASE_URL}/merge_requests" if not project_id else f"{GITLAB_BASE_URL}/projects/{project_id}/merge_requests"
    logger.debug(url)

    params = {"scope": scope, "state": "opened", "wip": "no"}
    all_merge_requests = await request(url=url, session=session, params=params)
    return all_merge_requests


async def get_merge_request_notes(session=None, id=None, project_id=None):
    url = f"{GITLAB_BASE_URL}/projects/{project_id}/merge_requests/{id}/notes"

    logger.debug(url)

    merge_requests = await request(url=url, session=session)
    return merge_requests


async def get_current_user(session=None):
    url = f"{GITLAB_BASE_URL}/user"

    logger.debug(url)

    user = await request(url=url, session=session)
    return user


async def log_merge_requests_without_comments(session=None):
    all_merge_requests = await get_merge_requests(session=session)
    merge_requests_without_comments = [
        mr for mr in all_merge_requests if mr["user_notes_count"] == 0]

    for mr in merge_requests_without_comments:
        logger.debug(f"{mr['title']} - {mr['web_url']}")


async def get_merge_requests_relevant_to_user(session=None, project_ids=[], user=None):
    all_mrs = []
    for project_id in project_ids:
        project_merge_requests = await get_merge_requests(session=session, project_id=project_id, scope="all")

        for mr in project_merge_requests:
            if mr["user_notes_count"]:

                if mr["author"]["id"] == user["id"]:
                    logger.debug(
                        f"MR is relevant for user as he is the author: {mr['title']}")

                    all_mrs.append(mr)
                    break

                notes = await get_merge_request_notes(session=session, id=mr['iid'], project_id=mr["source_project_id"])

                for note in notes:
                    if note["author"]["id"] == user["id"] or string_contains_user_mention(note['body'], user["username"]):
                        all_mrs.append(mr)
                        break

    return all_mrs


async def build_notes_lookup(session=None, merge_requests=[]):
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
            notes = await get_merge_request_notes(session=session, id=mr_id, project_id=mr["source_project_id"])

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


async def telegram_notify_notes(session=None, diffs=None, chat_id=None):
    for diff in diffs:
        mr = diff["mr"]
        notes = diff["notes"]

        for note in notes:
            await telegram_notify_note(session=session, note=note, mr=mr, chat_id=chat_id)


@retry_on_fail
async def wait_for_comments(session=None, project_ids=[], chat_id=None):
    current_user = await get_current_user(session=session)

    all_merge_requests = await get_merge_requests_relevant_to_user(session=session, user=current_user, project_ids=project_ids)

    prev_mrs_lookup = await build_notes_lookup(session=session, merge_requests=all_merge_requests)

    should_stop = False

    while not should_stop:
        try:
            new_merge_requests = await get_merge_requests_relevant_to_user(session=session, user=current_user, project_ids=project_ids)

            fresh_mr_lookup = await build_notes_lookup(session=session, merge_requests=new_merge_requests)

            diff_notes = get_diff_notes(
                new_lookup_table=fresh_mr_lookup, old_lookup_table=prev_mrs_lookup, user=current_user)
            if diff_notes:
                logger.info(f"Got {len(diff_notes)} new comments")

                await telegram_notify_notes(session=session, diffs=diff_notes, chat_id=chat_id)

            prev_mrs_lookup = fresh_mr_lookup

            sleep_in_sec = randint(5, 15)

            logger.debug(
                f"Sleeping in wait_for_comments for : {sleep_in_sec} sec")

            await asyncio.sleep(sleep_in_sec)
        except Exception as e:
            logger.error(e)


async def update_mr_labels(session=None, iid=None, project_id=None, labels=[]):

    url = f"{GITLAB_BASE_URL}/projects/{project_id}/merge_requests/{iid}"

    json_body = {"labels": labels}

    result = await request(method="PUT", url=url, session=session, json_body=json_body)

    logger.info(f"Updated labels for mr: {iid}. updated labels: {labels}")
    return result


@retry_on_fail
async def ensure_default_labels_exist_on_mrs(session=None):
    logger.debug("Checking if all mrs have default labels")
    mrs = await get_merge_requests(session=session)
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
            await update_mr_labels(session=session, labels=labels_for_update, iid=mr["iid"], project_id=mr["project_id"])


async def ensure_default_labels_loop(session=None):
    while True:
        await ensure_default_labels_exist_on_mrs(session=session)
        sleep_in_sec = randint(50, 120)

        logger.debug(
            f"Sleeping in ensure_default_labels_loop for : {sleep_in_sec} sec")

        await asyncio.sleep(sleep_in_sec)
