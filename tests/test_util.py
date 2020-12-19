import http
import pytest
import gidgethub

from unittest import mock


from aiohttp_bot import util


class FakeGH:
    def __init__(self, *, getiter=None, getitem=None, post=None, patch=None):
        self._getitem_return = getitem
        self._getiter_return = getiter
        self._post_return = post
        self._patch_return = patch
        self.getitem_url = None
        self.getiter_url = None
        self.patch_url = self.patch_data = None
        self.post_url = self.post_data = None

    async def getitem(self, url):
        self.getitem_url = url
        to_return = self._getitem_return[self.getitem_url]
        if isinstance(to_return, Exception):
            raise to_return
        else:
            return to_return

    async def getiter(self, url):
        self.getiter_url = url
        to_iterate = self._getiter_return[url]
        for item in to_iterate:
            yield item

    async def patch(self, url, *, data):
        self.patch_url = url
        self.patch_data = data
        return self._patch_return

    async def post(self, url, *, data):
        self.post_url = url
        self.post_data = data
        print(type(self._post_return))
        if isinstance(self._post_return, Exception):
            print("raising")
            raise self._post_return
        else:
            return self._post_return


def test_title_normalization():
    title = "abcd"
    body = "1234"
    assert util.normalize_title(title, body) == title

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations …"
    body = "…(GH-1478)\r\n\r\nstuff"
    expected = (
        "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations (GH-1478)"
    )
    assert util.normalize_title(title, body) == expected

    title = "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations …"
    body = "…(GH-1478)"
    assert util.normalize_title(title, body) == expected

    title = (
        "[2.7] bpo-29243: Fix Makefile with respect to --enable-optimizations (GH-14…"
    )
    body = "…78)"
    assert util.normalize_title(title, body) == expected


def test_message_normalization():
    message = "<!-- This is an HTML comment -->And this is the part we want"
    assert util.normalize_message(message) == "\n\nAnd this is the part we want"

    message = "<!-- HTML comment -->Part we want<!-- HTML comment 2 -->"
    assert util.normalize_message(message) == "\n\nPart we want"

    message = "\r\nParts <!--comment--> we want\r\nincluded"
    assert util.normalize_message(message) == "\n\nParts  we want\r\nincluded"


async def test_get_gh_participants_different_creator_and_committer():
    gh = FakeGH(
        getitem={
            "/repos/aio-libs/aiohttp/pulls/5544": {
                "user": {"login": "aiohttp-bot"},
                "merged_by": {"login": "bedevere-bot"},
            }
        }
    )
    result = await util.get_gh_participants(gh, 5544)
    assert result == "@aiohttp-bot and @bedevere-bot"


async def test_get_gh_participants_same_creator_and_committer():
    gh = FakeGH(
        getitem={
            "/repos/aio-libs/aiohttp/pulls/5544": {
                "user": {"login": "bedevere-bot"},
                "merged_by": {"login": "bedevere-bot"},
            }
        }
    )
    result = await util.get_gh_participants(gh, 5544)
    assert result == "@bedevere-bot"


async def test_get_gh_participants_pr_not_merged():
    gh = FakeGH(
        getitem={
            "/repos/aio-libs/aiohttp/pulls/5544": {
                "user": {"login": "bedevere-bot"},
                "merged_by": None,
            }
        }
    )
    result = await util.get_gh_participants(gh, 5544)
    assert result == "@bedevere-bot"


async def test_get_gh_participants_merged_by_aiohttp_bot():
    gh = FakeGH(
        getitem={
            "/repos/aio-libs/aiohttp/pulls/5544": {
                "user": {"login": "bedevere-bot"},
                "merged_by": {"login": "aiohttp-bot"},
            }
        }
    )
    result = await util.get_gh_participants(gh, 5544)
    assert result == "@bedevere-bot"


def test_get_participants_different_creator_and_committer():
    assert (
        util.get_participants("aiohttp-bot", "bedevere-bot")
        == "@aiohttp-bot and @bedevere-bot"
    )


def test_get_participants_merged_by_aiohttp_bot():
    assert util.get_participants("bedevere-bot", "aiohttp-bot") == "@bedevere-bot"


@mock.patch("subprocess.check_output")
def test_is_aiohttp_repo_contains_first_aiohttp_commit(subprocess_check_output):
    mock_output = b"""commit 7f777ed95a19224294949e1b4ce56bbffcb1fe9f
Author: Guido van Rossum <guido@python.org>
Date:   Thu Aug 9 14:25:15 1990 +0000

    Initial revision"""
    subprocess_check_output.return_value = mock_output
    assert util.is_aiohttp_repo()


def test_is_not_aiohttp_repo():
    assert util.is_aiohttp_repo() == False


