from aiohttp import web
import pytest

from github_bot.__main__ import create_app


@pytest.fixture
async def client(aiohttp_client):
    app = await create_app()
    return await aiohttp_client(app)


async def test_ping(client):
    headers = {"x-github-event": "ping",
               "x-github-delivery": "1234"}
    data = {"zen": "testing is good"}
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 200


async def test_success(client):
    headers = {"x-github-event": "project",
               "x-github-delivery": "1234"}
    # Sending a payload that shouldn't trigger any networking, but no errors
    # either.
    data = {"action": "created"}
    response = await client.post("/", headers=headers, json=data)
    assert response.status == 200


async def test_failure(client):
    """Even in the face of an exception, the server should not crash."""
    # Missing key headers.
    response = await client.post("/", headers={})
    assert response.status == 500
