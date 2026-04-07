"""Tests for the expanded tier table — at least one read, write, and destructive per new service."""

from __future__ import annotations

import pytest

from aaws.safety.classifier import classify


# ── CloudWatch Logs ──────────────────────────────────────────────────────────

def test_logs_read():
    assert classify("aws logs describe-log-groups", 0) == 0

def test_logs_write():
    assert classify("aws logs create-log-group --log-group-name test", 0) == 1

def test_logs_destructive():
    assert classify("aws logs delete-log-group --log-group-name test", 0) == 2


# ── Kinesis ──────────────────────────────────────────────────────────────────

def test_kinesis_read():
    assert classify("aws kinesis describe-stream --stream-name test", 0) == 0

def test_kinesis_write():
    assert classify("aws kinesis create-stream --stream-name test --shard-count 1", 0) == 1

def test_kinesis_destructive():
    assert classify("aws kinesis delete-stream --stream-name test", 0) == 2


# ── ElastiCache ──────────────────────────────────────────────────────────────

def test_elasticache_read():
    assert classify("aws elasticache describe-cache-clusters", 0) == 0

def test_elasticache_write():
    assert classify("aws elasticache create-cache-cluster --cache-cluster-id test", 0) == 1

def test_elasticache_destructive():
    assert classify("aws elasticache delete-cache-cluster --cache-cluster-id test", 0) == 2


# ── Auto Scaling ─────────────────────────────────────────────────────────────

def test_autoscaling_read():
    assert classify("aws autoscaling describe-auto-scaling-groups", 0) == 0

def test_autoscaling_write():
    assert classify("aws autoscaling create-auto-scaling-group --auto-scaling-group-name test", 0) == 1

def test_autoscaling_destructive():
    assert classify("aws autoscaling delete-auto-scaling-group --auto-scaling-group-name test", 0) == 2


# ── Cognito Identity Provider ────────────────────────────────────────────────

def test_cognito_read():
    assert classify("aws cognito-idp describe-user-pool --user-pool-id test", 0) == 0

def test_cognito_write():
    assert classify("aws cognito-idp create-user-pool --pool-name test", 0) == 1

def test_cognito_destructive():
    assert classify("aws cognito-idp delete-user-pool --user-pool-id test", 0) == 2


# ── Redshift ─────────────────────────────────────────────────────────────────

def test_redshift_read():
    assert classify("aws redshift describe-clusters", 0) == 0

def test_redshift_write():
    assert classify("aws redshift create-cluster --cluster-identifier test --node-type dc2.large", 0) == 1

def test_redshift_destructive():
    assert classify("aws redshift delete-cluster --cluster-identifier test", 0) == 2


# ── ELBv2 ────────────────────────────────────────────────────────────────────

def test_elbv2_read():
    assert classify("aws elbv2 describe-load-balancers", 0) == 0

def test_elbv2_write():
    assert classify("aws elbv2 create-load-balancer --name test", 0) == 1

def test_elbv2_destructive():
    assert classify("aws elbv2 delete-load-balancer --load-balancer-arn arn:test", 0) == 2


# ── API Gateway ──────────────────────────────────────────────────────────────

def test_apigateway_read():
    assert classify("aws apigateway get-rest-apis", 0) == 0

def test_apigateway_write():
    assert classify("aws apigateway create-rest-api --name test", 0) == 1

def test_apigateway_destructive():
    assert classify("aws apigateway delete-rest-api --rest-api-id abc123", 0) == 2


# ── SageMaker ────────────────────────────────────────────────────────────────

def test_sagemaker_read():
    assert classify("aws sagemaker describe-endpoint --endpoint-name test", 0) == 0

def test_sagemaker_write():
    assert classify("aws sagemaker create-endpoint --endpoint-name test", 0) == 1

def test_sagemaker_destructive():
    assert classify("aws sagemaker delete-endpoint --endpoint-name test", 0) == 2


# ── Glue ─────────────────────────────────────────────────────────────────────

def test_glue_read():
    assert classify("aws glue get-databases", 0) == 0

def test_glue_write():
    assert classify("aws glue create-database --database-input Name=test", 0) == 1

def test_glue_destructive():
    assert classify("aws glue delete-database --name test", 0) == 2


# ── Step Functions ───────────────────────────────────────────────────────────

def test_stepfunctions_read():
    assert classify("aws stepfunctions describe-state-machine --state-machine-arn arn:test", 0) == 0

def test_stepfunctions_write():
    assert classify("aws stepfunctions create-state-machine --name test --definition '{}'", 0) == 1

def test_stepfunctions_destructive():
    assert classify("aws stepfunctions delete-state-machine --state-machine-arn arn:test", 0) == 2


# ── Elastic Beanstalk ────────────────────────────────────────────────────────

def test_elasticbeanstalk_read():
    assert classify("aws elasticbeanstalk describe-environments", 0) == 0

def test_elasticbeanstalk_write():
    assert classify("aws elasticbeanstalk create-application --application-name test", 0) == 1

def test_elasticbeanstalk_destructive():
    assert classify("aws elasticbeanstalk terminate-environment --environment-name test", 0) == 2


# ── STS ──────────────────────────────────────────────────────────────────────

def test_sts_read():
    assert classify("aws sts get-caller-identity", 0) == 0

def test_sts_write():
    assert classify("aws sts assume-role --role-arn arn:test --role-session-name test", 0) == 1

def test_sts_decode_read():
    assert classify("aws sts decode-authorization-message --encoded-message abc", 0) == 0

def test_sts_get_session_token():
    assert classify("aws sts get-session-token", 0) == 1

def test_sts_assume_role_with_saml():
    assert classify("aws sts assume-role-with-saml --role-arn arn:test", 0) == 1