async def test_is_committer():
    teams = [{"name": "not aiohttp committer"}]
    gh = FakeGH(getiter={"/orgs/aio-libs/teams": teams})
    with pytest.raises(ValueError):
        await util.is_committer(gh, "mariatta")

    teams = [{"name": "aiohttp-committers", "id": 42}]
    getitem = {"/teams/42/memberships/mariatta": True}
    gh = FakeGH(getiter={"/orgs/aio-libs/teams": teams}, getitem=getitem)
    assert await util.is_committer(gh, "mariatta")
    assert gh.getiter_url == "/orgs/aio-libs/teams"

    teams = [{"name": "aiohttp-committers", "id": 42}]
    getitem = {
        "/teams/42/memberships/aiohttp-bot": gidgethub.BadRequest(
            status_code=http.HTTPStatus(404)
        )
    }
    gh = FakeGH(getiter={"/orgs/aio-libs/teams": teams}, getitem=getitem)
    assert not await util.is_committer(gh, "aiohttp-bot")

    teams = [{"name": "aiohttp-committers", "id": 42}]
    getitem = {
        "/teams/42/memberships/aiohttp-bot": gidgethub.BadRequest(
            status_code=http.HTTPStatus(400)
        )
    }
    gh = FakeGH(getiter={"/orgs/aio-libs/teams": teams}, getitem=getitem)
    with pytest.raises(gidgethub.BadRequest):
        await util.is_committer(gh, "aiohttp-bot")


def test_pr_is_awaiting_merge():
    labels = [{"name": "awaiting merge"}]
    assert util.pr_is_awaiting_merge(labels) is True


def test_pr_is_do_not_merge():
    labels = [{"name": "awaiting merge"}, {"name": "DO-NOT-MERGE"}]
    assert util.pr_is_awaiting_merge(labels) is False


#
# def test_pr_is_automerge():
#     labels = [
#         {"name": "CLA signed"},
#         {"name": util.AUTOMERGE_LABEL},
#         {"name": "awaiting review"},
#     ]
#     assert util.pr_is_automerge(labels) is True


def test_pr_is_not_awaiting_merge():
    labels = [{"name": "skip issue"}, {"name": "awaiting review"}]
    assert util.pr_is_awaiting_merge(labels) is False


#
# def test_pr_is_not_automerge():
#     labels = [{"name": "CLA signed"}, {"name": "awaiting merge"}]
#     assert util.pr_is_automerge(labels) is False


async def test_comment_on_pr_success():
    issue_number = 100
    message = "Thanks for the PR!"

    gh = FakeGH(
        post={
            "html_url": f"https://github.com/aio-libs/aiohttp/pull/{issue_number}#issuecomment-401309376"
        }
    )

    await util.comment_on_pr(gh, issue_number, message)
    assert gh.post_url == f"/repos/aio-libs/aiohttp/issues/{issue_number}/comments"
    assert gh.post_data == {"body": message}


async def test_comment_on_pr_failure():
    issue_number = 100
    message = "Thanks for the PR!"
    gh = FakeGH(post=gidgethub.BadRequest(status_code=http.HTTPStatus(400)))

    with pytest.raises(gidgethub.BadRequest):
        await util.comment_on_pr(gh, issue_number, message)


async def test_assign_pr_to_committer():

    issue_number = 100
    committer_login = "Mariatta"
    gh = FakeGH()

    await util.assign_pr_to_committer(gh, issue_number, committer_login)
    assert gh.patch_url == f"/repos/aio-libs/aiohttp/issues/{issue_number}"


async def test_get_pr_for_commit():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    gh = FakeGH(
        getitem={
            f"/search/issues?q=type:pr+repo:aio-libs/aiohttp+sha:{sha}": {
                "total_count": 1,
                "items": [
                    {
                        "number": 5547,
                        "title": "[3.6] bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)",
                        "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
                    }
                ],
            }
        }
    )
    result = await util.get_pr_for_commit(gh, sha)
    assert result == {
        "number": 5547,
        "title": "[3.6] bpo-32720: Fixed the replacement field grammar documentation. (GH-5544)",
        "body": "\n\n`arg_name` and `element_index` are defined as `digit`+ instead of `integer`.\n(cherry picked from commit 7a561afd2c79f63a6008843b83733911d07f0119)\n\nCo-authored-by: Mariatta <Mariatta@users.noreply.github.com>",
    }


async def test_get_pr_for_commit_not_found():
    sha = "f2393593c99dd2d3ab8bfab6fcc5ddee540518a9"
    gh = FakeGH(
        getitem={
            f"/search/issues?q=type:pr+repo:aio-libs/aiohttp+sha:{sha}": {
                "total_count": 0,
                "items": [],
            }
        }
    )
    result = await util.get_pr_for_commit(gh, sha)

    assert result is None
