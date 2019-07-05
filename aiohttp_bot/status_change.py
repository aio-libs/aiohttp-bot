import re

import gidgethub

from gidgethub import routing

from . import util

router = routing.Router()

TITLE_RE = re.compile(r"\[(?P<branch>\d+\.\d+)\].+?(?P<pr>\d+)\)")


@router.register("status")
async def check_status(event, gh, *args, **kwargs):
    """
    Check the state change
    """
    sha = event.data["sha"]

    if (
        event.data["commit"].get("committer")
        and event.data["commit"]["committer"]["login"] == "aiohttp-bot"
    ):
        await check_ci_status_and_approval(gh, sha, leave_comment=True)


async def check_ci_status_and_approval(
    gh, sha, pr_for_commit=None, leave_comment=False, is_automerge=False
):

    result = await gh.getitem(f"/repos/aio-libs/aiohttp/commits/{sha}/status")
    all_ci_status = [status["state"] for status in result["statuses"]]
    all_ci_context = [status["context"] for status in result["statuses"]]

    if (
        "pending" not in all_ci_status
        and "continuous-integration/travis-ci/pr" in all_ci_context
    ):
        if not pr_for_commit:
            pr_for_commit = await util.get_pr_for_commit(gh, sha)
        if pr_for_commit:
            pr_number = pr_for_commit["number"]
            normalized_pr_title = util.normalize_title(
                pr_for_commit["title"], pr_for_commit["body"]
            )

            title_match = TITLE_RE.match(normalized_pr_title)
            if title_match:
                if leave_comment:

                    original_pr_number = title_match.group("pr")
                    participants = await util.get_gh_participants(
                        gh, original_pr_number
                    )

                    emoji = "✅" if result["state"] == "success" else "❌"

                    await util.comment_on_pr(
                        gh,
                        issue_number=pr_number,
                        message=f"{participants}: Status check is done, and it's a {result['state']} {emoji} .",
                    )
                if result["state"] == "success":

                    if util.pr_is_awaiting_merge(pr_for_commit["labels"]):
                        await merge_pr(
                            gh, pr_for_commit, sha
                        )


async def merge_pr(gh, pr, sha):
    pr_number = pr["number"]
    async for commit in gh.getiter(f"/repos/aio-libs/aiohttp/pulls/{pr_number}/commits"):
        if commit["sha"] == sha:
            commit_msg = commit["commit"]["message"].split("\n")
            pr_commit_msg = "\n".join(commit_msg[1:])
            pr_title = f"{commit_msg[0]}"

            data = {
                "commit_title": pr_title,
                "commit_message": pr_commit_msg,
                "sha": sha,
                "merge_method": "squash",
            }
            try:
                await gh.put(
                    f"/repos/aio-libs/aiohttp/pulls/{pr_number}/merge", data=data
                )
            except gidgethub.BadRequest as err:
                await util.comment_on_pr(
                    gh, pr_number, f"Sorry, I can't merge this PR. Reason: `{err}`."
                )
            break