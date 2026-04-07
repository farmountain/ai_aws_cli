# Capability: error-recovery

## Purpose

Detect and interpret errors from AWS CLI and LLM providers, surfacing actionable guidance instead of raw error output.

## Requirements

### Requirement: AWS credential errors are detected and surfaced with actionable guidance
The system SHALL pattern-match `aws` CLI stderr output for known credential error strings (`Unable to locate credentials`, `ExpiredTokenException`, `NoCredentialsError`) and display a targeted, actionable message instead of the raw AWS error.

#### Scenario: Expired SSO session
- **WHEN** `aws` CLI exits with `ExpiredTokenException` in stderr
- **THEN** the system displays: "Your AWS session has expired. Refresh it with: `aws sso login --profile <profile>`"

#### Scenario: No credentials configured
- **WHEN** `aws` CLI exits with `Unable to locate credentials` in stderr
- **THEN** the system displays: "No AWS credentials found. Configure them with: `aws configure`"

### Requirement: Permission errors surface the required IAM action
The system SHALL detect `AccessDeniedException` in `aws` CLI stderr and extract and display the denied IAM action from the error message.

#### Scenario: AccessDeniedException with action
- **WHEN** `aws` CLI exits with `AccessDeniedException: User is not authorized to perform: ec2:DescribeInstances`
- **THEN** the system displays the denied action (`ec2:DescribeInstances`) and suggests: "Check your IAM permissions or switch to a profile with the required access."

### Requirement: Resource errors are fed to the LLM for plain-English interpretation
The system SHALL detect AWS resource errors (4xx HTTP range: not found, already exists, conflict) and send the error back to the LLM to produce a plain-English explanation and suggested next steps.

#### Scenario: BucketNotEmpty interpreted with next steps
- **WHEN** `aws s3 rb` fails with `BucketNotEmpty`
- **THEN** the system sends the error to the LLM
- **THEN** the LLM returns: "The bucket is not empty. Delete all objects first with `aws s3 rm s3://<bucket> --recursive`, then retry."
- **THEN** that interpretation is displayed to the user

#### Scenario: NoSuchBucket error interpreted
- **WHEN** `aws s3 ls s3://nonexistent-bucket` fails with `NoSuchBucket`
- **THEN** the system displays the LLM interpretation: "The bucket 'nonexistent-bucket' does not exist. Check the bucket name or run `aaws list my S3 buckets` to see available buckets."

### Requirement: aws CLI not installed is detected at startup
The system SHALL check for the presence of the `aws` executable in PATH at startup. If not found, the system SHALL display installation instructions and exit immediately.

#### Scenario: aws CLI missing on startup
- **WHEN** `aaws` is invoked and `aws` is not found in PATH
- **THEN** the system displays: "AWS CLI not found. Install it from: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
- **THEN** the system exits with a non-zero exit code without attempting any LLM or AWS calls

### Requirement: Network/timeout errors surface a retry suggestion
The system SHALL detect timeout and network errors from both the LLM provider and the `aws` CLI subprocess, and display a message suggesting the user check connectivity and retry.

#### Scenario: LLM call times out
- **WHEN** the LLM provider call exceeds the configured timeout (default: 30 seconds)
- **THEN** the system displays: "Request timed out. Check your network connection and try again."
- **THEN** no `aws` command is executed
