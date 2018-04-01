"""Prevent merging of [WIP] or WIP titled PRs
"""

from gidgethub import routing

from . import util

router = routing.Router()

STATUS_CONTEXT = "github-bot/work-in-progress"

FAILURE_URL = "https://devguide.python.org/pullrequest/#submitting"  # TODO: replace with proper URL


WIP_LABEL = 'Work in progress'
OK_STATUS = util.create_status(STATUS_CONTEXT, util.StatusState.SUCCESS,
                               description="No [WIP]/WIP: text in PR title")
FAILURE_STATUS_1 = util.create_status(STATUS_CONTEXT, util.StatusState.FAILURE,
                                      description="[WIP] found in title",
                                      target_url=FAILURE_URL)
FAILURE_STATUS_2 = util.create_status(STATUS_CONTEXT, util.StatusState.FAILURE,
                                      description="WIP: found in PR title",
                                      target_url=FAILURE_URL)



@router.register('pull_request', action='opened')
@router.register('pull_request', action='synchronize')
async def set_status(event, gh, *args, **kwargs):
    pull_request = event.data["pull_request"]
    title = pull_request['title']
    should_label = True
    if title.startswith('[WIP]'):
        status = FAILURE_STATUS_1
    elif title.startswith('WIP:'):
        status = FAILURE_STATUS_2
    else:
        status = OK_STATUS
        should_label = False
    await util.post_status(gh, event, status)
    if should_label:
        if any(WIP_LABEL == label['name'] for label in pull_request['labels']):
            return
        await gh.post(pull_request['labels_url'], data=[WIP_LABEL])
    else:
        for label in pull_request['labels']:
            if label['name'] == WIP_LABEL:
                await gh.delete(label['url'])


@router.register('pull_request', action='edited')
async def title_edited(event, gh, *args, **kwargs):
    """Set the status on a pull request that has changed its title."""
    if 'title' not in event.data['changes']:
        return
    await set_status(event, gh)



@router.register('pull_request', action='labeled')
@router.register('pull_request', action='unlabeled')
async def update_label(event, gh, *args, **kwargs):
    """Update the status if the "Work in progress" label was added."""
    if util.no_labels(event.data):
        return
    if util.label_name(event.data) == WIP_LABEL:
        await set_status(event, gh)
