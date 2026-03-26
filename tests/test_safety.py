"""Tests for safety tier classification and profile protection."""

from __future__ import annotations

import pytest

from aaws.safety.classifier import classify, is_protected_profile


# ── classify() ────────────────────────────────────────────────────────────────

def test_classify_tier_0_describe():
    assert classify("aws ec2 describe-instances", 0) == 0


def test_classify_tier_0_s3_ls():
    # Static table must override LLM-supplied tier
    assert classify("aws s3 ls", 1) == 0


def test_classify_tier_0_iam_list():
    assert classify("aws iam list-users --output json", 2) == 0


def test_classify_tier_1_run_instances():
    assert classify("aws ec2 run-instances --instance-type t3.micro", 0) == 1


def test_classify_tier_1_create_bucket():
    assert classify("aws s3api create-bucket --bucket my-bucket", 0) == 1


def test_classify_tier_2_terminate():
    assert classify("aws ec2 terminate-instances --instance-ids i-abc123", 0) == 2


def test_classify_tier_2_rb():
    assert classify("aws s3 rb s3://my-bucket --force", 0) == 2


def test_classify_tier_2_delete_user():
    assert classify("aws iam delete-user --user-name alice", 0) == 2


def test_classify_tier_3_bulk_recursive_rm():
    assert classify("aws s3 rm s3://my-bucket --recursive", 0) == 3


def test_classify_tier_3_delete_org():
    assert classify("aws organizations delete-organization", 0) == 3


def test_classify_fallback_to_llm_tier():
    # Unknown command prefix — must defer to LLM-supplied tier
    assert classify("aws codecatalyst unknown-action --foo bar", 2) == 2


def test_classify_fallback_llm_tier_0():
    assert classify("aws unknown-service describe-stuff", 0) == 0


# ── is_protected_profile() ────────────────────────────────────────────────────

def test_protected_exact_match():
    assert is_protected_profile("production", ["production", "prod"]) is True


def test_protected_glob_star():
    assert is_protected_profile("prod-us-east-1", ["prod-*"]) is True


def test_protected_glob_no_match():
    assert is_protected_profile("development", ["production", "prod-*"]) is False


def test_protected_empty_patterns():
    assert is_protected_profile("anything", []) is False


def test_protected_case_insensitive():
    assert is_protected_profile("PRODUCTION", ["production"]) is True


def test_not_protected_dev():
    assert is_protected_profile("dev", ["prod-*", "production"]) is False
