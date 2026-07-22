# SniperSight4

an intelligent market-structure platform that objectively maps market behavior, discovers high-probability trading opportunities, rigorously validates strategies, and automates disciplined trade execution using explainable AI and institutio

## Vision
Right now i have to scan markets manually for good trade setups.  I need to place trades at times that make sense.  when Im at work I can't place any trades or do any research.  I want the scanner to find the setups for me.  the high probability ones.  it can notify me and I can have it place the trade for me in one click.  I can also set up the bot to autonomously buy and sell for me.  just as if I were to place the trades manually.  This takes the emotions out of the trades and sticks to a system
• Name the markets and instruments: e.g. 'US equities and options' or 'crypto spot on Binance' — the scanner, broker API, and market hours all depend on this.
• Define 'high probability setup' concretely: which patterns or indicators (e.g. breakout above 20-day high with volume spike, RSI divergence), so the scanner has testable rules.
• State which broker or exchange the bot will place trades through, and confirm it has an API that supports one-click and autonomous order placement.
• Specify how notifications reach you at work: push notification, SMS, or Telegram — and that the one-click trade must work from a phone.
• Add risk controls to the 'why now': max position size, stop-loss per trade, and a daily loss limit that halts the bot, since it will trade unattended.
• Add risk controls to the 'why now': max position size, stop-loss per trade, and a daily loss limit that halts the bot, since it will trade unattended.
• Say whether autonomous mode starts paper-trading first, and what track record (e.g. 30 days of logged signals) is required before real money is enabled.
• Mention timeframe: is this scanning intraday setups every few minutes, or end-of-day swing setups once daily? This changes the architecture a lot.
• Clarify 'sticks to a system': the exact entry, exit, and sizing rules should be written down and versioned so backtests match what the bot actually does.

• Core thesis (lead with this): SniperSight4 turns discretionary market-structure reading into an objective, testable process. A deterministic, rules-based engine maps structure (swings, ranges, liquidity levels) — same chart in, same map out, every time. On top of that map, it flags setups matching defined playbooks and scores each signal with a plain-language, explainable rationale. Strategy validation (backtest → paper) is the trust engine; automated live execution is the endgame, unlocked only for strategies that survive validation. v1 promise: 'see the structure, trust the signal' — not 'let the bot trade for you.'

## Scope
• V1 is a deterministic market-intelligence engine: market-structure analysis, setup detection, strategy backtesting, and paper trading with explainable trade reasoning. Markets: cryptocurrency and stocks only. Non-goals for V1: (1) No live/automated trade execution — paper trades only, to validate strategy performance and risk management before any real capital is used. (2) No social or copy trading — leaderboards and strategy sharing deferred until the core engine is proven. (3) No options or other derivatives. (4) No asset classes beyond crypto and equities (no forex, futures).

## Design
Dark surfaces with a cyan accent; technical type; dense spacing; calm tone.
