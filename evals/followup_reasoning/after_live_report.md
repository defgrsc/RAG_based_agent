# Follow-up Reasoning Evaluation — after_live

Generated: 2026-08-30T23:18:12+08:00

## Outcome

- Conversations: 50
- User turns: 130
- Conversation pass rate: 0.48
- Turn pass rate: 0.7462

## Follow-up metrics

| Metric | Passed / Errors | Total | Rate |
|---|---:|---:|---:|
| followup_resolution_pass_rate | 80 | 80 | 1.0 |
| action_result_understanding_pass_rate | 29 | 32 | 0.9062 |
| troubleshooting_progression_pass_rate | 46 | 72 | 0.6389 |
| previous_recommendation_awareness_pass_rate | 73 | 80 | 0.9125 |
| diagnostic_answer_handling_pass_rate | 12 | 12 | 1.0 |
| repeated_step_error_rate | 0 | 24 | 0.0 |
| incorrect_refusal_rate | 3 | 80 | 0.0375 |
| escalation_accuracy | 18 | 40 | 0.45 |

## Failure distribution

| Failure | Count |
|---|---:|
| ANSWER_CONTENT_ERROR | 14 |
| PREMATURE_ESCALATION | 21 |
| INCORRECT_REFUSAL | 3 |
| PREVIOUS_RECOMMENDATION_IGNORED | 7 |
| MISSING_ESCALATION | 1 |
| ACTION_RESULT_ERROR | 3 |
