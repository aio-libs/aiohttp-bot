import enum
import sys

import gidgethub
import subprocess

LABEL_PREFIX = "awaiting"


@enum.unique
class Blocker(enum.Enum):
    """What is blocking a pull request from being committed."""

    review = f"{LABEL_PREFIX} review"
    core_review = f"{LABEL_PREFIX} comitter review"
    changes = f"{LABEL_PREFIX} changes"
    change_review = f"{LABEL_PREFIX} change review"
    merge = f"{LABEL_PREFIX} merge"


async def comment_on_pr(gh, issue_number, message):
    """
    Leave a comment on a PR/Issue
    """
    issue_comment_url = f"/repos/aio-libs/aiohttp/issues/{issue_number}/comments"
    data = {"body": message}
    response = await gh.post(issue_comment_url, data=data)
    print(f"Commented at {response['html_url']}, message: {message}")
    return response


async def assign_pr_to_committer(gh, issue_number, committer_login):
    """
    Assign the PR to a committer.  Should be done when bot failed
    to backport.
    """

    edit_issue_url = f"/repos/aio-libs/aiohttp/issues/{issue_number}"
    data = {"assignees": [committer_login]}
    await gh.patch(edit_issue_url, data=data)


def is_aiohttp_repo():
    cmd = "git log -r f382b5ffc445e45a110734f5396728da7914aeb6"
    try:
        subprocess.check_output(cmd.split(), stderr=subprocess.STDOUT)
    except subprocess.SubprocessError:
        return False
    return True


async def get_gh_participants(gh, pr_number):
    pr_url = f"/repos/aio-libs/aiohttp/pulls/{pr_number}"
    pr_result = await gh.getitem(pr_url)
    created_by = pr_result["user"]["login"]

    merged_by = None
    if pr_result["merged_by"] and pr_result["merged_by"]["login"] != "aiohttp-bot":
        merged_by = pr_result["merged_by"]["login"]

    participants = ""
    if created_by == merged_by or merged_by is None:
        participants = f"@{created_by}"
    else:
        participants = f"@{created_by} and @{merged_by}"

    return participants


def get_participants(created_by, merged_by):
    participants = ""
    if created_by == merged_by or merged_by == "aiohttp-bot":
        participants = f"@{created_by}"
    else:
        participants = f"@{created_by} and @{merged_by}"
    return participants


def normalize_title(title, body):
    """Normalize the title if it spills over into the PR's body."""
    if not (title.endswith("…") and body.startswith("…")):
        return title
    else:
        # Being paranoid in case \r\n is used.
        return title[:-1] + body[1:].partition("\r\n")[0]


def normalize_message(body):
    """Normalize the message body to make it commit-worthy.

    Mostly this just means removing HTML comments, but also removes unwanted
    leading or trailing whitespace.

    Returns the normalized body.
    """
    while "<!--" in body:
        body = body[: body.index("<!--")] + body[body.index("-->") + 3 :]
    return "\n\n" + body.strip()


# Copied over from https://github.com/python/bedevere
async def is_committer(gh, username):
    """Check if the user is an aiohttp committer."""
    org_teams = "/orgs/aio-libs/teams"
    team_name = "aiohttp-committers"
    async for team in gh.getiter(org_teams):
        if team["name"].lower() == team_name:
            break
    else:
        raise ValueError(f"{team_name!r} not found at {org_teams!r}")
    # The 'teams' object only provides a URL to a deprecated endpoint,
    # so manually construct the URL to the non-deprecated team membership
    # endpoint.
    membership_url = f"/teams/{team['id']}/memberships/{username}"
    try:
        await gh.getitem(membership_url)
    except gidgethub.BadRequest as exc:
        if exc.status_code == 404:
            return False
        raise
    else:
        return True


def user_login(item):
    return item["user"]["login"]


def pr_is_awaiting_merge(pr_labels):
    label_names = [label["name"] for label in pr_labels]
    if "DO-NOT-MERGE" not in label_names and "awaiting merge" in label_names:
        return True
    return False


async def get_pr_for_commit(gh, sha):
    prs_for_commit = await gh.getitem(
        f"/search/issues?q=type:pr+repo:aio-libs/aiohttp+sha:{sha}"
    )
    if prs_for_commit["total_count"] > 0:  # there should only be one
        pr_for_commit = prs_for_commit["items"][0]
        return pr_for_commit
    return None


async def committer_reviewers(gh, pull_request_url):
    """Find the reviewers who are committer developers."""
    # Unfortunately the reviews URL is not contained in a pull request's data.
    async for review in gh.getiter(pull_request_url + "/reviews"):
        reviewer = user_login(review)
        # Ignoring "comment" reviews.
        actual_review = review["state"].lower() in {"approved", "changes_requested"}
        if actual_review and await is_committer(gh, reviewer):
            yield reviewer


async def stage(gh, issue, blocked_on):
    """Remove any "awaiting" labels and apply the specified one."""
    label_name = blocked_on.value
    if any(label_name == label["name"] for label in issue["labels"]):
        return
    await remove_stage_labels(gh, issue)
    await gh.post(issue["labels_url"], data=[label_name])


async def remove_stage_labels(gh, issue):
    """Remove all "awaiting" labels."""
    # There's no reason to expect there to be multiple "awaiting" labels on a
    # single pull request, but just in case there are we might as well clean
    # up the situation when we come across it.
    for label in issue["labels"]:
        stale_name = label["name"]
        if stale_name.startswith(LABEL_PREFIX + " "):
            await gh.delete(issue["labels_url"], {"name": stale_name})


async def issue_for_PR(gh, pull_request):
    """Get the issue data for a pull request."""
    return await gh.getitem(pull_request["issue_url"])
