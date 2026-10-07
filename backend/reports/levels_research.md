# Do support levels matter for put-spread strike placement?  (191 symbols, strike fixed at 0.84σ/21d)

p = (level - strike)/σh. Excess = minus same-date universe average. t = monthly clustered. Blocks = 2016-19/2020-22/2023-26 ex_ror.


## swing low (5-bar fractal, 252d)
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                   38414    37.0     +0.6p   -0.000  -1.40  -0.011/+0.005/+0.005
strike just above level                    53943    34.1     -0.1p   +0.002   0.19  +0.008/-0.006/+0.005
strike 0-0.25σ BELOW level                 48716    33.0     -0.3p   +0.003   1.49  +0.007/+0.005/-0.001
strike 0.25-0.5σ below                     76150    33.1     +0.0p   +0.002   0.72  +0.004/+0.005/-0.001
strike >0.5σ below (level near price)     217477    32.8     -0.0p   -0.002  -1.08  -0.003/-0.001/-0.001
```

## 20d low
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                   78034    34.4     -0.3p   -0.001  -0.93  -0.010/+0.009/-0.001
strike just above level                   114300    34.3     +0.4p   -0.004  -0.79  -0.000/-0.003/-0.007
strike 0-0.25σ BELOW level                 75257    33.1     +0.4p   -0.003  -1.25  +0.001/-0.003/-0.006
strike 0.25-0.5σ below                     77654    32.4     +0.0p   +0.002  -0.06  +0.007/-0.002/+0.001
strike >0.5σ below (level near price)      77885    32.3     -0.5p   +0.007   2.12  +0.006/+0.001/+0.012
```

## 60d low
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                  226795    33.2     +0.2p   -0.001  -1.23  -0.002/-0.001/-0.001
strike just above level                    90650    33.3     +0.2p   -0.003  -0.87  -0.000/-0.001/-0.006
strike 0-0.25σ BELOW level                 43668    33.9     +0.1p   -0.002  -0.95  +0.001/+0.001/-0.006
strike 0.25-0.5σ below                     39243    34.0     -0.4p   +0.007   0.52  +0.003/+0.005/+0.012
strike >0.5σ below (level near price)      35188    34.1     -1.1p   +0.011   1.11  +0.013/+0.007/+0.013
```

## 252d low
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                  335964    33.9     +0.2p   -0.001  -0.73  -0.000/-0.002/-0.000
strike just above level                    36869    32.4     -0.6p   -0.002  -0.96  -0.016/-0.000/+0.004
strike 0-0.25σ BELOW level                 14849    33.7     -2.0p   +0.006   0.20  +0.011/+0.011/-0.001
strike 0.25-0.5σ below                     12640    34.1     -2.0p   +0.020   0.72  +0.025/+0.012/+0.025
strike >0.5σ below (level near price)      10919    35.9     -1.2p   +0.003  -0.74  +0.022/+0.013/-0.020
```

## HVN floor (180d profile)
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                  158493    36.0     +0.4p   +0.001  -0.23  +0.007/+0.004/-0.004
strike just above level                    50375    31.9     -1.0p   +0.000  -0.25  +0.004/+0.003/-0.003
strike 0-0.25σ BELOW level                 28699    31.6     -0.1p   -0.000  -0.76  -0.011/+0.003/+0.004
strike 0.25-0.5σ below                     29919    32.2     +0.8p   -0.006  -1.86  -0.010/-0.009/-0.001
strike >0.5σ below (level near price)      38764    31.6     -0.0p   +0.005   1.19  -0.003/+0.002/+0.011
```

## POC (180d profile)
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                  137745    36.2     +0.5p   +0.002  -0.15  +0.007/+0.002/-0.002
strike just above level                    45271    32.5     -1.0p   +0.003   0.02  +0.009/+0.007/-0.005
strike 0-0.25σ BELOW level                 26236    30.9     -1.0p   +0.006   0.76  -0.002/+0.016/+0.003
strike 0.25-0.5σ below                     28202    31.3     -0.0p   -0.004  -1.48  -0.006/-0.003/-0.003
strike >0.5σ below (level near price)      40491    31.4     +0.1p   +0.001  -0.39  -0.005/-0.004/+0.009
```

