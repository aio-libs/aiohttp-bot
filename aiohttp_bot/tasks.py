import celery
import asyncio
import os
import subprocess
import aiohttp
from gidgethub import aiohttp as gh_aiohttp

import cachetools

from celery import bootsteps

from cherry_picker import cherry_picker

from . import util

app = celery.Celery("backport_aiohttp")

app.conf.update(
    BROKER_URL=os.environ["REDIS_URL"], CELERY_RESULT_BACKEND=os.environ["REDIS_URL"]
)

cache = cachetools.LRUCache(maxsize=500)


@app.task()
def setup_aiohttp_repo():
    print("Setting up aiohttp repository")
    if "aiohttp" not in os.listdir("."):
        subprocess.check_output(
            f"git clone https://{os.environ.get('GH_AUTH')}:x-oauth-basic@github.com/aiohttp-bot/aiohttp.git".split()
        )
        subprocess.check_output(
            "git config --global user.email 'mariatta.wijaya+aiohttp-bot@gmail.com'".split()
        )
        subprocess.check_output(
            ["git", "config", "--global", "user.name", "'aiohttp-bot'"]
        )
        os.chdir("./aiohttp")
        subprocess.check_output(
            f"git remote add upstream https://{os.environ.get('GH_AUTH')}:x-oauth-basic@github.com/aio-libs/aiohttp.git".split()
        )
        print("Finished setting up aiohttp Repo")
    else:
        print("aiohttp directory already exists")


@app.task()
def backport_task(commit_hash, branch, *, issue_number, created_by, merged_by):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        backport_task_asyncio(
            commit_hash,
            branch,
            issue_number=issue_number,
            created_by=created_by,
            merged_by=merged_by,
        )
    )


async def backport_task_asyncio(
    commit_hash, branch, *, issue_number, created_by, merged_by
):
    """Backport a commit into a branch."""

    oauth_token = os.environ.get("GH_AUTH")
    async with aiohttp.ClientSession() as session:
        gh = gh_aiohttp.GitHubAPI(
            session, "aio-libs/aiohttp", oauth_token=oauth_token, cache=cache
        )

        if not util.is_aiohttp_repo():
            # cd to aiohttp if we're not already in it
            if "aiohttp" in os.listdir("."):
                os.chdir("./aiohttp")
            else:
                print(f"pwd: {os.getcwd()}, listdir: {os.listdir('.')}")

                await util.comment_on_pr(
                    gh,
                    issue_number,
                    f"""{util.get_participants(created_by, merged_by)}, Something is wrong... I can't backport for now.
                                   Please backport using [cherry_picker](https://pypi.org/project/cherry-picker/) on command line.
                                   ```
                                   cherry_picker {commit_hash} {branch}
                                   ```
                                   """,
                )
                await util.assign_pr_to_committer(gh, issue_number, merged_by)
        cp = cherry_picker.CherryPicker(
            "origin", commit_hash, [branch], prefix_commit=False
        )
        try:
            cp.backport()
        except cherry_picker.BranchCheckoutException:
            await util.comment_on_pr(
                gh,
                issue_number,
                f"""Sorry {util.get_participants(created_by, merged_by)}, I had trouble checking out the `{branch}` backport branch.
                                Please backport using [cherry_picker](https://pypi.org/project/cherry-picker/) on command line.
                                ```
                                cherry_picker {commit_hash} {branch}
                                ```
                                """,
            )
            await util.assign_pr_to_committer(gh, issue_number, merged_by)
            cp.abort_cherry_pick()
        except cherry_picker.CherryPickException:
            await util.comment_on_pr(
                gh,
                issue_number,
                f"""Sorry, {util.get_participants(created_by, merged_by)}, I could not cleanly backport this to `{branch}` due to a conflict. 
                                Please backport using [cherry_picker](https://pypi.org/project/cherry-picker/) on command line.
                                ```
                                cherry_picker {commit_hash} {branch}
                                ```
                                """,
            )
            await util.assign_pr_to_committer(gh, issue_number, merged_by)
            cp.abort_cherry_pick()


class InitRepoStep(bootsteps.StartStopStep):
    def start(self, c):
        print("Initialize the repository.")
        setup_aiohttp_repo()


app.steps["worker"].add(InitRepoStep)
