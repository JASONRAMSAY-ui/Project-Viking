# Put credit spread simulation (model-priced, return on risk per trade, net of costs)

Entry ~45 DTE, short ~0.20 delta, width 0.5 sigma, cost 5% of width. Fit = 2016-22, test = 2023+. Black-Scholes with IV = iv_mult x 90d realised vol and vol-on-drop. NOT real fills.


## Management rules (iv_mult 1.15)


### Entries: signal

- hold to expiry                       FIT  n= 55 win= 82% avg=-0.05 med=+0.13 worst=-1.06 PF=0.69 maxDD=5.9
                                       TEST n= 20 win= 80% avg=+0.00 med=+0.13 worst=-1.06 PF=1.05 maxDD=1.1
- exit at 21 cal DTE                   FIT  n= 55 win= 71% avg=+0.01 med=+0.07 worst=-0.92 PF=1.16 maxDD=2.5
                                       TEST n= 20 win= 75% avg=+0.02 med=+0.10 worst=-0.55 PF=1.39 maxDD=0.7
- exit at 14 cal DTE                   FIT  n= 55 win= 62% avg=-0.02 med=+0.11 worst=-1.01 PF=0.80 maxDD=3.9
                                       TEST n= 20 win= 75% avg=+0.04 med=+0.12 worst=-0.45 PF=1.79 maxDD=0.6
- take profit 50%                      FIT  n= 55 win= 85% avg=-0.10 med=+0.06 worst=-1.06 PF=0.38 maxDD=6.0
                                       TEST n= 20 win= 90% avg=-0.03 med=+0.05 worst=-1.06 PF=0.67 maxDD=1.1
- take profit 50% + exit 21 DTE        FIT  n= 55 win= 78% avg=-0.01 med=+0.05 worst=-0.92 PF=0.90 maxDD=2.3
                                       TEST n= 20 win= 90% avg=+0.01 med=+0.05 worst=-0.55 PF=1.32 maxDD=0.5
- stop: close below short strike       FIT  n= 55 win= 80% avg=+0.05 med=+0.13 worst=-0.47 PF=1.64 maxDD=1.8
                                       TEST n= 20 win= 70% avg=-0.01 med=+0.13 worst=-0.39 PF=0.94 maxDD=0.6
- stop: loss = 2x credit               FIT  n= 55 win= 80% avg=+0.02 med=+0.13 worst=-0.73 PF=1.24 maxDD=2.5
                                       TEST n= 20 win= 80% avg=+0.03 med=+0.13 worst=-0.51 PF=1.49 maxDD=0.5
- TP 50% + stop below short + 21 DTE   FIT  n= 55 win= 78% avg=+0.01 med=+0.05 worst=-0.37 PF=1.18 maxDD=1.4
                                       TEST n= 20 win= 85% avg=+0.00 med=+0.05 worst=-0.38 PF=1.02 maxDD=0.5

### Entries: control

- hold to expiry                       FIT  n=923 win= 87% avg=+0.01 med=+0.13 worst=-1.06 PF=1.10 maxDD=7.9
                                       TEST n=739 win= 88% avg=+0.03 med=+0.13 worst=-1.06 PF=1.30 maxDD=9.1
- exit at 21 cal DTE                   FIT  n=923 win= 64% avg=-0.03 med=+0.07 worst=-1.06 PF=0.69 maxDD=26.4
                                       TEST n=739 win= 63% avg=-0.02 med=+0.06 worst=-0.95 PF=0.76 maxDD=15.1
- exit at 14 cal DTE                   FIT  n=923 win= 71% avg=-0.02 med=+0.10 worst=-1.06 PF=0.81 maxDD=17.4
                                       TEST n=739 win= 74% avg=+0.00 med=+0.10 worst=-1.02 PF=1.01 maxDD=9.4
- take profit 50%                      FIT  n=923 win= 92% avg=-0.01 med=+0.05 worst=-1.06 PF=0.81 maxDD=12.6
                                       TEST n=739 win= 92% avg=-0.01 med=+0.05 worst=-1.06 PF=0.86 maxDD=12.1
