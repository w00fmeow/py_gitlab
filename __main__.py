import asyncio
import logging
import aiohttp
from argparse import ArgumentParser
from requests.structures import CaseInsensitiveDict
from typing import List
from src.py_gitlab import log_merge_requests_without_comments, ensure_default_labels_loop, wait_for_comments


logging.basicConfig(level=logging.DEBUG,
                    format='[ %(name)s ] - %(levelname)s : %(message)s')

logger = logging.getLogger("Gitlab")

file_handler = logging.FileHandler("/tmp/py_gitlab.log")
logger.addHandler(file_handler)


def list_of_integers(input: str) -> List[int]:
    try:
        return [int(x) for x in input.split(',')]
    except Exception as e:
        logger.error(e)


parser = ArgumentParser(description='Gitlab cli')

parser.add_argument("-t", '--token', type=str,
                    help='private token for auth', required=True)

parser.add_argument("-m", '--merge_requests', type=bool, default=False,
                    help='Check merge requests that are opened by current user', required=False)

parser.add_argument("-l", '--merge_requests_labels', type=bool, default=False,
                    help='Ensure default labels are applied to all mrs', required=False)

parser.add_argument("-w", '--watch_comments', type=bool, default=False,
                    help='Wait for new comments on any merge request user is associated with', required=False)

parser.add_argument('--project_ids', type=list_of_integers, default=[],
                    help='Project IDs to look at when fetching comments', required=False)

parser.add_argument("-d", '--debug', type=bool, default=False,
                    help='Enable debuging', required=False)

parser.add_argument('--telegram_token', type=str,
                    help='telegram api token', required=True)

parser.add_argument('--chat_id', type=str,
                    help='telegram chat id', required=True)

args = parser.parse_args()


headers = CaseInsensitiveDict()
headers["User-Agent"] = "Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10.5; en-US; rv:1.9.0.5) Gecko/2008120121 Firefox/3.0.54"


async def main():
    headers["Private-Token"] = args.token
    session = aiohttp.ClientSession(headers=headers)
    tasks = []

    try:
        if args.merge_requests:
            logger.info("Getting merge requests")
            tasks.append(log_merge_requests_without_comments(session=session))

        if args.merge_requests_labels:
            logger.info("Applying default labels to mrs")
            tasks.append(ensure_default_labels_loop(session=session))

        if args.watch_comments and args.project_ids:
            logger.info("Waiting for merge requests comments")
            tasks.append(wait_for_comments(
                session=session, project_ids=args.project_ids))

        await asyncio.gather(*tasks)

    except Exception as e:
        logger.error(e)

    finally:
        await session.close()


asyncio.run(main())
