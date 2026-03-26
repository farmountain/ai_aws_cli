"""Tests for output shape detection and Rich rendering."""

from __future__ import annotations

import json

import pytest

from aaws.formatter import format_output


def test_empty_string_no_results(capsys: pytest.CaptureFixture):
    format_output("", raw=False)
    captured = capsys.readouterr()
    assert "No results" in captured.out


def test_empty_json_list(capsys: pytest.CaptureFixture):
    format_output(json.dumps([]), raw=False)
    captured = capsys.readouterr()
    assert "No results" in captured.out


def test_empty_json_dict(capsys: pytest.CaptureFixture):
    format_output(json.dumps({}), raw=False)
    captured = capsys.readouterr()
    assert "No results" in captured.out


def test_raw_mode_passes_through(capsys: pytest.CaptureFixture):
    payload = json.dumps({"Buckets": [{"Name": "my-bucket"}]})
    format_output(payload, raw=True)
    captured = capsys.readouterr()
    assert "my-bucket" in captured.out


def test_list_shape_renders(capsys: pytest.CaptureFixture):
    data = json.dumps({"Buckets": [{"Name": "b1"}, {"Name": "b2"}]})
    format_output(data, raw=False)
    captured = capsys.readouterr()
    assert len(captured.out) > 0


def test_singular_dict_shape_renders(capsys: pytest.CaptureFixture):
    data = json.dumps({"User": {"UserId": "AIDABC", "UserName": "alice"}})
    format_output(data, raw=False)
    captured = capsys.readouterr()
    assert "alice" in captured.out


def test_string_list_renders_bullets(capsys: pytest.CaptureFixture):
    data = json.dumps({"QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123/my-q"]})
    format_output(data, raw=False)
    captured = capsys.readouterr()
    assert "my-q" in captured.out


def test_ec2_reservations_flattened(capsys: pytest.CaptureFixture):
    data = json.dumps({
        "Reservations": [
            {
                "Instances": [
                    {
                        "InstanceId": "i-abc123",
                        "InstanceType": "t3.micro",
                        "State": {"Name": "running"},
                    }
                ]
            }
        ]
    })
    format_output(data, raw=False)
    captured = capsys.readouterr()
    assert "i-abc123" in captured.out
