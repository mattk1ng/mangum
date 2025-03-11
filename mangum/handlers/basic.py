from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, field_validator

from mangum.handlers.utils import (
    handle_exclude_headers,
    handle_multi_value_headers,
)
from mangum.types import (
    LambdaConfig,
    LambdaContext,
    LambdaEvent,
    Response,
    Scope,
)


class BaseModelWithForbidExtra(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @classmethod
    def is_valid(cls, obj):
        try:
            cls.model_validate(obj)
            return True
        except ValidationError:
            return False


class MethodEnum(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"
    CONNECT = "CONNECT"


class BasicHandlerEventScope(BaseModelWithForbidExtra):
    path: str
    headers: dict[str, str]
    method: MethodEnum


class BasicHandlerEvent(BaseModelWithForbidExtra):
    scope: BasicHandlerEventScope
    body: bytes

    @field_validator("body", mode="before")
    def check_bytes(cls, v, info: ValidationInfo):
        if not isinstance(v, bytes):
            raise ValueError("body must be of type bytes")
        return v


class BasicHandler:
    @classmethod
    def infer(cls, event: LambdaEvent, context: LambdaContext, config: LambdaConfig) -> bool:
        return BasicHandlerEvent.is_valid(event)

    def __init__(self, event: LambdaEvent, context: LambdaContext, config: LambdaConfig) -> None:
        self.event = event
        self.context = context
        self.config = config

    @property
    def body(self) -> bytes:
        return self.event.get("body", b"")

    @property
    def scope(self) -> Scope:
        headers = self.event.get("headers", {}) or {}
        headers = {k.lower(): v for k, v in headers.items()}

        return {
            "type": "http",
            "path": self.event["scope"]["path"],
            "method": self.event["scope"]["method"],
            "headers": [[k.encode(), v.encode()] for k, v in headers.items()],
            "query_string": b"",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "aws.event": self.event,
            "aws.context": self.context,
        }

    def __call__(self, response: Response) -> dict[str, Any]:
        finalized_headers, _ = handle_multi_value_headers(response["headers"])

        return {
            "statusCode": response["status"],
            "headers": handle_exclude_headers(finalized_headers, self.config),
            "body": response["body"],
        }
