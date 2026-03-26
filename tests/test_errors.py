"""Tests for error classification and credential message extraction."""

from __future__ import annotations

import pytest

from aaws.errors import ErrorType, classify_error, get_credential_message


# ── classify_error ────────────────────────────────────────────────────────────

def test_classify_expired_token():
    assert classify_error("ExpiredTokenException: Token has expired") == ErrorType.EXPIRED_TOKEN


def test_classify_no_credentials():
    assert classify_error("Unable to locate credentials") == ErrorType.NO_CREDENTIALS


def test_classify_no_credentials_variant():
    assert classify_error("NoCredentialsError: no credentials found") == ErrorType.NO_CREDENTIALS


def test_classify_access_denied():
    stderr = "AccessDeniedException: User is not authorized to perform: ec2:DescribeInstances"
    assert classify_error(stderr) == ErrorType.ACCESS_DENIED


def test_classify_bucket_not_empty():
    stderr = "An error occurred (BucketNotEmpty) when calling the DeleteBucket operation"
    assert classify_error(stderr) == ErrorType.BUCKET_NOT_EMPTY


def test_classify_no_such_bucket():
    stderr = "An error occurred (NoSuchBucket) when calling the ListObjects operation"
    assert classify_error(stderr) == ErrorType.NO_SUCH_BUCKET


def test_classify_resource_not_found():
    stderr = "An error occurred (NoSuchKey): The specified key does not exist."
    assert classify_error(stderr) == ErrorType.RESOURCE_NOT_FOUND


def test_classify_unknown():
    assert classify_error("Some completely unexpected error XYZ99999") == ErrorType.UNKNOWN


# ── get_credential_message ────────────────────────────────────────────────────

def test_credential_message_expired_token():
    msg = get_credential_message("ExpiredTokenException", profile="prod")
    assert msg is not None
    assert "aws sso login" in msg
    assert "prod" in msg


def test_credential_message_no_credentials():
    msg = get_credential_message("Unable to locate credentials", profile="default")
    assert msg is not None
    assert "aws configure" in msg


def test_credential_message_access_denied_with_action():
    stderr = "AccessDeniedException: User is not authorized to perform: s3:GetObject"
    msg = get_credential_message(stderr, profile="default")
    assert msg is not None
    assert "s3:GetObject" in msg


def test_credential_message_returns_none_for_unknown():
    msg = get_credential_message("Some unrelated error", profile="default")
    assert msg is None
