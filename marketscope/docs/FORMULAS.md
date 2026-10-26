# MarketScope Technical Formulas & Calculation Rules

This document specifies the exact deterministic calculation models used in the MarketScope NSE Flow Terminal.

## 1. Fast & Slow Exponential Moving Averages (EMA)
- Fast EMA default period: 9 bars
- Slow EMA default period: 21 bars
- Smoothing factor:
  $$\alpha = \frac{2}{n + 1}$$
- Initialization:
  $$\text{EMA}_0 = \text{Close}_0$$
- Recurrence:
  $$\text{EMA}_t = \alpha \times \text{Close}_t + (1 - \alpha) \times \text{EMA}_{t-1}$$

## 2. Rolling-Window Relative Strength Index (RSI)
- Period: 14 changes
- Gains: $\sum \max(\Delta, 0)$
- Losses: $\sum \max(-\Delta, 0)$
$$\text{RSI} = 100 - \frac{100}{1 + \text{Gains} / \text{Losses}}$$
- If Losses = 0 and Gains > 0: RSI = 100
- If Losses = 0 and Gains = 0: RSI = 50

## 3. Volume-Weighted Average Price (VWAP)
- Resets at 09:15 IST each session day:
  $$\text{Typical Price} = \frac{\text{High} + \text{Low} + \text{Close}}{3}$$
  $$\text{VWAP} = \frac{\sum (\text{Typical Price} \times \text{Volume})}{\sum \text{Volume}}$$

## 4. Five-Bar Momentum Percentage
$$\text{Momentum} = 100 \times \left(\frac{\text{Close}_t}{\text{Close}_{t-5}} - 1\right)$$

## 5. Relative Volume (RVOL)
$$\text{RVOL} = \frac{\text{Volume}_t}{\text{mean}(\text{Volume}_{t-20 \dots t-1})}$$

## 6. Composite Directional Score (0 to 100)
Let $\text{clamp}(x) = \max(-1.0, \min(1.0, x))$:
- Trend contribution: $35 \times \text{clamp}\left(100 \times \left(\frac{\text{Fast EMA}}{\text{Slow EMA}} - 1\right) / 0.4\right)$
- Momentum contribution: $30 \times \text{clamp}(\text{Momentum} / 1.2)$
- VWAP contribution: $20 \times \text{clamp}\left(100 \times \left(\frac{\text{Close}}{\text{VWAP}} - 1\right) / 0.8\right)$
- RSI contribution: $15 \times \text{clamp}((\text{RSI} - 50) / 30)$

$$\text{Score} = \text{round}\left(50 + \frac{\text{Weighted Sum}}{2}\right)$$

### Classification Cutoffs:
- **BUY / Bullish:** Score $\ge 65$
- **SELL / Bearish:** Score $\le 35$
- **NEUTRAL:** $35 < \text{Score} < 65$

## 7. Order-Block Zone Heuristic
- Triggered on closed candles starting at index $\ge 6$.
- Bullish breakout: closes strictly above the highest high of prior 5 bars. Zone = $[ \text{Low}, \text{High} ]$ of the most recent prior down candle.
- Bearish breakout: closes strictly below the lowest low of prior 5 bars. Zone = $[ \text{Low}, \text{High} ]$ of the most recent prior up candle.
- Invalidation: Bullish zone invalidated if a subsequent bar closes below its low; bearish zone invalidated if a subsequent bar closes above its high.
- Up to 4 active surviving zones retained.
