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

### Merge request labels

In our company we work in squads, so on our project work multiple teams. On each daily we wanted to go over all opened merge requests by only our team members. In UI there is no option to filter merge requests by multiple users.

Cheap solution for this is to apply label to each merge request that was opened by our team and then filter by this label.

`--merge_requests_labels` argument will launch loop to apply labels on all merge request opened by current user if some are missing.

When I open merge requests labels are applied as script runs in background and constantly checks the mrs.
