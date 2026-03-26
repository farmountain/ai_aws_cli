"""
Static risk tier lookup table for common AWS CLI command prefixes.

Tier definitions:
  0 - Read-only     (describe, list, get, head)  → auto-execute
  1 - Write         (create, put, update, start)  → confirm y/n
  2 - Destructive   (delete, terminate, detach)   → warn + type "yes"
  3 - Catastrophic  (bulk-delete, org/account ops) → refuse by default

Lookup strategy: find the longest matching prefix in TIER_TABLE.
Unrecognised commands fall back to the LLM-assigned tier.
"""

from __future__ import annotations

# Longer/more-specific prefixes must appear after shorter ones; the classifier
# always picks the longest match, so order within this dict does not matter.

TIER_TABLE: dict[str, int] = {
    # ── EC2 ───────────────────────────────────────────────────────────────────
    "aws ec2 describe": 0,
    "aws ec2 get-": 0,
    "aws ec2 list-": 0,
    "aws ec2 run-instances": 1,
    "aws ec2 start-instances": 1,
    "aws ec2 stop-instances": 1,
    "aws ec2 reboot-instances": 1,
    "aws ec2 create-": 1,
    "aws ec2 modify-": 1,
    "aws ec2 associate-": 1,
    "aws ec2 attach-": 1,
    "aws ec2 import-": 1,
    "aws ec2 allocate-address": 1,
    "aws ec2 terminate-instances": 2,
    "aws ec2 delete-": 2,
    "aws ec2 detach-": 2,
    "aws ec2 disassociate-": 2,
    "aws ec2 deregister-": 2,
    "aws ec2 release-address": 2,
    "aws ec2 cancel-": 2,

    # ── S3 ────────────────────────────────────────────────────────────────────
    "aws s3 ls": 0,
    "aws s3 cp": 1,
    "aws s3 mv": 1,
    "aws s3 sync": 1,
    "aws s3 mb": 1,
    "aws s3 presign": 0,
    "aws s3 rm": 2,
    "aws s3 rb": 2,

    # S3 API
    "aws s3api get-": 0,
    "aws s3api list-": 0,
    "aws s3api head-": 0,
    "aws s3api put-": 1,
    "aws s3api create-bucket": 1,
    "aws s3api upload-": 1,
    "aws s3api copy-object": 1,
    "aws s3api delete-object": 2,
    "aws s3api delete-objects": 2,
    "aws s3api delete-bucket": 2,

    # ── IAM ───────────────────────────────────────────────────────────────────
    "aws iam get-": 0,
    "aws iam list-": 0,
    "aws iam generate-": 0,
    "aws iam simulate-": 0,
    "aws iam create-role": 1,
    "aws iam create-group": 1,
    "aws iam create-user": 1,
    "aws iam create-policy": 1,
    "aws iam create-instance-profile": 1,
    "aws iam tag-": 1,
    "aws iam update-": 1,
    "aws iam add-": 1,
    "aws iam upload-": 1,
    "aws iam set-default-policy-version": 2,
    "aws iam put-role-policy": 2,
    "aws iam put-user-policy": 2,
    "aws iam put-group-policy": 2,
    "aws iam attach-role-policy": 2,
    "aws iam attach-user-policy": 2,
    "aws iam attach-group-policy": 2,
    "aws iam create-access-key": 2,
    "aws iam delete-": 2,
    "aws iam detach-": 2,
    "aws iam remove-": 2,
    "aws iam deactivate-": 2,

    # ── Lambda ────────────────────────────────────────────────────────────────
    "aws lambda get-": 0,
    "aws lambda list-": 0,
    "aws lambda create-function": 1,
    "aws lambda update-function": 1,
    "aws lambda publish-": 1,
    "aws lambda put-": 1,
    "aws lambda add-permission": 1,
    "aws lambda invoke": 1,
    "aws lambda tag-": 1,
    "aws lambda delete-": 2,
    "aws lambda remove-permission": 2,
    "aws lambda untag-": 2,

    # ── RDS ───────────────────────────────────────────────────────────────────
    "aws rds describe-": 0,
    "aws rds list-": 0,
    "aws rds create-db-instance": 1,
    "aws rds create-db-cluster": 1,
    "aws rds create-db-snapshot": 1,
    "aws rds modify-db-instance": 1,
    "aws rds modify-db-cluster": 1,
    "aws rds start-db-instance": 1,
    "aws rds stop-db-instance": 1,
    "aws rds reboot-db-instance": 1,
    "aws rds restore-": 1,
    "aws rds delete-db-instance": 2,
    "aws rds delete-db-cluster": 2,
    "aws rds delete-db-snapshot": 2,

    # ── CloudFormation ────────────────────────────────────────────────────────
    "aws cloudformation describe-": 0,
    "aws cloudformation get-": 0,
    "aws cloudformation list-": 0,
    "aws cloudformation validate-": 0,
    "aws cloudformation create-stack": 1,
    "aws cloudformation update-stack": 1,
    "aws cloudformation deploy": 1,
    "aws cloudformation continue-update-rollback": 1,
    "aws cloudformation delete-stack": 2,
    "aws cloudformation cancel-update-stack": 2,

    # ── EKS ───────────────────────────────────────────────────────────────────
    "aws eks describe-": 0,
    "aws eks list-": 0,
    "aws eks create-cluster": 1,
    "aws eks create-nodegroup": 1,
    "aws eks update-": 1,
    "aws eks associate-": 1,
    "aws eks delete-cluster": 2,
    "aws eks delete-nodegroup": 2,
    "aws eks disassociate-": 2,

    # ── ECS ───────────────────────────────────────────────────────────────────
    "aws ecs describe-": 0,
    "aws ecs list-": 0,
    "aws ecs create-cluster": 1,
    "aws ecs create-service": 1,
    "aws ecs register-task-definition": 1,
    "aws ecs run-task": 1,
    "aws ecs update-service": 1,
    "aws ecs start-task": 1,
    "aws ecs delete-cluster": 2,
    "aws ecs delete-service": 2,
    "aws ecs stop-task": 2,
    "aws ecs deregister-task-definition": 2,

    # ── Route53 ───────────────────────────────────────────────────────────────
    "aws route53 list-": 0,
    "aws route53 get-": 0,
    "aws route53 test-": 0,
    "aws route53 change-resource-record-sets": 1,
    "aws route53 create-hosted-zone": 1,
    "aws route53 associate-": 1,
    "aws route53 delete-hosted-zone": 2,
    "aws route53 disassociate-": 2,

    # ── DynamoDB ──────────────────────────────────────────────────────────────
    "aws dynamodb describe-": 0,
    "aws dynamodb list-tables": 0,
    "aws dynamodb get-item": 0,
    "aws dynamodb query": 0,
    "aws dynamodb scan": 0,
    "aws dynamodb create-table": 1,
    "aws dynamodb put-item": 1,
    "aws dynamodb update-item": 1,
    "aws dynamodb update-table": 1,
    "aws dynamodb batch-write-item": 1,
    "aws dynamodb delete-item": 2,
    "aws dynamodb delete-table": 2,

    # ── SNS / SQS ─────────────────────────────────────────────────────────────
    "aws sns list-": 0,
    "aws sns get-": 0,
    "aws sns create-topic": 1,
    "aws sns subscribe": 1,
    "aws sns publish": 1,
    "aws sns set-": 1,
    "aws sns delete-topic": 2,
    "aws sns unsubscribe": 2,

    "aws sqs list-": 0,
    "aws sqs get-": 0,
    "aws sqs receive-message": 0,
    "aws sqs create-queue": 1,
    "aws sqs send-message": 1,
    "aws sqs set-": 1,
    "aws sqs delete-message": 2,
    "aws sqs delete-queue": 2,
    "aws sqs purge-queue": 2,

    # ── Secrets Manager / SSM ─────────────────────────────────────────────────
    "aws secretsmanager describe-": 0,
    "aws secretsmanager get-": 0,
    "aws secretsmanager list-": 0,
    "aws secretsmanager create-secret": 1,
    "aws secretsmanager put-secret-value": 1,
    "aws secretsmanager update-secret": 1,
    "aws secretsmanager rotate-secret": 1,
    "aws secretsmanager delete-secret": 2,

    "aws ssm describe-": 0,
    "aws ssm get-": 0,
    "aws ssm list-": 0,
    "aws ssm put-parameter": 1,
    "aws ssm send-command": 1,
    "aws ssm start-session": 1,
    "aws ssm delete-parameter": 2,
    "aws ssm delete-parameters": 2,

    # ── CloudWatch ────────────────────────────────────────────────────────────
    "aws cloudwatch describe-": 0,
    "aws cloudwatch get-": 0,
    "aws cloudwatch list-": 0,
    "aws cloudwatch put-metric-alarm": 1,
    "aws cloudwatch put-metric-data": 1,
    "aws cloudwatch enable-alarm-actions": 1,
    "aws cloudwatch delete-alarms": 2,
    "aws cloudwatch disable-alarm-actions": 2,

    # ── ECR ───────────────────────────────────────────────────────────────────
    "aws ecr describe-": 0,
    "aws ecr get-": 0,
    "aws ecr list-": 0,
    "aws ecr batch-get-image": 0,
    "aws ecr create-repository": 1,
    "aws ecr put-": 1,
    "aws ecr tag-resource": 1,
    "aws ecr delete-repository": 2,
    "aws ecr batch-delete-image": 2,
    "aws ecr untag-resource": 2,

    # ── Organizations (tier 3) ─────────────────────────────────────────────────
    "aws organizations describe-": 0,
    "aws organizations list-": 0,
    "aws organizations create-account": 3,
    "aws organizations delete-organization": 3,
    "aws organizations remove-account-from-organization": 3,
    "aws organizations leave-organization": 3,
}

# Additional substring patterns that always force tier 3.
# Each entry is a tuple of (required_prefix, required_substring) — both must match.
# Use (prefix, "") to match on prefix alone, or ("", substring) for substring-only.
TIER_3_SUBSTRINGS: list[tuple[str, str]] = [
    ("aws iam delete-account-alias", ""),
    ("aws iam delete-account-password-policy", ""),
    # s3 rm with --recursive wipes an entire bucket/prefix
    ("aws s3 rm", "--recursive"),
]
