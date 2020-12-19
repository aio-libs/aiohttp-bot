import http
import gidgethub

from gidgethub import sansio

from aiohttp_bot import status_change

# from aiohttp_bot.util import AUTOMERGE_LABEL


class FakeGH:
    def __init__(self, *, getitem=None, getiter=None, put=None, post=None):
        self._getitem_return = getitem
        self._getiter_return = getiter
        self.getitem_url = None
        self.getiter_url = None
        self._put_return = put
        self._post_return = post

    async def getitem(self, url):
        self.getitem_url = url
        to_return = self._getitem_return[self.getitem_url]
        return to_return

    async def getiter(self, url):
        self.getiter_url = url
        to_iterate = self._getiter_return[url]
        for item in to_iterate:
            yield item

    async def put(self, url, *, data):
        self.put_url = url
        self.put_data = data
        to_return = self._put_return
        if isinstance(to_return, Exception):
            raise to_return
        else:
            return to_return

    async def post(self, url, *, data):
        self.post_url = url
        self.post_data = data
        return self._post_return


async def test_awaiting_merge_webhook_ci_failure_pr_is_not_merged():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {
        "action": "labeled",
        "pull_request": {
            "user": {"login": "aiohttp-bot"},
            "labels": [{"name": "awaiting merge"}],
            "head": {"sha": sha},
        },
    }

    event = sansio.Event(data, event="pull_request", delivery_id="1")

    getitem = {
        f"/repos/aio-libs/aiohttp/commits/{sha}/status": {
            "state": "failure",
            "statuses": [
                {
                    "state": "success",
                    "description": "Issue report skipped",
                    "context": "bedevere/issue-number",
                },
                {
                    "state": "failure",
                    "description": "The Travis CI build failed",
                    "target_url": "https://travis-ci.org/aio-libs/aiohttp/builds/340259685?utm_source=github_status&utm_medium=notification",
                    "context": "continuous-integration/travis-ci/pr",
                },
            ],
        },
        "/repos/aio-libs/aiohttp/pulls/5547": {"labels": [{"name": "awaiting merge"}]},
        f"/search/issues?q=type:pr+repo:aio-libs/aiohttp+sha:{sha}": {
            "total_count": 1,
            "items": [
                {
                    "number": 5547,
                    "title": "[3.6] bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)",
                    "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
                    "labels": [{"name": "awaiting merge"}],
                }
            ],
        },
    }

    gh = FakeGH(getitem=getitem)
    await status_change.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")  # does not leave a comment
    assert not hasattr(gh, "put_data")  # is not merged


async def test_awaiting_core_review_label_added_is_not_merged():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {
        "action": "labeled",
        "pull_request": {
            "user": {"login": "aiohttp-bot"},
            "labels": [{"name": "awaiting merge"}],
            "head": {"sha": sha},
        },
    }

    event = sansio.Event(data, event="pull_request", delivery_id="1")

    getitem = {
        f"/repos/aio-libs/aiohttp/commits/{sha}/status": {
            "state": "failure",
            "statuses": [
                {
                    "state": "success",
                    "description": "Issue report skipped",
                    "context": "bedevere/issue-number",
                },
                {
                    "state": "failure",
                    "description": "The Travis CI build failed",
                    "target_url": "https://travis-ci.org/aio-libs/aiohttp/builds/340259685?utm_source=github_status&utm_medium=notification",
                    "context": "continuous-integration/travis-ci/pr",
                },
            ],
        },
        f"/search/issues?q=type:pr+repo:aio-libs/aiohttp+sha:{sha}": {
            "total_count": 1,
            "items": [
                {
                    "number": 5547,
                    "title": "[3.6] bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)",
                    "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
                    "labels": [{"name": "awaiting merge"}],
                }
            ],
        },
    }

    gh = FakeGH(getitem=getitem)
    await status_change.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")  # does not leave a comment
    assert not hasattr(gh, "put_data")  # is not merged


async def test_awaiting_merge_label_ignore_non_aiohttp_bot_pr():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {
        "action": "labeled",
        "pull_request": {
            "user": {"login": "Mariatta"},
            "labels": [{"name": "awaiting merge"}],
            "head": {"sha": sha},
        },
    }

    event = sansio.Event(data, event="pull_request", delivery_id="1")

    getitem = {
        f"/repos/aio-libs/aiohttp/commits/{sha}/status": {
            "state": "success",
            "statuses": [
                {
                    "state": "success",
                    "description": "Issue report skipped",
                    "context": "bedevere/issue-number",
                },
                {
                    "state": "success",
                    "description": "The Travis CI build failed",
                    "target_url": "https://travis-ci.org/aio-libs/aiohttp/builds/340259685?utm_source=github_status&utm_medium=notification",
                    "context": "continuous-integration/travis-ci/pr",
                },
            ],
        }
    }

    gh = FakeGH(getitem=getitem)  # , getiter=getiter)
    await status_change.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")  # does not leave a comment
    assert not hasattr(gh, "put_data")  # is not merged


