import json

import pytest

from mangum import Mangum
from mangum.handlers import BasicHandler


def get_valid_mock_aws_basic_event(method, path, body, headers):
    return {"scope": {"method": method, "path": path, "headers": headers}, "body": body}


@pytest.mark.parametrize("method,path,body", [("GET", "/", "")])
def test_basic_event_scope_real(method, path, body):
    event = get_valid_mock_aws_basic_event(method, path, body, {})
    example_context = {}
    handler = BasicHandler(event, example_context, {})

    assert handler.scope == {
        "path": path,
        "method": method,
        "headers": [],
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "aws.context": {},
        "aws.event": event,
    }


@pytest.mark.parametrize(
    "model, is_valid",
    [
        ({}, False),
        ({"scope": {"path": "/", "method": "POST", "headers": {}}, "body": b""}, True),
        ({"scope": {"path": "/", "method": "POST", "headers": {}}}, False),
        ({"scope": {"path": "/", "method": "POST", "headers": {}}, "body": b"", "extra": ""}, False),
        ({"scope": {"path": "/", "method": "UNKNOWN", "headers": {}}, "body": b""}, False),
        ({"scope": {"path": "/", "method": "UNKNOWN", "headers": {}}, "body": ""}, False),
    ],
)
def test_basic_event_infer(model, is_valid):
    example_context = {}
    assert BasicHandler.infer(model, example_context, {}) == is_valid


@pytest.mark.parametrize(
    "method,path,request_content_type,response_content_type,payload,response",
    [
        ("GET", "/", b"text/plain; charset=utf-8", b"text/plain; charset=utf-8", b"Hello world", b"Hello world"),
        (
            "GET",
            "/",
            b"application/json",
            b"text/plain; charset=utf-8",
            json.dumps({"hello": "world"}).encode("utf-8"),
            b"Hello world",
        ),
        (
            "GET",
            "/",
            b"text/plain; charset=utf-8",
            b"text/plain; charset=utf-8",
            b"",
            b"Hello world",
        ),
    ],
)
def test_aws_api_gateway_response(method, path, request_content_type, response_content_type, payload, response):
    async def app(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", response_content_type]],
            }
        )
        await send({"type": "http.response.body", "body": response})

    event = get_valid_mock_aws_basic_event(method, path, payload, {"Content-Type": request_content_type})

    handler = Mangum(app, lifespan="off")

    result = handler(event, {})

    assert result == {
        "statusCode": 200,
        "headers": {"content-type": response_content_type.decode()},
        "body": response,
    }
