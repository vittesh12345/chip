| scenario | task | result | expected | time | detail |
|---|---|---|---|---|---|
| acc_a | prove | PASS | PASS | 13.1s | 18 assertions, k-induction closed |
| acc_a | cover | PASS | PASS | 2.1s | 8/8 covers reached |
| acc_b | prove | PASS | PASS | 12.1s | 18 assertions, k-induction closed |
| acc_b | cover | PASS | PASS | 2.2s | 8/8 covers reached |
| neg_out_valid_q | cover | PASS | PASS | 1.3s | 5/5 covers reached |
| neg_out_valid_q | fire | FAIL | FAIL | 0.7s | `D_out_fire_matches_ref` fails at step 1 |
| neg_out_valid_q | loss | FAIL | FAIL | 0.8s | `D_no_silent_loss` fails at step 3 |
| neg_product | cover | PASS | PASS | 1.0s | 2/2 covers reached |
| neg_product | fire | FAIL | FAIL | 0.8s | `D_out_fire_matches_ref` fails at step 3 |
| res_a | prove | PASS | PASS | 10.4s | 18 assertions, k-induction closed |
| res_a | cover | PASS | PASS | 2.4s | 8/8 covers reached |
| res_b | prove | PASS | PASS | 15.3s | 18 assertions, k-induction closed |
| res_b | cover | PASS | PASS | 2.4s | 8/8 covers reached |
| therm_c0 | prove | PASS | PASS | 9.3s | 16 assertions, k-induction closed |
| therm_c0 | cover | PASS | PASS | 1.7s | 8/8 covers reached |
| therm_c1 | prove | PASS | PASS | 10.8s | 16 assertions, k-induction closed |
| therm_c1 | cover | PASS | PASS | 1.6s | 8/8 covers reached |
| therm_c2 | prove | PASS | PASS | 7.6s | 16 assertions, k-induction closed |
| therm_c2 | cover | PASS | PASS | 1.6s | 8/8 covers reached |
