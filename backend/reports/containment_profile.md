# Historical containment profile (puts: downside)

Price-only, daily bars, ~10 years. Strike distance = z x 90d daily vol x sqrt(horizon); z=0.84 is about 0.20 delta, z=1.28 about 0.10 delta. 'Contained' = strike never touched within the horizon.


## /ES:XCME  (2513 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2418 | 1.1 | 2.2 | 3.9 | 5.1 | 9.5 | 48% | 66% | 72% | 81% | 87% | 92% |
| 10d | 2413 | 1.6 | 3.1 | 5.4 | 7.5 | 14.5 | 48% | 66% | 72% | 79% | 88% | 92% |
| 21d | 2402 | 2.2 | 4.6 | 8.1 | 10.6 | 18.9 | 48% | 66% | 72% | 80% | 87% | 91% |
| 30d | 2393 | 2.5 | 5.4 | 9.5 | 12.9 | 26.5 | 49% | 67% | 72% | 80% | 87% | 90% |
| 45d | 2378 | 3.0 | 6.3 | 11.4 | 15.5 | 32.7 | 51% | 67% | 73% | 80% | 86% | 90% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1073 paths touched; 26% by day 5, 49% by day 10, 76% by day 21, 87% by day 30, 100% by day 45; median first touch day 11; 68% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 21 days): 21d contained at z=0.84: 100% (all days 66%); at z=1.28: 100% (all days 80%).

## QQQ  (2510 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2415 | 1.4 | 2.9 | 4.8 | 6.3 | 10.0 | 51% | 68% | 74% | 82% | 89% | 93% |
| 10d | 2410 | 2.0 | 3.9 | 7.0 | 8.8 | 13.9 | 51% | 68% | 74% | 82% | 89% | 92% |
| 21d | 2399 | 2.6 | 5.9 | 9.9 | 12.9 | 17.2 | 52% | 68% | 73% | 81% | 89% | 93% |
| 30d | 2390 | 3.0 | 7.0 | 11.6 | 14.9 | 21.8 | 52% | 68% | 73% | 81% | 89% | 93% |
| 45d | 2375 | 3.7 | 8.0 | 14.0 | 18.2 | 25.4 | 51% | 68% | 73% | 84% | 89% | 93% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1059 paths touched; 24% by day 5, 45% by day 10, 73% by day 21, 86% by day 30, 100% by day 45; median first touch day 12; 68% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 22 days): 21d contained at z=0.84: 100% (all days 68%); at z=1.28: 100% (all days 81%).

## TLT  (2510 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2415 | 1.1 | 2.1 | 3.2 | 3.9 | 5.6 | 44% | 65% | 73% | 82% | 90% | 96% |
| 10d | 2410 | 1.6 | 3.0 | 4.4 | 5.6 | 8.0 | 42% | 62% | 71% | 82% | 91% | 96% |
| 21d | 2399 | 2.5 | 4.5 | 6.7 | 8.3 | 11.0 | 38% | 61% | 70% | 81% | 91% | 96% |
| 30d | 2390 | 3.0 | 5.4 | 8.0 | 10.0 | 13.2 | 38% | 61% | 69% | 81% | 91% | 96% |
| 45d | 2375 | 3.8 | 6.6 | 10.1 | 12.6 | 16.4 | 38% | 61% | 70% | 81% | 90% | 97% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1366 paths touched; 13% by day 5, 34% by day 10, 67% by day 21, 81% by day 30, 100% by day 45; median first touch day 14; 46% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 91 days): 21d contained at z=0.84: 74% (all days 61%); at z=1.28: 95% (all days 81%).

## IWM  (2510 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2415 | 1.6 | 3.1 | 4.8 | 6.4 | 11.3 | 46% | 65% | 73% | 83% | 90% | 94% |
| 10d | 2410 | 2.3 | 4.3 | 6.9 | 9.1 | 14.3 | 45% | 65% | 74% | 82% | 90% | 93% |
| 21d | 2399 | 3.3 | 6.4 | 10.0 | 12.4 | 20.1 | 45% | 66% | 73% | 81% | 90% | 93% |
| 30d | 2390 | 3.9 | 7.4 | 11.8 | 14.7 | 33.9 | 46% | 67% | 73% | 82% | 89% | 93% |
| 45d | 2375 | 4.7 | 8.7 | 14.1 | 17.3 | 41.6 | 47% | 68% | 75% | 83% | 88% | 92% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1124 paths touched; 19% by day 5, 41% by day 10, 71% by day 21, 85% by day 30, 100% by day 45; median first touch day 13; 63% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 44 days): 21d contained at z=0.84: 86% (all days 66%); at z=1.28: 93% (all days 81%).

