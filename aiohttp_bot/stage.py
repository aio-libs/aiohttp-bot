import re

import gidgethub

from gidgethub import routing

from . import util

router = routing.Router()


@router.register("pull_request_review", action="submitted")
async def new_review(event, gh, *args, **kwargs):
    """Update the stage based on the latest review."""
    pull_request = event.data["pull_request"]
    review = event.data["review"]
    reviewer = util.user_login(review)
    state = review["state"].lower()
    if state == "commented":
        # Don't care about comment reviews.
        return
    elif await util.is_committer(gh, reviewer):
        if state == "approved":
            await util.stage(gh, await util.issue_for_PR(gh, pull_request), util.Blocker.merge)

