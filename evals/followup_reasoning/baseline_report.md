# Follow-up Reasoning Evaluation — baseline

Generated: 2026-08-30T22:53:56+08:00

## Outcome

- Conversations: 50
- User turns: 130
- Conversation pass rate: 0.0
- Turn pass rate: 0.3846

## Follow-up metrics

| Metric | Passed / Errors | Total | Rate |
|---|---:|---:|---:|
| followup_resolution_pass_rate | 0 | 80 | 0.0 |
| action_result_understanding_pass_rate | 0 | 32 | 0.0 |
| troubleshooting_progression_pass_rate | 0 | 72 | 0.0 |
| previous_recommendation_awareness_pass_rate | 9 | 80 | 0.1125 |
| diagnostic_answer_handling_pass_rate | 0 | 12 | 0.0 |
| repeated_step_error_rate | 0 | 24 | 0.0 |
| incorrect_refusal_rate | 25 | 80 | 0.3125 |
| escalation_accuracy | 24 | 40 | 0.6 |

## Failure distribution

| Failure | Count |
|---|---:|
| FOLLOWUP_RESOLUTION_ERROR | 80 |
| PREVIOUS_RECOMMENDATION_IGNORED | 83 |
| ACTION_RESULT_ERROR | 46 |
| TROUBLESHOOTING_STAGE_ERROR | 80 |
| INCORRECT_REFUSAL | 25 |
| ANSWER_CONTENT_ERROR | 59 |
| MISSING_ESCALATION | 12 |
| DIAGNOSTIC_ANSWER_ERROR | 12 |
| PREMATURE_ESCALATION | 4 |
