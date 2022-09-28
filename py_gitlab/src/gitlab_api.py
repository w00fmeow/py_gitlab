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

    async def get_merge_requests(self, scope="created_by_me", project_id=None, with_merge_status_recheck='true'):
        url = f"{self.base_url}/merge_requests" if not project_id else f"{self.base_url}/projects/{project_id}/merge_requests"

        query_params = {"scope": scope, "state": "opened", "wip": "no",
                        "with_merge_status_recheck": with_merge_status_recheck}
        all_merge_requests = await self.http_service.get(url=url, query_params=query_params)
        return all_merge_requests

    async def get_merge_request_notes(self, id=None, project_id=None):
        url = f"{self.base_url}/projects/{project_id}/merge_requests/{id}/notes"

        merge_requests = await self.http_service.get(url=url)
        return merge_requests

    async def get_current_user(self):
        if not self.current_user:
            url = f"{self.base_url}/user"

            user = await self.http_service.get(url=url)
            self.current_user = user
        return self.current_user

    async def get_merge_requests_by_project_ids(self, project_ids=[]):
        all_mrs = []

        for project_id in project_ids:
            project_merge_requests = await self.get_merge_requests(project_id=project_id, scope="all")

            for mr in project_merge_requests:
                all_mrs.append(mr)

        return all_mrs

    def user_has_notes_in_mr(self, mr=None, user=None):
        for note in mr["notes"]:
            if not note["system"] and note["author"]["id"] == user["id"] or string_contains_user_mention(note['body'], user["username"]):
                return True

        return False

    async def get_merge_requests_relevant_to_user(self, project_ids=[]):
        relevant_mrs = []
        # TODO: /merge_requests&scope=all returns 500.
        # https://gitlab.com/gitlab-org/gitlab/-/issues/342405
        mrs = await self.get_merge_requests_by_project_ids(project_ids=project_ids)

        for mr in mrs:
            is_relevant = False

            mr_assignee_ids_set = set([assignee["id"]
                                      for assignee in mr["assignees"]])

            mr_reviewer_ids_set = set([reviewer["id"]
                                      for reviewer in mr["reviewers"]])
            mr["notes"] = []

            if mr["user_notes_count"]:
                if mr["author"]["id"] == self.current_user["id"]:
                    is_relevant = True

                notes = await self.get_merge_request_notes(id=mr['iid'], project_id=mr["source_project_id"])
                if notes:
                    mr["notes"] = notes

                if self.user_has_notes_in_mr(mr=mr, user=self.current_user):
                    is_relevant = True

            if self.current_user["id"] in mr_assignee_ids_set:
                logger.debug(
                    f"MR is relevant for user as he is in assignees array: {mr['title']}")
                is_relevant = True

            if self.current_user["id"] in mr_reviewer_ids_set:
                logger.debug(
                    f"MR is relevant for user as he is in reviewers array: {mr['title']}")
                is_relevant = True

            if is_relevant:
                relevant_mrs.append(mr)

        return relevant_mrs

    async def update_mr_labels(self,  iid=None, project_id=None, labels=[]):

        url = f"{self.base_url}/projects/{project_id}/merge_requests/{iid}"

        json_body = {"labels": labels}

        result = await self.http_service.put(url=url, json_body=json_body)

        logger.info(f"Updated labels for mr: {iid}. updated labels: {labels}")
        return result

    async def update_mr_assignee_ids(self,  iid=None, project_id=None, assignee_ids=[]):

        url = f"{self.base_url}/projects/{project_id}/merge_requests/{iid}"

        json_body = {"assignee_ids": assignee_ids}

        result = await self.http_service.put(url=url, json_body=json_body)

        logger.info(
            f"Updated assignees for mr: {iid}. updated assignee_ids: {assignee_ids}")
        return result

    async def update_mr_reviewer_ids(self,  iid=None, project_id=None, reviewer_ids=[]):

        url = f"{self.base_url}/projects/{project_id}/merge_requests/{iid}"

        json_body = {"reviewer_ids": reviewer_ids}

        result = await self.http_service.put(url=url, json_body=json_body)

        logger.info(
            f"Updated reviewers for mr: {iid}. updated reviewer_ids: {reviewer_ids}")
        return result

    async def unsubscribe_from_mr(self, iid=None, project_id=None):

        url = f"{self.base_url}/projects/{project_id}/merge_requests/{iid}/unsubscribe"

        result = await self.http_service.post(url=url)

        logger.info(
            f"Unsubscribed from mr : {iid}.")
        return result
