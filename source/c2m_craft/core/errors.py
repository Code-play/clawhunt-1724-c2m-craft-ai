"""Typed errors shared by the CLI and the HTTP layer.

Every error carries a stable machine code plus optional details, so the web API
can serialise it without guessing and the tests can assert on codes rather than
on message wording.
"""

from __future__ import annotations


class CraftError(Exception):
    code = "craft_error"
    http_status = 400

    def __init__(self, message: str, details=None, *, code: str | None = None,
                 http_status: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details if details is not None else []
        if code:
            self.code = code
        if http_status:
            self.http_status = http_status

    def as_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationFailed(CraftError):
    code = "validation_failed"
    http_status = 422


class ContractError(ValidationFailed):
    code = "contract_violation"

    def __init__(self, contract: str, errors: list, message: str | None = None) -> None:
        text = message or f"{contract} validation failed ({len(errors)} problem(s))"
        super().__init__(text, details=errors, code=self.code)
        self.contract = contract


class NotFound(CraftError):
    code = "not_found"
    http_status = 404


class Conflict(CraftError):
    code = "conflict"
    http_status = 409


class BadRequest(CraftError):
    code = "bad_request"
    http_status = 400


class InsufficientFacts(ValidationFailed):
    code = "insufficient_facts"