async def test_ci_passed_with_awaiting_merge_label_not_aiohttp_bot_is_not_merged():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {"sha": sha, "commit": {"committer": {"login": "Mariatta"}}}
    event = sansio.Event(data, event="status", delivery_id="1")

    getitem = {
        f"/repos/aio-libs/aiohttp/commits/{sha}/status": {
            "state": "success",
            "statuses": [
                {
                    "state": "success",
                    "description": "Issue report skipped",
                    "context": "bedevere/issue-number",
                },
                {
                    "state": "success",
                    "description": "The Travis CI build passed",
                    "target_url": "https://travis-ci.org/aio-libs/aiohttp/builds/340259685?utm_source=github_status&utm_medium=notification",
                    "context": "continuous-integration/travis-ci/pr",
                },
            ],
        },
        "/repos/aio-libs/aiohttp/pulls/5544": {
            "user": {"login": "aiohttp-bot"},
            "merged_by": {"login": "Mariatta"},
        },
        "/repos/aio-libs/aiohttp/pulls/5547": {"labels": [{"name": "awaiting merge"}]},
        f"/search/issues?q=type:pr+repo:aio-libs/aiohttp+sha:{sha}": {
            "total_count": 1,
            "items": [
                {
                    "number": 5547,
                    "title": "bpo-32720: Fixed the replacement field grammar documentation.",
                    "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
                    "labels": [{"name": "awaiting merge"}],
                }
            ],
        },
    }

    gh = FakeGH(getitem=getitem)
    await status_change.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")  # does not leave a comment
    assert not hasattr(gh, "put_data")  # is not merged


async def test_ci_pending():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {"sha": sha, "commit": {"committer": {"login": "aiohttp-bot"}}}
    event = sansio.Event(data, event="status", delivery_id="1")

    getitem = {
        f"/repos/aio-libs/aiohttp/commits/{sha}/status": {
            "state": "pending",
            "statuses": [
                {
                    "state": "pending",
                    "description": "Issue report skipped",
                    "context": "bedevere/issue-number",
                },
                {
                    "state": "success",
                    "description": "The Travis CI build passed",
                    "target_url": "https://travis-ci.org/aio-libs/aiohttp/builds/340259685?utm_source=github_status&utm_medium=notification",
                    "context": "continuous-integration/travis-ci/pr",
                },
            ],
        },
        "/repos/aio-libs/aiohttp/pulls/5544": {
            "user": {"login": "aiohttp-bot"},
            "merged_by": {"login": "Mariatta"},
        },
    }

    getiter = {
        "/repos/aio-libs/aiohttp/pulls/5547/commits": [
            {
                "sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
                "commit": {
                    "message": "bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>"
                },
            }
        ]
    }

    gh = FakeGH(getitem=getitem, getiter=getiter)
    await status_change.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")  # does not leave a comment
    assert not hasattr(gh, "put_data")  # is not merged


async def test_travis_not_done():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {"sha": sha, "commit": {"committer": {"login": "aiohttp-bot"}}}
    event = sansio.Event(data, event="status", delivery_id="1")

    getitem = {
        f"/repos/aio-libs/aiohttp/commits/{sha}/status": {
            "state": "success",
            "statuses": [
                {
                    "state": "success",
                    "description": "Issue report skipped",
                    "context": "bedevere/issue-number",
                }
            ],
        },
        "/repos/aio-libs/aiohttp/pulls/5544": {
            "user": {"login": "aiohttp-bot"},
            "merged_by": {"login": "Mariatta"},
        },
    }

    getiter = {
        "/repos/aio-libs/aiohttp/pulls/5547/commits": [
            {
                "sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
                "commit": {
                    "message": "bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>"
                },
            }
        ]
    }

    gh = FakeGH(getitem=getitem, getiter=getiter)
    await status_change.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")  # does not leave a comment
    assert not hasattr(gh, "put_data")  # is not merged
    assert not hasattr(gh, "get_")  # is not merged

    assert not gh.getiter_url


async def test_pr_title_does_not_match():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {"sha": sha, "commit": {"committer": {"login": "aiohttp-bot"}}}
    event = sansio.Event(data, event="status", delivery_id="1")

    getitem = {
        f"/repos/aio-libs/aiohttp/commits/{sha}/status": {
            "state": "success",
            "statuses": [
                {
                    "state": "success",
                    "description": "Issue report skipped",
                    "context": "bedevere/issue-number",
                },
                {
                    "state": "success",
                    "description": "The Travis CI build passed",
                    "target_url": "https://travis-ci.org/aio-libs/aiohttp/builds/340259685?utm_source=github_status&utm_medium=notification",
                    "context": "continuous-integration/travis-ci/pr",
                },
            ],
        },
        "/repos/aio-libs/aiohttp/pulls/5544": {
            "user": {"login": "aiohttp-bot"},
            "merged_by": {"login": "Mariatta"},
        },
        f"/search/issues?q=type:pr+repo:aio-libs/aiohttp+sha:{sha}": {
            "total_count": 1,
            "items": [
                {
                    "number": 5547,
                    "title": "bpo-32720: Fixed the replacement field grammar documentation.",
                    "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
                    "labels": [{"name": "awaiting merge"}],
                }
            ],
        },
    }

    getiter = {
        "/repos/aio-libs/aiohttp/pulls/5547/commits": [
            {
                "sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
                "commit": {
                    "message": "bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>"
                },
            }
        ]
    }

    gh = FakeGH(getitem=getitem, getiter=getiter)
    await status_change.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")  # does not leave a comment
    assert not hasattr(gh, "put_data")  # is not merged


async def test_pr_not_found_for_commit():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    data = {"sha": sha, "commit": {"committer": None, "author": None}}

    event = sansio.Event(data, event="status", delivery_id="1")

    getitem = {
        f"/search/issues?q=type:pr+repo:aio-libs/aiohttp+sha:{sha}": {
            "total_count": 0,
            "items": [],
        }
    }

    gh = FakeGH(getitem=getitem)
    await status_change.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")  # does not leave a comment
    assert not hasattr(gh, "put_data")  # does not leave a comment
