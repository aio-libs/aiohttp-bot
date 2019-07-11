import os
from unittest import mock

from gidgethub import sansio

import redis
import kombu

os.environ["REDIS_URL"] = "someurl"

from aiohttp_bot import backport_pr


class FakeGH:
    def __init__(self, *, getitem=None, post=None, delete=None):
        self._getitem_return = getitem
        self.getitem_url = None
        self.getiter_url = None
        self._post_return = post
        self.delete_url = None
        self._delete_return = delete

    async def getitem(self, url, url_vars={}):
        self.getitem_url = sansio.format_url(url, url_vars)
        return self._getitem_return[self.getitem_url]

    async def post(self, url, *, data):
        self.post_url = url
        self.post_data = data
        return self._post_return

    async def delete(self, url, url_vars={}):
        self.delete_url = sansio.format_url(url, url_vars)


async def test_unmerged_pr_is_ignored():
    data = {"action": "closed", "pull_request": {"merged": False}}
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = FakeGH()
    await backport_pr.router.dispatch(event, gh)
    assert gh.getitem_url is None


async def test_labeled_on_unmerged_pr_is_ignored():
    data = {"action": "labeled", "pull_request": {"merged": False}}
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    gh = FakeGH()
    await backport_pr.router.dispatch(event, gh)
    assert gh.getitem_url is None


async def test_labeled_on_merged_pr_no_backport_label():
    data = {
        "action": "labeled",
        "pull_request": {
            "merged": True,
            "number": 1,
            "merged_by": {"login": "Mariatta"},
            "user": {"login": "Mariatta"},
            "merge_commit_sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
            "issue_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1",
        },
        "label": {"name": "enhancement"},
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    # label = "awaiting merge"
    # encoded_label = label.replace(" ", "%20")

    gh = FakeGH()
    await backport_pr.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")
    assert not hasattr(gh, "post_url")


async def test_merged_pr_no_backport_label():
    data = {
        "action": "closed",
        "pull_request": {
            "merged": True,
            "number": 1,
            "merged_by": {"login": "Mariatta"},
            "user": {"login": "Mariatta"},
            "merge_commit_sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
            "issue_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    label = "awaiting merge"
    encoded_label = label.replace(" ", "%20")

    getitem = {
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1": {
            "labels_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels{/name}",
            "labels": [
                {
                    "url": f"https://api.github.com/repos/aio-libs/aiohttp/labels/{encoded_label}",
                    "name": label,
                }
            ],
        },
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels": [],
    }

    gh = FakeGH(getitem=getitem)
    await backport_pr.router.dispatch(event, gh)
    assert not hasattr(gh, "post_data")
    assert not hasattr(gh, "post_url")


async def test_merged_pr_with_backport_label():
    data = {
        "action": "closed",
        "pull_request": {
            "merged": True,
            "number": 1,
            "merged_by": {"login": "Mariatta"},
            "user": {"login": "Mariatta"},
            "merge_commit_sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
            "issue_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    label = "awaiting merge"
    encoded_label = label.replace(" ", "%20")

    getitem = {
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1": {
            "labels_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels{/name}",
            "labels": [
                {
                    "url": f"https://api.github.com/repos/aio-libs/aiohttp/labels/{encoded_label}",
                    "name": label,
                }
            ],
        },
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels": [
            {"name": "needs backport to 3.7"}
        ],
    }

    post = {
        "html_url": "https://github.com/aio-libs/aiohttp/pull/1#issuecomment-401309376"
    }

    gh = FakeGH(getitem=getitem, post=post)
    with mock.patch("aiohttp_bot.tasks.backport_task.delay"):
        await backport_pr.router.dispatch(event, gh)
        assert "I'm working now to backport this PR to: 3.7" in gh.post_data["body"]
        assert gh.post_url == "/repos/aio-libs/aiohttp/issues/1/comments"


async def test_merged_pr_with_backport_label_thank_pr_author():
    data = {
        "action": "closed",
        "pull_request": {
            "merged": True,
            "number": 1,
            "merged_by": {"login": "Mariatta"},
            "user": {"login": "gvanrossum"},
            "merge_commit_sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
            "issue_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")

    label = "awaiting merge"
    encoded_label = label.replace(" ", "%20")

    getitem = {
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1": {
            "labels_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels{/name}",
            "labels": [
                {
                    "url": f"https://api.github.com/repos/aio-libs/aiohttp/labels/{encoded_label}",
                    "name": label,
                }
            ],
        },
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels": [
            {"name": "needs backport to 3.7"}
        ],
    }

    post = {
        "html_url": "https://github.com/aio-libs/aiohttp/pull/1#issuecomment-401309376"
    }

    gh = FakeGH(getitem=getitem, post=post)
    with mock.patch("aiohttp_bot.tasks.backport_task.delay"):
        await backport_pr.router.dispatch(event, gh)
        assert "I'm working now to backport this PR to: 3.7" in gh.post_data["body"]
        assert "Thanks @gvanrossum for the PR" in gh.post_data["body"]
        assert gh.post_url == "/repos/aio-libs/aiohttp/issues/1/comments"


async def test_backport_pr_redis_connection_error():
    data = {
        "action": "closed",
        "pull_request": {
            "merged": True,
            "number": 1,
            "merged_by": {"login": "Mariatta"},
            "user": {"login": "gvanrossum"},
            "merge_commit_sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
            "issue_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    label = "awaiting merge"
    encoded_label = label.replace(" ", "%20")

    getitem = {
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1": {
            "labels_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels{/name}",
            "labels": [
                {
                    "url": f"https://api.github.com/repos/aio-libs/aiohttp/labels/{encoded_label}",
                    "name": label,
                }
            ],
        },
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels": [
            {"name": "needs backport to 3.7"}
        ],
    }

    post = {
        "html_url": "https://github.com/aio-libs/aiohttp/pull/1#issuecomment-401309376"
    }

    gh = FakeGH(getitem=getitem, post=post)
    with mock.patch("aiohttp_bot.tasks.backport_task.delay") as backport_delay_mock:
        backport_delay_mock.side_effect = redis.exceptions.ConnectionError
        await backport_pr.router.dispatch(event, gh)
        assert "I'm having trouble backporting to `3.7`" in gh.post_data["body"]


async def test_backport_pr_kombu_operational_error():
    data = {
        "action": "closed",
        "pull_request": {
            "merged": True,
            "number": 1,
            "merged_by": {"login": "Mariatta"},
            "user": {"login": "gvanrossum"},
            "merge_commit_sha": "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9",
            "issue_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1",
        },
    }
    event = sansio.Event(data, event="pull_request", delivery_id="1")
    label = "awaiting merge"
    encoded_label = label.replace(" ", "%20")

    getitem = {
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1": {
            "labels_url": "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels{/name}",
            "labels": [
                {
                    "url": f"https://api.github.com/repos/aio-libs/aiohttp/labels/{encoded_label}",
                    "name": label,
                }
            ],
        },
        "https://api.github.com/repos/aio-libs/aiohttp/issues/1/labels": [
            {"name": "needs backport to 3.7"}
        ],
    }
    post = {
        "html_url": "https://github.com/aio-libs/aiohttp/pull/1#issuecomment-401309376"
    }

    gh = FakeGH(getitem=getitem, post=post)
    with mock.patch("aiohttp_bot.tasks.backport_task.delay") as backport_delay_mock:
        backport_delay_mock.side_effect = kombu.exceptions.OperationalError
        await backport_pr.router.dispatch(event, gh)
        assert "I'm having trouble backporting to `3.7`" in gh.post_data["body"]
