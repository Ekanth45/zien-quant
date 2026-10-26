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

## 2. Welles Wilder Smoothed Relative Strength Index (RSI)
- Period: 14 bars
- Initialization: Seeded with the simple average of the first 14 changes:
  $$\text{avg\_gain}_0 = \frac{1}{14} \sum_{i=1}^{14} \max(\Delta_i, 0)$$
  $$\text{avg\_loss}_0 = \frac{1}{14} \sum_{i=1}^{14} \max(-\Delta_i, 0)$$
- Recurrence (Wilder's Smoothing):
  $$\text{avg\_gain}_t = \frac{\text{avg\_gain}_{t-1} \times 13 + \max(\Delta_t, 0)}{14}$$
  $$\text{avg\_loss}_t = \frac{\text{avg\_loss}_{t-1} \times 13 + \max(-\Delta_t, 0)}{14}$$
- Relative Strength & Index:
  $$\text{RS} = \frac{\text{avg\_gain}}{\text{avg\_loss}}$$
  $$\text{RSI} = 100 - \frac{100}{1 + \text{RS}}$$
- Edge Cases:
  - If $\text{avg\_loss} = 0$ and $\text{avg\_gain} > 0$: $\text{RSI} = 100$
  - If $\text{avg\_loss} = 0$ and $\text{avg\_gain} = 0$: $\text{RSI} = 50$

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

## 8. Average True Range (ATR) & Dynamic Targets
- True Range (TR):
  $$\text{TR}_t = \max(\text{High}_t - \text{Low}_t, |\text{High}_t - \text{Close}_{t-1}|, |\text{Low}_t - \text{Close}_{t-1}|)$$
- ATR (14-period Wilder smoothing):
  $$\text{ATR}_t = \frac{\text{ATR}_{t-1} \times 13 + \text{TR}_t}{14}$$
- Dynamic Breakout Targets:
  - Bullish Target 1: $\max(\text{Resistance}, \text{Price} + 1.5 \times \text{ATR})$
  - Bullish Target 2: $\text{Price} + 2.5 \times \text{ATR}$
  - Bearish Target 1: $\min(\text{Support}, \text{Price} - 1.5 \times \text{ATR})$
  - Bearish Target 2: $\text{Price} - 2.5 \times \text{ATR}$

## 9. Mandatory Risk-to-Reward (R:R) Gating & Setup Grading
- Risk-to-Reward Calculation:
  $$\text{R:R} = \frac{|\text{Target}_1 - \text{Price}|}{\max(0.1, |\text{Price} - \text{Stop Loss}|)}$$
- Mandatory Gate:
  $$\text{R:R} \ge 1.5$$
- Setups with $\text{R:R} < 1.5$ fail the execution hurdle and are demoted to Grade C (`RANGE BOUND / AVOID`).
- Grading Hierarchy:
  - **Grade A+**: $\text{R:R} \ge 2.2$ AND $RVOL \ge 1.5$ AND $|\text{Momentum}| > 1.2\%$ on closed confirming bar.
  - **Grade A**: $\text{R:R} \ge 1.8$ AND Score aligned with signal direction AND $RVOL \ge 1.0$.
  - **Grade B**: $\text{R:R} \ge 1.5$ with valid technical order block boundary.
  - **Grade C**: $\text{R:R} < 1.5$ or low-expectancy range bound structure.