## AVWAP from 252d low
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                  139874    36.6     +0.9p   +0.003   0.08  +0.008/+0.002/+0.001
strike just above level                    60034    31.3     -0.7p   -0.001  -0.29  -0.004/+0.005/-0.004
strike 0-0.25σ BELOW level                 36260    29.8     -0.7p   -0.001  -0.21  -0.008/+0.004/-0.002
strike 0.25-0.5σ below                     39830    30.5     -0.1p   -0.005  -1.57  -0.007/-0.002/-0.005
strike >0.5σ below (level near price)      56289    32.4     -0.5p   +0.002   0.20  +0.001/-0.002/+0.007
```

## 50d SMA
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                   24883    39.5     +1.2p   -0.002  -0.93  -0.016/+0.020/-0.005
strike just above level                    58433    33.2     -1.3p   +0.005  -0.29  +0.006/+0.001/+0.008
strike 0-0.25σ BELOW level                 47881    31.2     -0.7p   +0.003   0.27  +0.003/+0.003/+0.004
strike 0.25-0.5σ below                     54781    31.3     +0.3p   -0.004  -1.42  -0.003/-0.002/-0.006
strike >0.5σ below (level near price)      73563    32.4     +0.8p   -0.003  -1.13  -0.002/-0.003/-0.004
```

## 200d SMA
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                  130010    36.7     +1.0p   +0.003   0.08  +0.011/+0.003/-0.001
strike just above level                    52751    31.3     -1.4p   +0.002  -0.08  +0.002/+0.007/-0.002
strike 0-0.25σ BELOW level                 26431    32.1     -0.1p   +0.000   0.18  -0.014/+0.008/+0.004
strike 0.25-0.5σ below                     26179    32.2     +0.5p   -0.002  -0.72  -0.002/-0.005/+0.001
strike >0.5σ below (level near price)      33130    31.3     -0.5p   +0.000   0.21  +0.003/-0.006/+0.003
```

## round number
```
bucket                                         n  touch%  ex_touch   ex_ror      t  blocks(ex_ror)
strike >0.5σ ABOVE level                  142364    36.7     +1.6p   -0.010  -4.60  -0.001/-0.010/-0.017
strike just above level                    72827    33.2     -0.4p   -0.004  -1.31  +0.001/-0.005/-0.006
strike 0-0.25σ BELOW level                 55191    33.3     -0.1p   -0.001  -0.56  +0.003/-0.001/-0.004
strike 0.25-0.5σ below                     68544    32.5     -0.5p   +0.005   1.86  +0.000/+0.007/+0.006
strike >0.5σ below (level near price)     105090    30.2     -1.6p   +0.017   6.00  +0.004/+0.015/+0.026
```

# Reaction test: price tests support and the close holds above it -> next 10d return (σ units), excess vs same date
```
level                                 held n   ex_r10      t | broke n   ex_r10      t
swing low (5-bar fractal, 252d)        74917   +0.002   0.24 |   39425   -0.006  -0.61
20d low                                30865   +0.004   0.48 |   27331   -0.002   0.84
60d low                                14757   -0.021  -0.53 |   13640   +0.002   0.49
252d low                                4919   -0.040  -0.67 |    4950   -0.049   0.32
HVN floor (180d profile)               19211   -0.021  -1.81 |  119372   -0.018  -2.17
POC (180d profile)                     21276   -0.018  -1.34 |  145990   -0.018  -2.22
AVWAP from 252d low                    28214   -0.031  -2.33 |   78627   -0.018  -1.29
50d SMA                                37793   +0.023   0.58 |  177159   -0.006  -1.20
200d SMA                               17328   -0.007  -0.73 |  153012   -0.016  -1.80
round number                           34184   +0.011   0.52 |   16388   +0.007   0.47
```
