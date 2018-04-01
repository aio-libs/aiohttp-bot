from gidgethub import sansio


from github_bot import wip


async def test_set_status_failure(fake_gh):
    data = {
        'pull_request': {
            'statuses_url': 'https://api.github.com/blah/blah/git-sha',
            'title': "[WIP] work in progress",
            'issue_url': "issue_url",
            'labels': [],
            'labels_url': "labels_url",
        },
    }
    issue_data = {
        'labels': [
            {'name': "non-trivial"},
        ],
    }
    event = sansio.Event(data, event='pull_request', delivery_id='12345')
    gh = fake_gh(getitem=issue_data)
    await wip.set_status(event, gh)
    assert len(gh.post_) == 2
    url, status = gh.post_[0]
    assert url == 'https://api.github.com/blah/blah/git-sha'
    assert status['state'] == 'failure'
    assert status['target_url'].startswith('https://devguide.python.org')
    assert status['context'] == 'github-bot/work-in-progress'

    url, label = gh.post_[1]
    assert url == 'https://api.github.com/labels_url'
    assert label == ['Work in progress']


async def test_set_status_ok(fake_gh):
    data = {
        'pull_request': {
            'statuses_url': 'https://api.github.com/blah/blah/git-sha',
            'title': "work in progress",
            'issue_url': "issue_url",
            'labels': [],
            'labels_url': "labels_url",
        },
    }
    issue_data = {
        'labels': [
            {'name': "non-trivial"},
        ],
    }
    event = sansio.Event(data, event='pull_request', delivery_id='12345')
    gh = fake_gh(getitem=issue_data)
    await wip.set_status(event, gh)
    assert len(gh.post_) == 1
    url, status = gh.post_[0]
    assert url == 'https://api.github.com/blah/blah/git-sha'
    assert status['state'] == 'success'
    assert status['context'] == 'github-bot/work-in-progress'


async def test_set_status_ok_remove_label(fake_gh):
    data = {
        'pull_request': {
            'statuses_url': 'https://api.github.com/blah/blah/git-sha',
            'title': "work in progress",
            'issue_url': "issue_url",
            'labels': [{'name': 'Work in progress',
                        'url': 'label_url'}],
            'labels_url': "labels_url",
        },
    }
    issue_data = {
        'labels': [
            {'name': "non-trivial"},
        ],
    }
    event = sansio.Event(data, event='pull_request', delivery_id='12345')
    gh = fake_gh(getitem=issue_data)
    await wip.set_status(event, gh)
    assert len(gh.post_) == 1
    url, status = gh.post_[0]
    assert url == 'https://api.github.com/blah/blah/git-sha'
    assert status['state'] == 'success'
    assert status['context'] == 'github-bot/work-in-progress'

    assert gh.delete_url == 'https://api.github.com/label_url'