## /NQ:XCME  (1991 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 1896 | 1.7 | 3.2 | 5.2 | 6.7 | 11.0 | 47% | 66% | 72% | 81% | 88% | 92% |
| 10d | 1891 | 2.3 | 4.6 | 7.4 | 9.3 | 15.6 | 48% | 67% | 72% | 80% | 88% | 93% |
| 21d | 1880 | 3.0 | 6.5 | 10.3 | 13.6 | 19.8 | 50% | 66% | 71% | 81% | 88% | 93% |
| 30d | 1871 | 3.7 | 7.4 | 12.2 | 16.1 | 24.3 | 50% | 65% | 72% | 81% | 90% | 93% |
| 45d | 1856 | 4.7 | 8.5 | 15.1 | 20.4 | 27.5 | 48% | 66% | 73% | 84% | 90% | 93% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 876 paths touched; 23% by day 5, 45% by day 10, 73% by day 21, 84% by day 30, 100% by day 45; median first touch day 12; 70% of breached paths closed back beyond the strike by day 45.

## SPY  (2511 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2416 | 0.9 | 2.1 | 3.8 | 5.0 | 8.8 | 52% | 68% | 74% | 82% | 88% | 92% |
| 10d | 2411 | 1.4 | 3.0 | 5.2 | 7.1 | 14.1 | 50% | 68% | 74% | 81% | 89% | 92% |
| 21d | 2400 | 2.0 | 4.4 | 8.0 | 10.6 | 17.7 | 50% | 68% | 73% | 81% | 87% | 92% |
| 30d | 2391 | 2.3 | 5.2 | 9.2 | 12.8 | 26.2 | 52% | 67% | 73% | 81% | 87% | 91% |
| 45d | 2376 | 2.8 | 6.0 | 11.1 | 15.2 | 32.4 | 52% | 68% | 74% | 81% | 86% | 90% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1038 paths touched; 25% by day 5, 47% by day 10, 74% by day 21, 86% by day 30, 100% by day 45; median first touch day 11; 67% of breached paths closed back beyond the strike by day 45.

## GLD  (2510 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2415 | 1.0 | 1.9 | 3.2 | 4.4 | 6.8 | 51% | 71% | 77% | 86% | 92% | 95% |
| 10d | 2410 | 1.4 | 2.7 | 4.4 | 5.5 | 9.6 | 50% | 70% | 77% | 86% | 92% | 96% |
| 21d | 2399 | 2.0 | 3.7 | 5.8 | 7.4 | 13.3 | 51% | 72% | 78% | 86% | 95% | 98% |
| 30d | 2390 | 2.4 | 4.3 | 6.7 | 8.4 | 13.9 | 51% | 71% | 78% | 89% | 96% | 99% |
| 45d | 2375 | 2.8 | 5.1 | 7.7 | 9.6 | 15.6 | 52% | 73% | 81% | 91% | 97% | 99% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1012 paths touched; 16% by day 5, 36% by day 10, 64% by day 21, 82% by day 30, 100% by day 45; median first touch day 15; 60% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 37 days): 21d contained at z=0.84: 95% (all days 72%); at z=1.28: 100% (all days 86%).

## XLF  (2511 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2416 | 1.3 | 2.6 | 4.5 | 6.1 | 11.1 | 49% | 69% | 75% | 83% | 89% | 93% |
| 10d | 2411 | 1.9 | 3.8 | 6.3 | 8.5 | 15.8 | 50% | 67% | 74% | 81% | 89% | 92% |
| 21d | 2400 | 3.0 | 5.7 | 8.9 | 11.5 | 23.2 | 47% | 65% | 72% | 81% | 89% | 93% |
| 30d | 2391 | 3.4 | 6.7 | 10.4 | 14.4 | 33.4 | 47% | 66% | 73% | 81% | 89% | 94% |
| 45d | 2376 | 4.1 | 7.7 | 13.1 | 16.8 | 41.5 | 49% | 68% | 74% | 83% | 89% | 93% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1115 paths touched; 21% by day 5, 42% by day 10, 74% by day 21, 87% by day 30, 100% by day 45; median first touch day 13; 63% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 38 days): 21d contained at z=0.84: 100% (all days 65%); at z=1.28: 100% (all days 81%).

