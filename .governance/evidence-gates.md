# Evidence Gates — ai_aws_cli

Evidence types required before a task can be marked complete.

| ID | Evidence Type | Description |
|---|---|---|
| ET-01 | test_result | Test suite run with pass/fail counts |
| ET-02 | build_result | Build exit code 0 + output |
| ET-03 | lint_result | Linter/type checker zero errors |
| ET-04 | diff_review | File diff reviewed and confirmed |
| ET-05 | spec_reference | Named requirement cited |
| ET-06 | done_check | All definition-of-done dimensions assessed |

## Gate Requirements by Task Type

| Task Type | Required Evidence |
|---|---|
| Code/Backend | ET-01, ET-02, ET-04, ET-06 |
| Architecture | ET-04, ET-05, ET-06 |
| Documentation | ET-04, ET-06 |
| Configuration | ET-04, ET-06 |
