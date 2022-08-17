#!/usr/bin/env python3
from src.http_service import HttpService
from src.logger import logger
from src.utils import string_contains_user_mention

GITLAB_API_PATH = "api/v4"


class GitlabApi:
    def __init__(self, token=None, domain="gitlab.com"):
        self.token = token

        self.http_service = HttpService(headers={
            "Private-Token": self.token
        })

        self.base_url = f"https://{domain}/{GITLAB_API_PATH}"

        self.current_user = None

    async def get_merge_requests(self, scope="created_by_me", project_id=None):
        url = f"{self.base_url}/merge_requests" if not project_id else f"{self.base_url}/projects/{project_id}/merge_requests"

        query_params = {"scope": scope, "state": "opened", "wip": "no"}
        all_merge_requests = await self.http_service.get(url=url, query_params=query_params)
        return all_merge_requests

    async def get_merge_request_notes(self, id=None, project_id=None):
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{id}/notes"

        merge_requests = await self.http_service.get(url=url)
        return merge_requests

    async def get_current_user(self):
        url = f"{self.base_url}/user"

        user = await self.http_service.get(url=url)
        self.current_user = user
        return user

    async def get_merge_requests_relevant_to_user(self, project_ids=[]):
        all_mrs = []
        # TODO: /merge_requests&scope=all returns 500.
        # https://gitlab.com/gitlab-org/gitlab/-/issues/342405
        for project_id in project_ids:
            project_merge_requests = await self.get_merge_requests(project_id=project_id, scope="all")

            for mr in project_merge_requests:
                if mr["user_notes_count"]:

                    if mr["author"]["id"] == self.current_user["id"]:
                        logger.debug(
                            f"MR is relevant for user as he is the author: {mr['title']}")

                        all_mrs.append(mr)
                        break

                    notes = await self.get_merge_request_notes(id=mr['iid'], project_id=mr["source_project_id"])

                    for note in notes:
                        if note["author"]["id"] == self.current_user["id"] or string_contains_user_mention(note['body'], self.current_user["username"]):
                            all_mrs.append(mr)
                            break

        return all_mrs

    async def update_mr_labels(self,  iid=None, project_id=None, labels=[]):

        url = f"{self.base_url}/projects/{project_id}/merge_requests/{iid}"

        json_body = {"labels": labels}

        result = await self.http_service.put(url=url, json_body=json_body)

        logger.info(f"Updated labels for mr: {iid}. updated labels: {labels}")
        return result
