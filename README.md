py_gitlab

---

This is the automation for tasks that I wasn't happy with when working daily with [Gitlab](https//:gitlab.com)

## Goals

- Merge request comments
- Merge request labels

### Comments

When working on the merge requests sometimes it can take up two couple of hours for email notification to arrive.
I wanted to get notifications right away to telegram.

when passing `--watch_comments` flag the script will poll all relevant to current user merge requests, when there is a new comment available there will be a telegram notification with details.

![Message demo](./assets/message-demo.png?raw=true "Message demo")

### Merge request labels

In our company we work in squads, so on our project work multiple teams. On each daily we wanted to go over all opened merge requests by only our team members. In UI there is no option to filter merge requests by multiple users.

Cheap solution for this is to apply label to each merge request that was opened by our team and then filter by this label.

`--merge_requests_labels` argument will launch loop to apply labels on all merge request opened by current user if some are missing.

When I open merge requests labels are applied as script runs in background and constantly checks the mrs.

## Installation

run from project dir:

```
$ python3 -m pip install -e ./
```

## Running

```
$ py_gitlab --help
usage: py_gitlab [-h] -t TOKEN [-m MERGE_REQUESTS] [-l MERGE_REQUESTS_LABELS] [-w WATCH_COMMENTS]
                 [--project_ids PROJECT_IDS] [-d DEBUG] --telegram_token TELEGRAM_TOKEN --chat_id CHAT_ID

Gitlab cli

options:
  -h, --help            show this help message and exit
  -t TOKEN, --token TOKEN
                        private token for auth
  -m MERGE_REQUESTS, --merge_requests MERGE_REQUESTS
                        Check merge requests that are opened by current user
  -l MERGE_REQUESTS_LABELS, --merge_requests_labels MERGE_REQUESTS_LABELS
                        Ensure labels are applied to all user merge requests
  -w WATCH_COMMENTS, --watch_comments WATCH_COMMENTS
                        Wait for new comments on any merge request user is associated with
  --project_ids PROJECT_IDS
                        Project IDs to look at when fetching comments
  -d DEBUG, --debug DEBUG
                        Enable debuging
  --telegram_token TELEGRAM_TOKEN
                        telegram api token
  --chat_id CHAT_ID     telegram chat id

```

Example with arguments:

```
$ py_gitlab --token KOEQhX1TKIqLErlqvpWL \
        --watch_comments=1 \
        --merge_requests_labels="Some label,Another One" \
        --telegram_token=bot123456789:rXrTYcXFbOqc21Pfl-nngNEcVkEQ5NJOOlg \
        --project_ids="123,654" \
        --chat_id=123456789
```
