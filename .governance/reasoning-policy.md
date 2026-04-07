# Reasoning Policy — ai_aws_cli

Before producing any plan, decision, or implementation, apply this sequence:

| Stage | Name | Gate |
|---|---|---|
| 1 | Outcome | Written outcome statement — what does success look like? |
| 2 | Inversion | What would make this go wrong? List failure modes. |
| 3 | Spec review | Read the relevant spec scenarios. |
| 4 | Architecture | Does this respect system boundaries? |
| 5 | TDD | Write tests first. |
| 6 | Implementation | Implement minimally. No gold-plating. |
| 7 | Evidence | Collect required evidence (tests, diffs, build). |
| 8 | UX/AX review | Who is affected? Run the checklist. |
| 9 | Done check | Do all definition-of-done dimensions pass? |
| 10 | Reflexion | What should be remembered? What would be done differently? |

Stages 1-4 are mandatory. Skipping requires logging a reason.
