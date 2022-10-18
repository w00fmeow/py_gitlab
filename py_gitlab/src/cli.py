#!/usr/bin/env python3
import asyncio
import logging
from argparse import ArgumentParser
from src.orchestrator import Orchestrator
from src.utils import parse_string_of_integers_to_list, parse_string_of_strings_to_list, parse_string_to_domain


logging.basicConfig(level=logging.DEBUG,
                    format='[ %(name)s ] - %(levelname)s : %(message)s')

logger = logging.getLogger("Gitlab")

file_handler = logging.FileHandler("/tmp/py_gitlab.log")
logger.addHandler(file_handler)


parser = ArgumentParser(description='Gitlab cli')

parser.add_argument("-t", '--token', type=str,
                    help='Gitlab private token for auth', required=True)

parser.add_argument('--gitlab_domain', type=parse_string_to_domain, default="gitlab.com",
                    help='Custom gitlab domain', required=False)

parser.add_argument("-m", '--merge_requests', type=bool, default=False,
                    help='Check merge requests that are opened by current user', required=False)

parser.add_argument("-l", '--merge_requests_labels', type=parse_string_of_strings_to_list, default=False,
                    help='Ensure labels are applied to all user merge requests', required=False)

parser.add_argument("-w", '--watch_comments', type=bool, default=False,
                    help='Wait for new comments on any merge request user is associated with', required=False)

parser.add_argument('--project_ids', type=parse_string_of_integers_to_list, default=[],
                    help='Project IDs to look at when fetching comments', required=False)

parser.add_argument("-d", '--debug', type=bool, default=False,
                    help='Enable debuging', required=False)

parser.add_argument('--telegram_token', type=str,
                    help='telegram api token', required=True)

parser.add_argument('--chat_id', type=str,
                    help='telegram chat id', required=True)

parser.add_argument("-u", '--unassign', type=bool, default=False,
                    help='Unassign current user from merge requests with multiple assignees', required=False)


args = parser.parse_args()


async def run():
    tasks = []

    orchestrator = Orchestrator(
        gitlab_token=args.token,
        telegram_chat_id=args.chat_id,
        telegram_token=args.telegram_token,
        merge_requests_labels=args.merge_requests_labels,
        gitlab_domain=args.gitlab_domain)

    try:
        if args.merge_requests:
            logger.info("Getting merge requests")
            tasks.append(
                orchestrator.log_merge_requests_without_comments())

        if args.merge_requests_labels:
            logger.info("Applying default labels to mrs")
            tasks.append(
                orchestrator.ensure_default_labels_loop())

        if args.watch_comments and args.project_ids:
            logger.info("Waiting for merge requests comments")
            tasks.append(orchestrator.wait_for_comments(
                project_ids=args.project_ids))

        if args.unassign and args.project_ids:
            logger.info("Unassigning user from not relevant merge requests")

            tasks.append(orchestrator.unassign_from_mrs_loop(
                project_ids=args.project_ids))

        await asyncio.gather(*tasks)

    except Exception as e:
        logger.error(e)


def main():
    asyncio.run(run())