## /CL:XNYM  (2511 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2416 | 2.9 | 5.6 | 9.0 | 12.0 | 21.3 | 45% | 64% | 70% | 79% | 89% | 93% |
| 10d | 2411 | 4.1 | 8.0 | 12.6 | 16.3 | 35.3 | 46% | 63% | 71% | 80% | 88% | 93% |
| 21d | 2400 | 6.0 | 11.3 | 17.6 | 21.4 | 60.8 | 45% | 64% | 70% | 80% | 88% | 92% |
| 30d | 2391 | 7.2 | 13.3 | 20.0 | 25.6 | 68.3 | 45% | 63% | 70% | 80% | 89% | 93% |
| 45d | 2376 | 8.9 | 16.4 | 22.5 | 31.0 | 75.0 | 45% | 64% | 72% | 83% | 90% | 95% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1203 paths touched; 18% by day 5, 43% by day 10, 72% by day 21, 86% by day 30, 100% by day 45; median first touch day 12; 57% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 58 days): 21d contained at z=0.84: 88% (all days 64%); at z=1.28: 97% (all days 80%).

## /GC:XCEC  (2513 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2418 | 1.2 | 2.1 | 3.5 | 4.7 | 7.9 | 45% | 67% | 75% | 84% | 92% | 95% |
| 10d | 2413 | 1.6 | 3.0 | 4.8 | 5.9 | 10.7 | 47% | 68% | 75% | 84% | 92% | 96% |
| 21d | 2402 | 2.2 | 4.1 | 6.4 | 8.1 | 13.6 | 49% | 69% | 77% | 85% | 93% | 97% |
| 30d | 2393 | 2.6 | 4.8 | 7.4 | 9.1 | 17.7 | 48% | 71% | 78% | 87% | 95% | 99% |
| 45d | 2378 | 3.0 | 5.7 | 8.4 | 10.4 | 18.2 | 50% | 71% | 78% | 89% | 97% | 99% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1072 paths touched; 16% by day 5, 38% by day 10, 67% by day 21, 84% by day 30, 100% by day 45; median first touch day 14; 64% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 65 days): 21d contained at z=0.84: 60% (all days 69%); at z=1.28: 83% (all days 85%).

## /ZN:XCBT  (2513 bars)

Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile

| Horizon | n | 50% | 75% | 90% | 95% | 99% | contained z=0.5 | contained z=0.84 | contained z=1.0 | contained z=1.28 | contained z=1.65 | contained z=2.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5d | 2418 | 0.4 | 0.8 | 1.3 | 1.6 | 2.2 | 40% | 61% | 69% | 80% | 90% | 95% |
| 10d | 2413 | 0.6 | 1.1 | 1.8 | 2.2 | 3.3 | 40% | 59% | 67% | 79% | 89% | 94% |
| 21d | 2402 | 1.0 | 1.7 | 2.7 | 3.5 | 4.6 | 38% | 59% | 66% | 78% | 88% | 94% |
| 30d | 2393 | 1.1 | 2.0 | 3.3 | 4.1 | 5.9 | 36% | 59% | 68% | 78% | 87% | 94% |
| 45d | 2378 | 1.4 | 2.6 | 4.0 | 4.8 | 7.5 | 36% | 57% | 66% | 77% | 88% | 92% |

Timing of breaches of the z=0.84 strike (set for 21d, watched to 45d): 1384 paths touched; 15% by day 5, 38% by day 10, 70% by day 21, 84% by day 30, 100% by day 45; median first touch day 14; 41% of breached paths closed back beyond the strike by day 45.

After a downtrend break (phase 1 signal, 111 days): 21d contained at z=0.84: 59% (all days 59%); at z=1.28: 68% (all days 78%).