- take profit 50% + exit 21 DTE        FIT  n=923 win= 74% avg=-0.03 med=+0.04 worst=-1.06 PF=0.54 maxDD=31.9
                                       TEST n=739 win= 72% avg=-0.03 med=+0.04 worst=-0.95 PF=0.59 maxDD=20.5
- stop: close below short strike       FIT  n=923 win= 70% avg=-0.03 med=+0.13 worst=-1.04 PF=0.77 maxDD=27.8
                                       TEST n=739 win= 73% avg=-0.00 med=+0.13 worst=-0.65 PF=0.99 maxDD=9.0
- stop: loss = 2x credit               FIT  n=923 win= 78% avg=-0.02 med=+0.13 worst=-1.06 PF=0.84 maxDD=22.7
                                       TEST n=739 win= 80% avg=+0.00 med=+0.13 worst=-0.90 PF=1.03 maxDD=7.4
- TP 50% + stop below short + 21 DTE   FIT  n=923 win= 73% avg=-0.04 med=+0.04 worst=-0.75 PF=0.52 maxDD=35.2
                                       TEST n=739 win= 70% avg=-0.03 med=+0.04 worst=-0.65 PF=0.53 maxDD=25.5

## Sensitivity to the volatility-premium assumption (hold to expiry vs 50% TP + stop + 21 DTE, signal entries)

- iv_mult 1.00 hold to expiry                       ALL n= 75 win= 80% avg=-0.07 med=+0.12 worst=-1.06 PF=0.59 maxDD=6.5
- iv_mult 1.00 TP 50% + stop below short + 21 DTE   ALL n= 75 win= 80% avg=-0.01 med=+0.04 worst=-0.43 PF=0.83 maxDD=1.7
- iv_mult 1.15 hold to expiry                       ALL n= 75 win= 81% avg=-0.04 med=+0.13 worst=-1.06 PF=0.75 maxDD=5.5
- iv_mult 1.15 TP 50% + stop below short + 21 DTE   ALL n= 75 win= 80% avg=+0.01 med=+0.05 worst=-0.38 PF=1.13 maxDD=1.7
- iv_mult 1.30 hold to expiry                       ALL n= 75 win= 84% avg=-0.00 med=+0.14 worst=-1.06 PF=0.98 maxDD=4.8
- iv_mult 1.30 TP 50% + stop below short + 21 DTE   ALL n= 75 win= 81% avg=+0.02 med=+0.06 worst=-0.37 PF=1.66 maxDD=1.3

## Per asset (rule: TP 50% + stop below short + 21 DTE; signal entries, all years)

- /ES:XCME   n=  3 win=100% avg=+0.05 med=+0.05 worst=+0.04 PF=inf maxDD=0.0
- QQQ        n=  4 win=100% avg=+0.05 med=+0.05 worst=+0.04 PF=inf maxDD=0.0
- TLT        n= 13 win= 77% avg=-0.01 med=+0.05 worst=-0.38 PF=0.79 maxDD=0.4
- IWM        n=  7 win= 86% avg=+0.03 med=+0.06 worst=-0.21 PF=1.94 maxDD=0.2
- /NQ:XCME   n=  2 win=100% avg=+0.06 med=+0.06 worst=+0.06 PF=inf maxDD=0.0
- SPY        n=  1 win=100% avg=+0.04 med=+0.04 worst=+0.04 PF=inf maxDD=0.0
- GLD        n=  5 win=100% avg=+0.05 med=+0.05 worst=+0.04 PF=inf maxDD=0.0
- XLF        n=  5 win=100% avg=+0.06 med=+0.04 worst=+0.04 PF=inf maxDD=0.0
- /GC:XCEC   n= 10 win= 70% avg=+0.01 med=+0.04 worst=-0.21 PF=1.22 maxDD=0.3
- /CL:XNYM   n=  9 win=100% avg=+0.10 med=+0.08 worst=+0.06 PF=inf maxDD=0.0
- /ZN:XCBT   n= 16 win= 50% avg=-0.10 med=-0.00 worst=-0.33 PF=0.19 maxDD=1.3
