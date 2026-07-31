/* Learn surface + first-run orientation.

   This file exists because of one sentence from the operator: "there's lingo I
   have no idea what it means, features I don't know what they are, zero
   explanation." glossary.js answers the first part a word at a time. This
   answers the second part: what the engine is actually doing, and WHY that
   works, for someone who has never traded.

   Structure, ported from the previous project's lessons system:
       CORE MECHANIC -> WHY IT WORKS -> COMMON MISTAKES -> interactive widget
   Same four sections on every chapter. The consistency is the point: once you
   have read one chapter you know the shape of all of them.

   THE COPY IS WRITTEN AGAINST THIS PROJECT'S ENGINES, NOT THE OLD ONE'S.
   The source lessons described a different engine — other mode names, letter
   grades, ATR multipliers that do not exist here. Every rule below was read out
   of the file named in that chapter's SOURCE line, and each chapter states the
   algo version it was written against. If a version here is behind the one in
   the status bar, the chapter is stale, and it says so rather than quietly
   describing a rule that no longer exists.

   Two mount points, and they are the only contract with the rest of the shell:
       #learnRoot   — the Learn surface
       #orientRoot  — first-run orientation, top of Command
   This module edits nothing else and boots itself.

   No framework, no build step, no CDN. Widgets are hand-written inline SVG.
   Loud-fallback rule: a missing mount, a failed stylesheet or a widget that
   throws all render something visible. Nothing here is allowed to leave a blank
   rectangle where an explanation should be. */
(function (root) {
  'use strict';

  /* ═══════════════════════════════════════════════════════════════════════
     1. tiny helpers
     ═══════════════════════════════════════════════════════════════════════ */

  const HTML_ESC = { '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' };
  const esc = s => String(s).replace(/[<>&"]/g, c => HTML_ESC[c]);
  /* SVG coordinates are rounded to 2dp. Full float precision produces markup
     that is three times longer and pixel-identical. */
  const f = n => Math.round(n * 100) / 100;
  const nf = (n, d) => Number(n).toLocaleString(undefined,
    { minimumFractionDigits: d == null ? 0 : d, maximumFractionDigits: d == null ? 0 : d });

  /* price -> y. Built once per drawing so every element shares one scale. */
  function yScale(lo, hi, top, bot) {
    const span = (hi - lo) || 1;
    return p => top + ((hi - p) / span) * (bot - top);
  }

  function T(x, y, s, o) {
    o = o || {};
    return '<text x="' + f(x) + '" y="' + f(y) + '" fill="' + (o.fill || 'var(--fg-3)') +
      '" font-size="' + (o.size || 10) + '"' +
      (o.anchor ? ' text-anchor="' + o.anchor + '"' : '') +
      (o.ls ? ' letter-spacing="' + o.ls + '"' : '') +
      (o.weight ? ' font-weight="' + o.weight + '"' : '') +
      '>' + esc(s) + '</text>';
  }

  function line(x1, y1, x2, y2, o) {
    o = o || {};
    return '<line x1="' + f(x1) + '" y1="' + f(y1) + '" x2="' + f(x2) + '" y2="' + f(y2) +
      '" stroke="' + (o.stroke || 'var(--border)') + '" stroke-width="' + (o.w || 1) + '"' +
      (o.dash ? ' stroke-dasharray="' + o.dash + '"' : '') +
      (o.op != null ? ' opacity="' + o.op + '"' : '') + '/>';
  }

  function rect(x, y, w, h, o) {
    o = o || {};
    return '<rect x="' + f(x) + '" y="' + f(y) + '" width="' + f(Math.max(w, 0)) +
      '" height="' + f(Math.max(h, 0)) + '" fill="' + (o.fill || 'none') + '"' +
      (o.stroke ? ' stroke="' + o.stroke + '" stroke-width="' + (o.w || 1) + '"' : '') +
      (o.r ? ' rx="' + o.r + '"' : '') +
      (o.dash ? ' stroke-dasharray="' + o.dash + '"' : '') +
      (o.op != null ? ' opacity="' + o.op + '"' : '') + '/>';
  }

  /* One candle. `edge` outlines the bar in a highlight colour — used to say
     "this is the bar the rule is about" without changing its body colour, which
     still has to mean up or down. */
  function candle(cx, w, b, y, o) {
    o = o || {};
    const col = o.color || (b.c >= b.o ? 'var(--green-soft)' : 'var(--red-2)');
    const yo = y(b.o), yc = y(b.c);
    const top = Math.min(yo, yc), h = Math.max(Math.abs(yo - yc), 1.6);
    const op = o.op == null ? 1 : o.op;
    return line(cx, y(b.h), cx, y(b.l), { stroke: o.edge || col, w: o.edge ? 1.4 : 1, op: op }) +
      '<rect x="' + f(cx - w / 2) + '" y="' + f(top) + '" width="' + f(w) + '" height="' + f(h) +
      '" fill="' + col + '" opacity="' + op + '"' +
      (o.edge ? ' stroke="' + o.edge + '" stroke-width="1.4"' : '') + '/>';
  }

  function svgRoot(w, h, body, label) {
    return '<svg viewBox="0 0 ' + w + ' ' + h + '" preserveAspectRatio="xMidYMid meet"' +
      ' role="img" aria-label="' + esc(label || '') + '">' + body + '</svg>';
  }

  /* A verdict strip. Every widget that states an engine verdict renders it the
     same way, so the shape of an answer is recognisable across chapters. */
  function verdict(x, y, w, txt, col) {
    return rect(x, y, w, 26, { fill: 'rgba(0,0,0,.45)', stroke: col, r: 5, op: 1 }) +
      T(x + 9, y + 17, txt, { fill: col, size: 10.5, ls: '.10em' });
  }

  const C = {
    up: 'var(--green-soft)', down: 'var(--red-2)',
    green: 'var(--green)', red: 'var(--red)', amber: 'var(--amber)',
    cyan: 'var(--cyan)', purple: 'var(--purple)', blue: 'var(--blue)',
    fg: 'var(--fg)', fg2: 'var(--fg-2)', fg3: 'var(--fg-3)', fg4: 'var(--fg-4)',
    line: 'var(--border-soft)'
  };

  /* ═══════════════════════════════════════════════════════════════════════
     2. the engine's regime classifier, in JavaScript

     A literal port of `_classify` in engine/regime.py. It lives here rather
     than inside the widget so the test can check the port against the same
     truth table the Python is written from — a diagram that disagreed with the
     engine would be worse than no diagram.
     ═══════════════════════════════════════════════════════════════════════ */

  function classifyRegime(lastBreak, lastHigh, lastLow) {
    if (!lastBreak) return 'RANGE';
    if (lastBreak.event === 'CHOCH') return 'TRANSITION';
    const d = lastBreak.direction;
    if (d === 'BULL') {
      if (lastHigh === 'HH' && lastLow === 'HL') return 'BULL_TREND';
      if (lastHigh === 'HH' || lastLow === 'HL') return 'WEAKENING_BULL';
    }
    if (d === 'BEAR') {
      if (lastHigh === 'LH' && lastLow === 'LL') return 'BEAR_TREND';
      if (lastHigh === 'LH' || lastLow === 'LL') return 'WEAKENING_BEAR';
    }
    return 'RANGE';
  }

  /* engine/zones.py — formation_quality / freshness / strength, ported exactly
     so the lifecycle widget shows the numbers the engine would record. */
  const TF_WEIGHT = { '1W': 20, '1D': 15, '4H': 10, '1H': 5, '15m': 5 };
  const zoneQuality = (cluster, tf) =>
    Math.min(100, 50 + Math.min(30, cluster * 10) + (TF_WEIGHT[tf] || 5));
  const zoneFreshness = (episodes, ageBars, broken) =>
    broken ? 0 : Math.max(0, 100 - episodes * 25 - Math.min(25, Math.floor(ageBars / 100)));
  const zoneStrength = (q, fresh) => Math.floor((q + fresh) / 2);

  /* ═══════════════════════════════════════════════════════════════════════
     3. widgets

     Every widget is a pure spec: data plus `svg(step, param)` returning markup.
     Nothing touches the DOM, which is why this file loads under node and why
     the widgets are testable at all. Mounting is a separate, dumb step.

       { id, title, caption, layout?, param?, steps: [{label, note, param?}],
         svg(step, param) -> '<svg …>' }
     ═══════════════════════════════════════════════════════════════════════ */

  const WIDGETS = {};

  /* ─────────── 3.1 swing tiers ─────────── */
  /* 27 fractal pivots. `k` is how far each survives:
       0 micro only · 1 local · 2 survived the first recursion · 3 the second.
     The sequence is not decorative — run engine/swings.py's promote_tier over
     the k>=1 subset and exactly the k>=2 pivots survive; run it again over
     those and only the 150 high does. */
  const SWING_PTS = [
    { t: 'L', p: 100, k: 1 }, { t: 'H', p: 106, k: 0 }, { t: 'L', p: 103, k: 0 },
    { t: 'H', p: 112, k: 1 }, { t: 'L', p: 104, k: 1 }, { t: 'H', p: 109, k: 0 },
    { t: 'L', p: 106, k: 0 }, { t: 'H', p: 124, k: 2 }, { t: 'L', p: 110, k: 1 },
    { t: 'H', p: 118, k: 1 }, { t: 'L', p: 114, k: 0 }, { t: 'H', p: 116, k: 0 },
    { t: 'L', p: 108, k: 2 }, { t: 'H', p: 121, k: 0 }, { t: 'L', p: 118, k: 0 },
    { t: 'H', p: 150, k: 3 }, { t: 'L', p: 120, k: 1 }, { t: 'H', p: 128, k: 1 },
    { t: 'L', p: 122, k: 0 }, { t: 'H', p: 125, k: 0 }, { t: 'L', p: 112, k: 2 },
    { t: 'H', p: 134, k: 1 }, { t: 'L', p: 124, k: 1 }, { t: 'H', p: 140, k: 2 },
    { t: 'L', p: 118, k: 2 }, { t: 'H', p: 132, k: 1 }, { t: 'L', p: 122, k: 1 }
  ];
  const SWING_SCORE = [
    ['margin over neighbours', 18.00, 18, '6.4% — capped at 5%'],
    ['reversal size', 14.72, 24, '9.2 ATR of the 15 needed for full marks'],
    ['held before price traded through', 14.00, 14, '90+ candles'],
    ['volume at the turn', 8.70, 12, '3.1x average, log-scaled'],
    ['liquidity harvested', 8.00, 8, 'took the prior high, sits in a cluster'],
    ['structure it caused', 26.00, 26, '2 breaks'],
    ['survived the second recursion', 12.00, 12, 'dominant']
  ];

  WIDGETS.swingTiers = {
    id: 'swingTiers',
    title: 'Four passes and a score',
    caption: '27 fractals in · one dominant pivot out',
    steps: [
      {
        label: 'EVERY FRACTAL', note: 'Twenty-seven five-candle fractals. A bar is a swing ' +
          'high when its high beats the two bars either side of it, strictly. At this stage ' +
          'almost every wiggle qualifies, which is exactly why the raw fractal is useless on ' +
          'its own.'
      },
      {
        label: '0.75 ATR', note: 'Seventeen left. A fractal is promoted to <b>LOCAL</b> only ' +
          'if price reversed away from it by at least three quarters of an average bar before ' +
          'the next opposite fractal. Anything smaller is inside the noise the market makes ' +
          'anyway.'
      },
      {
        label: 'BEAT THE NEIGHBOURS', note: 'Six left. Collapse the survivors into a strictly ' +
          'alternating high / low list, then keep the ones more extreme than the same-type ' +
          'pivot two places to the left <b>and</b> two places to the right.'
      },
      {
        label: 'AGAIN', note: 'One left. The same test, run on the survivors. Nothing about ' +
          'this step is timeframe-specific, which is the whole reason it is a recursion and ' +
          'not a lookback: it scales itself to whatever chart it runs on with no extra ' +
          'parameter.'
      },
      {
        label: 'THEN THE SCORE', note: 'Surviving is not the tier. A score out of 114 decides ' +
          'it: <b>55 or more is MAJOR, 30 or more is INTERMEDIATE</b>, and below 30 the pivot ' +
          'stays a local wiggle with no higher-tier fact written at all. Note which two ' +
          'components are heaviest.'
      }
    ],
    svg: function (step) {
      const W = 640, H = 300, padX = 34, padT = 26, padB = 34;
      const s = clampStep(this, step);
      if (s === 4) return this._score(W, H);
      const y = yScale(96, 154, padT, H - padB);
      const x = i => padX + (i / (SWING_PTS.length - 1)) * (W - padX * 2);
      let b = '';
      b += line(padX, y(150), W - padX, y(150), { stroke: C.line, dash: '3 5', op: .35 });
      b += line(padX, y(100), W - padX, y(100), { stroke: C.line, dash: '3 5', op: .35 });
      /* the price path stays fully drawn at every step — the pivots dim, the
         market does not disappear */
      b += '<polyline points="' + SWING_PTS.map((pt, i) => f(x(i)) + ',' + f(y(pt.p))).join(' ') +
        '" fill="none" stroke="var(--fg-4)" stroke-width="1" opacity=".55"/>';
      let live = 0;
      SWING_PTS.forEach((pt, i) => {
        const on = pt.k >= s;
        if (on) live++;
        const col = pt.k >= 3 ? C.purple : pt.k >= 2 ? C.cyan : pt.k >= 1 ? C.fg2 : C.fg4;
        b += '<circle cx="' + f(x(i)) + '" cy="' + f(y(pt.p)) + '" r="' + (on ? (pt.k >= 2 ? 5 : 3.4) : 2) +
          '" fill="' + (on ? col : 'var(--fg-4)') + '" opacity="' + (on ? 1 : .22) + '"/>';
        if (on && pt.k >= 2) {
          b += T(x(i), pt.t === 'H' ? y(pt.p) - 10 : y(pt.p) + 15, String(pt.p),
            { fill: col, size: 9.5, anchor: 'middle' });
        }
      });
      const names = ['MICRO fractals', 'LOCAL swings', 'first-recursion survivors',
        'second-recursion survivor'];
      b += T(padX, 16, live + ' ' + names[s], { fill: C.fg2, size: 11, ls: '.08em' });
      b += T(W - padX, 16, 'engine/swings.py', { fill: C.fg4, size: 9, anchor: 'end', ls: '.10em' });
      b += T(padX, H - 10, s === 0 ? 'strict 2 left / 2 right — ties produce nothing'
        : s === 1 ? 'reversal >= 0.75 x ATR14, measured at the swing\'s own bar'
          : s === 2 ? 'more extreme than the same-type pivot at k-2 and k+2'
            : 'the same test, applied to the survivors',
        { fill: C.fg4, size: 9.5, ls: '.08em' });
      return svgRoot(W, H, b, 'swing tier filtering, step ' + (s + 1));
    },
    _score: function (W, H) {
      let b = '', yy = 34;
      b += T(34, 18, 'MAJOR SCORE — the pivot at 150', { fill: C.purple, size: 11, ls: '.10em' });
      b += T(W - 34, 18, 'engine/swings.py', { fill: C.fg4, size: 9, anchor: 'end', ls: '.10em' });
      const barX = 250, barW = 250;
      let total = 0;
      SWING_SCORE.forEach(row => {
        total += row[1];
        const frac = row[1] / row[2];
        b += T(34, yy + 9, row[0], { fill: C.fg3, size: 10 });
        b += rect(barX, yy, barW * (row[2] / 26), 12, { fill: 'rgba(255,255,255,.05)', r: 3 });
        b += rect(barX, yy, barW * (row[2] / 26) * frac, 12,
          { fill: row[2] >= 24 ? C.purple : C.cyan, r: 3, op: .85 });
        b += T(barX + barW + 12, yy + 9, row[1].toFixed(2) + ' / ' + row[2],
          { fill: C.fg2, size: 10, anchor: 'end' });
        b += T(34, yy + 22, row[3], { fill: C.fg4, size: 8.5 });
        yy += 32;
      });
      b += line(34, yy + 2, W - 34, yy + 2, { stroke: C.line });
      b += T(34, yy + 20, 'TOTAL ' + total.toFixed(2) + '  ·  MAJOR needs 55  ·  INTERMEDIATE needs 30',
        { fill: C.fg, size: 11, ls: '.08em' });
      return svgRoot(W, Math.max(H, yy + 34), b, 'major score breakdown');
    }
  };

  /* ─────────── 3.2 wick vs close ─────────── */
  /* The most valuable widget in the source project, rebuilt against this
     engine's actual break rule: close beyond the level by more than
     max(1 tick, 0.05 x ATR). Both bars always wick through. Only the close
     differs — and at a small enough wick, even the closing bar fails. */
  const WVC = { level: 105, atr: 4.0, tick: 0.01 };
  WVC.tol = Math.max(WVC.tick, 0.05 * WVC.atr);   // 0.20

  WIDGETS.wickVsClose = {
    id: 'wickVsClose',
    title: 'Wick versus close',
    caption: 'same wick · opposite verdict',
    param: { label: 'WICK DEPTH', min: 0.2, max: 6, step: 0.1, value: 3, unit: 'pts' },
    steps: [
      {
        label: 'THE LEVEL', note: 'A confirmed swing high at 105. The engine will not treat it ' +
          'as broken until a candle <b>closes</b> beyond it by more than ' +
          '<code>max(1 tick, 0.05 x ATR)</code> — with ATR at 4.00 that is 0.20, drawn as the ' +
          'thin band above the line.'
      },
      {
        label: 'SWEEP', note: 'This bar traded above 105 and closed back underneath it. The ' +
          'high above the level was reached, the orders resting there were filled, and price ' +
          'refused to stay. <b>No break.</b> The engine records this shape against a liquidity ' +
          'pool as a SWEEP, outcome REJECTED.'
      },
      {
        label: 'BREAK', note: 'Same high, to the pixel. This bar closed beyond the level and ' +
          'past the tolerance, so it is a real break — a BOS if it went with the current ' +
          'structural direction, a CHoCH if it went against it. Now drag the wick slider down ' +
          'below about 0.4 and watch this same bar stop counting.'
      },
      {
        label: 'SIDE BY SIDE', note: 'Two bars with identical highs and opposite meanings. ' +
          'Most retail structure indicators would mark both as a break of that high. This one ' +
          'marks neither until the close says so, and that single distinction is the difference ' +
          'between buying a breakout and being the liquidity that funded someone else\'s exit.'
      }
    ],
    svg: function (step, param) {
      const s = clampStep(this, step);
      const wick = param == null ? this.param.value : Number(param);
      const W = 640, H = 320, padX = 40, padT = 30, padB = 74;
      const lv = WVC.level, tol = WVC.tol;
      const y = yScale(101.5, Math.max(112, lv + wick + 1.5), padT, H - padB);
      const bw = (W - padX * 2) / 9;
      const cx = i => padX + (i + 0.5) * bw;
      /* five context bars climbing toward the level */
      const prior = [];
      for (let i = 0; i < 5; i++) {
        const o = 102 + 0.55 * i, c = 102 + 0.55 * (i + 1);
        prior.push({ o: o, c: c, h: Math.max(o, c) + 0.35, l: Math.min(o, c) - 0.35 });
      }
      const sweepBar = { o: 103.4, h: lv + wick, l: 103.0, c: 104.6 };
      const bosBar = { o: 103.4, h: lv + wick, l: 103.0, c: lv + wick * 0.55 };
      /* the verdict is COMPUTED, never asserted — the widget cannot drift from
         the rule it is teaching */
      const broke = bar => bar.c > lv + tol;

      let b = '';
      b += rect(padX, y(lv + tol), W - padX * 2, y(lv) - y(lv + tol),
        { fill: 'rgba(192,132,252,.16)' });
      b += line(padX, y(lv), W - padX, y(lv), { stroke: C.purple, w: 1.5, dash: '6 4' });
      b += T(padX + 4, y(lv) - 7, 'PRIOR SWING HIGH  105.00', { fill: C.purple, size: 9.5, ls: '.10em' });
      b += T(W - padX - 4, y(lv + tol) - 5, 'break needs a close above ' + (lv + tol).toFixed(2),
        { fill: C.purple, size: 9, anchor: 'end' });
      prior.forEach((bar, i) => { b += candle(cx(i), bw * 0.5, bar, y, { op: .6 }); });

      const showSweep = s === 1 || s === 3;
      const showBos = s === 2 || s === 3;
      const sx = s === 3 ? cx(5.6) : cx(6);
      const bx = s === 3 ? cx(7.1) : cx(6);
      if (showSweep) {
        b += candle(sx, bw * 0.58, sweepBar, y, { edge: C.amber });
        b += T(sx, y(sweepBar.h) - 8, 'SWEEP', { fill: C.amber, size: 10, anchor: 'middle', ls: '.14em' });
      }
      if (showBos) {
        b += candle(bx, bw * 0.58, bosBar, y, { edge: broke(bosBar) ? C.cyan : C.amber });
        b += T(bx, y(bosBar.h) - 8, broke(bosBar) ? 'BREAK' : 'NOT YET',
          { fill: broke(bosBar) ? C.cyan : C.amber, size: 10, anchor: 'middle', ls: '.14em' });
      }

      const vy = H - 62;
      if (s === 0) {
        b += verdict(padX, vy, W - padX * 2,
          'wick depth ' + wick.toFixed(1) + ' pts  ·  tolerance ' + tol.toFixed(2) +
          '  ·  nothing has been tested yet', C.fg3);
      } else if (s === 3) {
        b += verdict(padX, vy, (W - padX * 2) / 2 - 6,
          'SWEEP  close ' + sweepBar.c.toFixed(2) + '  ·  no break', C.amber);
        b += verdict(padX + (W - padX * 2) / 2 + 6, vy, (W - padX * 2) / 2 - 6,
          (broke(bosBar) ? 'BREAK  close ' : 'NO BREAK  close ') + bosBar.c.toFixed(2) +
          (broke(bosBar) ? '' : ' — inside tolerance'), broke(bosBar) ? C.cyan : C.amber);
      } else {
        const bar = s === 1 ? sweepBar : bosBar;
        const ok = broke(bar);
        b += verdict(padX, vy, W - padX * 2,
          'high ' + bar.h.toFixed(2) + ' > 105.00 yes   ·   close ' + bar.c.toFixed(2) +
          (ok ? ' > 105.20 yes  ->  BREAK' : ' > 105.20 no  ->  NO BREAK'),
          ok ? C.cyan : C.amber);
      }
      b += T(padX, H - 22, 'engine/structure.py — a closed candle\'s close beyond the level by ' +
        'max(1 tick, 0.05 x ATR). Wicks never break.', { fill: C.fg4, size: 9.5 });
      return svgRoot(W, H, b, 'wick versus close, step ' + (s + 1));
    }
  };

  /* ─────────── 3.3 zone lifecycle ─────────── */
  /* Demand zone anchored at a swing low of 100 with ATR 8, so the band is
     0.25 x 8 = 2.00 wide: [100, 102]. Break tolerance 0.05 x 8 = 0.40. */
  const ZL = { bottom: 100, top: 102, tol: 0.40, tf: '4H', cluster: 1 };
  ZL.quality = zoneQuality(ZL.cluster, ZL.tf);        // 70
  /* Bars are explicit rather than generated: each one has to sit in an exact
     relationship to the band for the episode arithmetic to be honest. */
  const ZL_BARS = [
    { o: 113, h: 114, l: 111, c: 112 }, { o: 112, h: 112.5, l: 107, c: 108 },
    { o: 108, h: 109, l: 104, c: 105 },
    { o: 105, h: 105.4, l: 101.2, c: 104.0 },                        // 3  episode 1
    { o: 104, h: 107, l: 103.6, c: 106.5 }, { o: 106.5, h: 109.5, l: 106, c: 109 },
    { o: 109, h: 109.4, l: 106.6, c: 107 }, { o: 107, h: 107.2, l: 104.4, c: 105 },
    { o: 105, h: 105.2, l: 100.9, c: 101.5 },                        // 8  episode 2
    { o: 101.5, h: 102.4, l: 100.4, c: 101.8 },                      // 9  same episode
    { o: 101.8, h: 103.0, l: 100.6, c: 102.4 },                      // 10 same episode
    { o: 102.4, h: 105.6, l: 103.0, c: 105.2 },                      // 11 back outside
    { o: 105.2, h: 107.8, l: 105, c: 107.4 }, { o: 107.4, h: 107.6, l: 105.2, c: 105.6 },
    { o: 105.6, h: 105.8, l: 103.4, c: 103.8 },
    { o: 103.8, h: 104, l: 100.2, c: 102.6 },                        // 15 episode 3
    { o: 102.6, h: 104.6, l: 102.4, c: 104.2 }, { o: 104.2, h: 104.4, l: 102.2, c: 102.6 },
    { o: 102.6, h: 102.8, l: 100.8, c: 101.2 },                      // 18 still inside
    { o: 101.2, h: 101.4, l: 98.6, c: 99.2 }                         // 19 close < 99.60
  ];
  const ZL_STEPS = [
    { upto: 3, ep: 0, age: 0, state: 'FRESH', broken: false },
    { upto: 4, ep: 1, age: 3, state: 'TOUCHED', broken: false },
    { upto: 11, ep: 2, age: 10, state: 'TESTED', broken: false },
    { upto: 16, ep: 3, age: 15, state: 'WEAKENED', broken: false },
    { upto: 20, ep: 3, age: 19, state: 'BROKEN', broken: true }
  ];

  WIDGETS.zoneLifecycle = {
    id: 'zoneLifecycle',
    title: 'Zone lifecycle',
    caption: 'FRESH -> TOUCHED -> TESTED -> WEAKENED -> BROKEN',
    steps: [
      {
        label: 'FRESH', note: 'Created the moment its anchor swing confirmed, never touched. ' +
          'This is the best state the zone will ever be in. Strength is quality and freshness ' +
          'averaged: quality 70 (50 base, 10 for one clustered neighbour, 10 for the 4H ' +
          'timeframe) and freshness 100.'
      },
      {
        label: 'TOUCHED', note: 'Price entered the band and left. One <b>episode</b>. Freshness ' +
          'drops 25 points and never comes back — the resting orders that made this a zone have ' +
          'been partly consumed. Note that this bar only wicked in: a wick into a zone is the ' +
          'zone working, not the zone failing.'
      },
      {
        label: 'TESTED', note: 'Second episode — and read the bars carefully. Price spent ' +
          '<b>three consecutive bars</b> inside the band and the counter moved by one. An ' +
          'episode is an entry from outside, not a bar. What consumes a zone is a fresh ' +
          'approach, not time spent sitting in it.'
      },
      {
        label: 'WEAKENED', note: 'Third episode and beyond. Freshness is down to 25 of 100. ' +
          'The common instinct is that a level tested three times is proven; the arithmetic ' +
          'here says the opposite, and the arithmetic is describing an order book being ' +
          'gradually emptied.'
      },
      {
        label: 'BROKEN', note: 'A candle <b>closed</b> below the far edge by more than ' +
          '<code>max(1 tick, 0.05 x ATR)</code> — the same close-not-wick rule as structure. ' +
          'Freshness goes to zero, but strength does not: formation quality is immutable, so ' +
          'the record still says this was a decent zone that got used up.'
      }
    ],
    svg: function (step) {
      const s = clampStep(this, step);
      const st = ZL_STEPS[s];
      const W = 640, H = 320, padX = 40, padT = 28, padB = 76;
      const y = yScale(97.5, 115, padT, H - padB);
      const bw = (W - padX * 2) / ZL_BARS.length;
      const cx = i => padX + (i + 0.5) * bw;
      const fresh = zoneFreshness(st.ep, st.age, st.broken);
      const strength = zoneStrength(ZL.quality, fresh);

      let b = '';
      b += rect(padX, y(ZL.top), W - padX * 2, y(ZL.bottom) - y(ZL.top),
        { fill: st.broken ? 'rgba(248,113,113,.10)' : 'rgba(0,255,170,.10)' });
      b += line(padX, y(ZL.top), W - padX, y(ZL.top),
        { stroke: st.broken ? C.red : C.green, w: 1, op: .8 });
      b += line(padX, y(ZL.bottom), W - padX, y(ZL.bottom),
        { stroke: st.broken ? C.red : C.green, w: 1, op: .8 });
      b += line(padX, y(ZL.bottom - ZL.tol), W - padX, y(ZL.bottom - ZL.tol),
        { stroke: C.fg4, dash: '2 4', op: .7 });
      b += T(padX + 4, y(ZL.bottom) + 13, 'DEMAND  100.00 - 102.00   (0.25 x ATR wide)',
        { fill: st.broken ? C.red : C.green, size: 9.5, ls: '.08em' });

      ZL_BARS.forEach((bar, i) => {
        if (i >= st.upto) return;
        const isBreak = st.broken && i === 19;
        b += candle(cx(i), bw * 0.5, bar, y,
          { op: i >= st.upto - 1 ? 1 : .8, edge: isBreak ? C.red : null });
      });
      /* the three-bars-one-episode point needs to be pointed AT, not narrated */
      if (s === 2) {
        const x0 = cx(8) - bw * 0.4, x1 = cx(10) + bw * 0.4, yy = y(99.4);
        b += line(x0, yy, x1, yy, { stroke: C.amber, w: 1.2 });
        b += line(x0, yy - 4, x0, yy + 4, { stroke: C.amber, w: 1.2 });
        b += line(x1, yy - 4, x1, yy + 4, { stroke: C.amber, w: 1.2 });
        b += T((x0 + x1) / 2, yy + 15, '3 bars inside = 1 episode',
          { fill: C.amber, size: 9, anchor: 'middle' });
      }

      const col = st.broken ? C.red : s === 0 ? C.green : s >= 3 ? C.amber : C.fg2;
      b += verdict(padX, H - 66, W - padX * 2,
        st.state + '   ·   episodes ' + st.ep + '   ·   quality ' + ZL.quality +
        ' (fixed at creation)   ·   freshness ' + fresh + '   ·   strength ' + strength, col);
      const barX = padX, barW = W - padX * 2;
      b += rect(barX, H - 34, barW, 8, { fill: 'rgba(255,255,255,.05)', r: 4 });
      b += rect(barX, H - 34, barW * (strength / 100), 8, { fill: col, r: 4, op: .85 });
      b += T(padX, H - 12, 'strength = (quality + freshness) / 2 — evidence for comparing two ' +
        'zones, never a probability', { fill: C.fg4, size: 9.5 });
      return svgRoot(W, H, b, 'zone lifecycle, ' + st.state);
    }
  };

  /* ─────────── 3.4 sweep vs breakout ─────────── */
  /* An equal-highs pool: two INTERMEDIATE highs at 110.00 and 109.45. With ATR
     8 the equality tolerance is 0.10 x 8 = 0.80 and they are 0.55 apart, so the
     engine clusters them. Pool level = the extreme = 110.00. */
  const SB = { level: 110, tol: 0.40 };
  const SB_PRIOR = [
    { o: 104, h: 105.4, l: 103.6, c: 105.2 }, { o: 105.2, h: 108.2, l: 105, c: 108 },
    { o: 108, h: 110.0, l: 107.6, c: 108.6 },                       // equal high #1
    { o: 108.6, h: 108.8, l: 105.8, c: 106.2 }, { o: 106.2, h: 106.6, l: 104.4, c: 105 },
    { o: 105, h: 107.4, l: 104.8, c: 107.2 },
    { o: 107.2, h: 109.45, l: 107, c: 108.2 },                      // equal high #2
    { o: 108.2, h: 108.4, l: 106.6, c: 107 }, { o: 107, h: 108.6, l: 106.8, c: 108.4 }
  ];
  const SB_TRIG = {
    sweep: { o: 108.2, h: 112.4, l: 108.0, c: 109.6 },
    broken: { o: 108.2, h: 112.4, l: 108.0, c: 110.9 }
  };
  const SB_AFTER = {
    sweep: [{ o: 109.6, h: 109.8, l: 107, c: 107.4 }, { o: 107.4, h: 107.6, l: 104.6, c: 105 },
    { o: 105, h: 105.4, l: 102.4, c: 102.8 }, { o: 102.8, h: 103.4, l: 100.2, c: 100.6 }],
    broken: [{ o: 110.9, h: 112.6, l: 110.4, c: 112.2 }, { o: 112.2, h: 114.4, l: 111.8, c: 114 },
    { o: 114, h: 115.2, l: 113, c: 113.6 }, { o: 113.6, h: 116.8, l: 113.4, c: 116.4 }]
  };

  WIDGETS.sweepVsBreakout = {
    id: 'sweepVsBreakout',
    title: 'Sweep versus breakout',
    caption: 'identical setup · two resolutions',
    layout: 'twin',
    steps: [
      {
        label: 'THE POOL', note: 'Two swing highs at 110.00 and 109.45 — within ' +
          '<code>0.10 x ATR</code> of each other, so the engine treats them as the same price ' +
          'and builds one pool at 110.00. Two generations of traders have now parked stop-loss ' +
          'and breakout orders in the same place.'
      },
      {
        label: 'THE TRIGGER', note: 'One bar, drawn twice. Both reach 112.40, both take every ' +
          'order resting above 110.00. Up to this instant the two charts are identical and ' +
          'nothing on screen can tell you which one you are in.'
      },
      { label: '+1 BAR', note: 'The closes have already separated them. The left bar closed at ' +
          '109.60 — back inside the pool, so <b>SWEEP, outcome REJECTED</b>. The right closed ' +
          'at 110.90, past 110.00 plus the 0.40 tolerance, so <b>BROKEN</b> and the pool is ' +
          'consumed.' },
      { label: '+2 BARS', note: 'The sweep side is unwinding. This is the shape that gives the ' +
          'chapter its mechanism: someone needed to sell size, the only buyers large enough ' +
          'were the stops above the highs, so price went up to meet them and then had nothing ' +
          'holding it there.' },
      { label: '+3 BARS', note: 'Note what is NOT being claimed. The engine does not predict ' +
          'which resolution happens. It refuses to call the left one a break, which is a much ' +
          'smaller and much more defensible claim.' },
      { label: '+4 BARS', note: 'Four bars later they are twenty points apart, and the only ' +
          'thing that ever differed was where one candle closed.' }
    ],
    svg: function (step) {
      const s = clampStep(this, step);
      const nAfter = Math.max(0, s - 2);
      return this._panel('SWEEP', 'sweep', s, nAfter, C.amber) +
        this._panel('BREAKOUT', 'broken', s, nAfter, C.cyan);
    },
    _panel: function (title, kind, s, nAfter, col) {
      const W = 320, H = 260, padX = 26, padT = 30, padB = 44;
      const bars = SB_PRIOR.concat(s >= 1 ? [SB_TRIG[kind]] : [])
        .concat(SB_AFTER[kind].slice(0, nAfter));
      const lo = Math.min.apply(null, bars.map(b => b.l).concat([99.6]));
      const hi = Math.max.apply(null, bars.map(b => b.h).concat([113]));
      const y = yScale(lo - 1, hi + 1, padT, H - padB);
      const slots = SB_PRIOR.length + 1 + SB_AFTER[kind].length;
      const bw = (W - padX * 2) / slots;
      const cx = i => padX + (i + 0.5) * bw;
      let b = '';
      b += T(padX, 15, title, { fill: col, size: 10, ls: '.20em' });
      b += line(padX, y(SB.level), W - padX, y(SB.level), { stroke: C.purple, dash: '4 3' });
      b += T(W - padX, y(SB.level) - 5, 'POOL 110.00', { fill: C.purple, size: 9, anchor: 'end' });
      bars.forEach((bar, i) => {
        const trig = s >= 1 && i === SB_PRIOR.length;
        b += candle(cx(i), bw * 0.52, bar, y,
          { op: i < SB_PRIOR.length ? .65 : 1, edge: trig ? col : null });
      });
      if (s === 0) {
        [2, 6].forEach(i => {
          b += '<circle cx="' + f(cx(i)) + '" cy="' + f(y(SB_PRIOR[i].h)) + '" r="4" fill="none" stroke="' +
            C.purple + '" stroke-width="1.4"/>';
        });
        b += T(padX, H - 24, 'two highs, 0.55 apart', { fill: C.fg4, size: 9 });
      } else {
        const t = SB_TRIG[kind];
        const broke = t.c > SB.level + SB.tol;
        b += T(padX, H - 26, 'high ' + t.h.toFixed(2) + '  ·  close ' + t.c.toFixed(2),
          { fill: C.fg3, size: 9.5 });
        b += T(padX, H - 12, broke ? 'close > 110.40  ->  BROKEN' : 'close <= 110.00  ->  SWEEP / REJECTED',
          { fill: col, size: 9.5, ls: '.06em' });
      }
      return svgRoot(W, H, b, title + ' panel');
    }
  };

  /* ─────────── 3.5 regime map ─────────── */
  const RG_ORDER = ['BULL_TREND', 'WEAKENING_BULL', 'TRANSITION',
    'BEAR_TREND', 'WEAKENING_BEAR', 'RANGE'];
  const RG_PLAY = {
    BULL_TREND: 'demand touch -> PULLBACK LONG, base rank 50',
    WEAKENING_BULL: 'demand touch -> PULLBACK LONG, base rank 50',
    BEAR_TREND: 'supply touch -> PULLBACK SHORT, base rank 50',
    WEAKENING_BEAR: 'supply touch -> PULLBACK SHORT, base rank 50',
    TRANSITION: 'zone touch AND a liquidity sweep -> REVERSAL, base 40. No sweep: nothing.',
    RANGE: 'no playbook. Nothing can fire here, by design.'
  };
  const RG_EVENTS = [
    { k: 'START', txt: 'no facts yet' },
    { k: 'LABEL', type: 'HIGH', label: 'HH', txt: 'a swing high above the last one' },
    { k: 'BREAK', event: 'BOS', direction: 'BULL', txt: 'a close above that high' },
    { k: 'LABEL', type: 'LOW', label: 'HL', txt: 'a swing low above the last one' },
    { k: 'LABEL', type: 'HIGH', label: 'LH', txt: 'a high that failed to exceed the last' },
    { k: 'BREAK', event: 'CHOCH', direction: 'BEAR', txt: 'a close below the last swing low' },
    { k: 'LABEL', type: 'LOW', label: 'LL', txt: 'a lower low' },
    { k: 'BREAK', event: 'BOS', direction: 'BEAR', txt: 'another close lower' },
    { k: 'LABEL', type: 'HIGH', label: 'HH', txt: 'a high above the last one' }
  ];
  /* Replay the event stream through the ported classifier so the widget shows
     what the engine would classify, not what the author remembers. */
  const RG_STATES = (function () {
    let lastBreak = null, hi = null, lo = null, prev = null;
    return RG_EVENTS.map(e => {
      if (e.k === 'LABEL') { if (e.type === 'HIGH') hi = e.label; else lo = e.label; }
      else if (e.k === 'BREAK') lastBreak = e;
      const r = classifyRegime(lastBreak, hi, lo);
      const out = { regime: r, hi: hi, lo: lo, changed: r !== prev, lastBreak: lastBreak };
      prev = r;
      return out;
    });
  })();

  WIDGETS.regimeMap = {
    id: 'regimeMap',
    title: 'Six states',
    caption: 'classified from structure facts only',
    steps: RG_EVENTS.map((e, i) => ({
      label: e.k === 'START' ? 'START' : e.k === 'BREAK' ? e.event + ' ' + e.direction : e.label,
      note: (function () {
        const st = RG_STATES[i];
        const base = '<b>' + st.regime.replace('_', ' ') + '</b> — ' +
          (st.changed ? 'the classification changed, so a regime fact is written.'
            : 'the classification did not change, so <b>no fact is written</b>. ' +
            'The store only records transitions.');
        const extra = i === 2
          ? ' Look closely: a bull break with only a high label in evidence is not BULL_TREND. ' +
          'The engine needs both HH and HL before it will say trend, and with half the ' +
          'evidence it says WEAKENING_BULL.'
          : i === 4
            ? ' Nothing broke. One label disagreed, and that alone downgrades a live trend — ' +
            'which is the earliest warning this classifier can give you.'
            : i === 5
              ? ' A change of character is not a new trend. It is an unsettled state, and the ' +
              'only regime in which the REVERSAL playbook can fire — and even then only with ' +
              'a liquidity sweep to pay for it.'
              : i === 8
                ? ' Same shape in the other direction: a bear trend with one label now ' +
                'disagreeing.'
                : '';
        return base + extra;
      })()
    })),
    svg: function (step) {
      const s = clampStep(this, step);
      const st = RG_STATES[s], ev = RG_EVENTS[s];
      const W = 640, H = 300;
      let b = '';
      b += T(24, 18, 'EVENT ' + (s + 1) + ' OF ' + RG_EVENTS.length + '  ·  ' +
        (ev.k === 'START' ? 'nothing yet' : ev.k === 'BREAK' ? ev.event + ' ' + ev.direction : ev.type + ' ' + ev.label) +
        '  ·  ' + ev.txt, { fill: C.fg3, size: 10, ls: '.06em' });
      const bw = 190, bh = 54, gx = 24, gy = 34;
      RG_ORDER.forEach((r, i) => {
        const col = i % 3, row = Math.floor(i / 3);
        const x = gx + col * (bw + 12), yy = gy + row * (bh + 12);
        const on = r === st.regime;
        const tone = r.indexOf('BULL') >= 0 ? C.green : r.indexOf('BEAR') >= 0 ? C.red
          : r === 'TRANSITION' ? C.amber : C.fg3;
        b += rect(x, yy, bw, bh, {
          fill: on ? 'rgba(255,255,255,.06)' : 'rgba(0,0,0,.30)',
          stroke: on ? tone : C.line, w: on ? 1.6 : 1, r: 8
        });
        b += T(x + 12, yy + 22, r.replace('_', ' '),
          { fill: on ? tone : C.fg4, size: 11, ls: '.10em' });
        b += T(x + 12, yy + 38, r === 'BULL_TREND' ? 'BOS bull + HH + HL'
          : r === 'BEAR_TREND' ? 'BOS bear + LH + LL'
            : r === 'WEAKENING_BULL' ? 'BOS bull + one of them'
              : r === 'WEAKENING_BEAR' ? 'BOS bear + one of them'
                : r === 'TRANSITION' ? 'last break was a CHoCH' : 'everything else',
          { fill: on ? C.fg3 : C.fg4, size: 8.5 });
      });
      const ey = gy + 2 * (bh + 12) + 12;
      b += line(24, ey, W - 24, ey, { stroke: C.line });
      b += T(24, ey + 18, 'EVIDENCE', { fill: C.fg4, size: 9, ls: '.20em' });
      b += T(110, ey + 18, 'last break ' +
        (st.lastBreak ? st.lastBreak.event + ' / ' + st.lastBreak.direction : 'none') +
        '     high label ' + (st.hi || '—') + '     low label ' + (st.lo || '—'),
        { fill: C.fg2, size: 10 });
      b += T(24, ey + 38, 'PLAYBOOK', { fill: C.fg4, size: 9, ls: '.20em' });
      b += T(110, ey + 38, RG_PLAY[st.regime],
        { fill: st.regime === 'RANGE' ? C.fg4 : C.fg2, size: 10 });
      b += T(24, ey + 60, st.changed ? 'classification changed -> regime fact written'
        : 'classification unchanged -> no fact written',
        { fill: st.changed ? C.cyan : C.fg4, size: 9.5, ls: '.06em' });
      return svgRoot(W, H, b, 'regime classification, event ' + (s + 1));
    }
  };

  /* ─────────── 3.6 size from stop ─────────── */
  const RISK = { equity: 10000, pct: 0.02, entry: 100 };

  WIDGETS.sizeFromStop = {
    id: 'sizeFromStop',
    title: 'Size follows the stop',
    caption: '$200 of risk, whatever the distance',
    param: { label: 'STOP DISTANCE', min: 0.5, max: 12, step: 0.1, value: 4, unit: '$' },
    steps: [
      {
        label: 'THE RISK IS FIXED', param: 4, note: '2% of a $10,000 account is $200. That ' +
          'number is decided before you look at the chart, and it does not move because a ' +
          'setup looks good.'
      },
      {
        label: 'A NEAR STOP', param: 1, note: 'A $1 stop buys 200 units — a $20,000 position ' +
          'on a $10,000 account. You did not choose 2x leverage; it fell out of the stop ' +
          'distance. Drag the slider and watch the identity hold: <b>implied leverage = risk% ' +
          'divided by stop%</b>.'
      },
      {
        label: 'A FAR STOP', param: 8, note: 'An $8 stop buys 25 units. Eight times the ' +
          'distance, an eighth of the size, and <b>the same $200 lost if it is hit</b>. That ' +
          'interchangeability is the entire reason for sizing this way: a run of losses becomes ' +
          'arithmetic instead of an emergency.'
      },
      {
        label: 'THE CAP CUTS SIZE', param: 1, note: 'On a spot venue the leverage cap is 1x, ' +
          'so the near-stop trade cannot be taken whole. The engine <b>reduces the size</b> and ' +
          'records the decision as REDUCED with reason LEVERAGE_CAP(1x). It does not move the ' +
          'stop to make the size fit — the stop is the trade\'s definition of being wrong, and ' +
          'a trade without one is not a trade.'
      },
      {
        label: 'THE ENVELOPE', param: 4, note: 'Around every position: 2% per trade, 4% total ' +
          'open risk, 2 concurrent positions, a 6% realised daily loss that halts new entries, ' +
          'and a separate drawdown halt from the account peak. They are coupled on purpose — 4% ' +
          'is exactly two 2% trades — which is why no single one of them can be edited alone.'
      }
    ],
    svg: function (step, param) {
      const s = clampStep(this, step);
      const stop = param == null
        ? (this.steps[s].param != null ? this.steps[s].param : this.param.value)
        : Number(param);
      const W = 640, H = 300, padX = 40;
      const capped = s === 3;
      let riskUsd = RISK.equity * RISK.pct;
      let units = riskUsd / stop;
      let notional = units * RISK.entry;
      let lev = notional / RISK.equity;
      let reduced = false;
      if (capped && lev > 1) {                       // engine caps by cutting size
        const scale = 1 / lev;
        riskUsd = Math.round(riskUsd * scale * 100) / 100;
        units = riskUsd / stop; notional = units * RISK.entry; lev = notional / RISK.equity;
        reduced = true;
      }
      if (s === 4) return this._envelope(W, H);

      const y = yScale(RISK.entry - 13, RISK.entry + 3, 34, H - 118);
      let b = '';
      b += line(padX, y(RISK.entry), W - padX, y(RISK.entry), { stroke: C.cyan, w: 1.4 });
      b += T(padX + 4, y(RISK.entry) - 6, 'ENTRY 100.00', { fill: C.cyan, size: 9.5, ls: '.10em' });
      b += line(padX, y(RISK.entry - stop), W - padX, y(RISK.entry - stop),
        { stroke: C.red, w: 1.4, dash: '5 4' });
      b += T(padX + 4, y(RISK.entry - stop) + 14,
        'STOP ' + (RISK.entry - stop).toFixed(2) + '   ·   ' + stop.toFixed(1) + ' away  (' +
        (stop / RISK.entry * 100).toFixed(2) + '% of price)', { fill: C.red, size: 9.5, ls: '.06em' });
      b += rect(padX, y(RISK.entry), W - padX * 2, y(RISK.entry - stop) - y(RISK.entry),
        { fill: 'rgba(248,113,113,.07)' });
      /* the position bar: width is the notional, so the two stop distances are
         visibly different trades that cost the same to be wrong about */
      const barY = H - 100, barW = W - padX * 2;
      b += T(padX, barY - 8, 'POSITION SIZE', { fill: C.fg4, size: 9, ls: '.20em' });
      b += rect(padX, barY, barW, 16, { fill: 'rgba(255,255,255,.05)', r: 4 });
      b += rect(padX, barY, barW * Math.min(1, notional / 24000), 16,
        { fill: reduced ? C.amber : C.cyan, r: 4, op: .8 });
      b += T(padX + 6, barY + 12, nf(units, 2) + ' units  ·  $' + nf(notional) + ' notional',
        { fill: 'var(--bg)', size: 10, weight: '600' });
      b += verdict(padX, H - 64, barW,
        'risk $' + nf(riskUsd, 2) + '   ·   units = risk / stop = ' + nf(units, 2) +
        '   ·   implied leverage ' + lev.toFixed(2) + 'x' + (reduced ? '   ·   REDUCED' : ''),
        reduced ? C.amber : C.fg2);
      b += T(padX, H - 24, reduced
        ? 'LEVERAGE_CAP(1x) — size cut from ' + nf(200 / stop, 2) + ' units to ' + nf(units, 2) +
        '. The stop did not move.'
        : 'leverage = risk% / stop% = ' + (RISK.pct * 100).toFixed(0) + '% / ' +
        (stop / RISK.entry * 100).toFixed(2) + '% = ' + lev.toFixed(2) + 'x',
        { fill: C.fg4, size: 9.5 });
      return svgRoot(W, H, b, 'position sizing, step ' + (s + 1));
    },
    _envelope: function (W, H) {
      const rows = [
        ['risk per trade', '2% of current equity', '$200 on $10,000'],
        ['total open risk', '4%', 'two full-size trades, then reduce or refuse'],
        ['concurrent positions', '2', 'BTC and ETH count together — correlated exposure'],
        ['daily loss halt', '6% realised in a UTC day', 'about three stop-outs, not one'],
        ['drawdown halt', 'from the account peak', 'catches a slow bleed no single day trips'],
        ['reduced below 25%', 'refused instead', 'a token position pays a full trade\'s fees'],
        ['open positions', 'still settle', 'refusing to close is not a safety feature']
      ];
      let b = '', yy = 40;
      b += T(40, 22, 'THE ENVELOPE — engine/risk.py, one portfolio-wide pass in time order',
        { fill: C.fg3, size: 10.5, ls: '.06em' });
      rows.forEach(r => {
        b += T(40, yy, r[0], { fill: C.fg4, size: 10 });
        b += T(230, yy, r[1], { fill: C.fg, size: 11 });
        b += T(400, yy, r[2], { fill: C.fg4, size: 9 });
        b += line(40, yy + 8, W - 40, yy + 8, { stroke: C.line, op: .6 });
        yy += 30;
      });
      b += T(40, yy + 12, 'Every one of these produces APPROVED, REDUCED or REJECTED with the ' +
        'reason attached. A refusal is as auditable as a fill.', { fill: C.fg3, size: 10 });
      return svgRoot(W, Math.max(H, yy + 26), b, 'the risk envelope');
    }
  };

  /* ─────────── 3.7 confluence ─────────── */
  const CF_FACTORS = ['RSI', 'MACD', 'MA SLOPE', 'MOMENTUM', 'RATE OF CHANGE'];
  /* Illustrative of the SHAPE, not measured on this store. The measured case is
     named in the chapter: the previous project's 26 factors collapsing to about
     five independent signals. */
  const CF_R = [
    [1, .93, .91, .96, .94],
    [.93, 1, .88, .90, .92],
    [.91, .88, 1, .87, .89],
    [.96, .90, .87, 1, .95],
    [.94, .92, .89, .95, 1]
  ];
  const CF_AXES = [
    ['FIRE RATE', 'how often it is present at all', 'absent 95% of the time = not carrying the decision'],
    ['DISPERSION', 'how much it varies', 'says the same thing every time = separates nothing'],
    ['CONTRIBUTION', 'share of the composite\'s variance', 'shares summing above 1.0 = double-counting'],
    ['REDUNDANCY', 'pairwise correlation', '|r| >= 0.70 is overlap — gives an effective independent count'],
    ['OUTCOME EDGE', 'correlation with realised R', 'judged against the noise floor +/- 1.96 / sqrt(n)']
  ];
  const CF_RANK = [
    ['base — PULLBACK', 50, 'or 40 for a REVERSAL'],
    ['liquidity sweep within 10 bars', 20, 'in the direction of the trade'],
    ['volume on the confirming bar', 15, 'above 1.5x the previous 20-bar average'],
    ['R:R at or above 2.5', 15, ''],
    ['higher timeframe agrees', 10, '4H defers to 1D, 1D to 1W']
  ];

  WIDGETS.confluenceStack = {
    id: 'confluenceStack',
    title: 'Counting agreement',
    caption: 'five green ticks, one opinion',
    steps: [
      {
        label: 'FIVE AGREE', note: 'Five indicators, all bullish. This reads as five ' +
          'confirmations and it is the most persuasive screen in retail trading.'
      },
      {
        label: 'ONE SOURCE', note: 'All five are functions of the same closing prices. When ' +
          'price rises they all say bullish, because there was never any arrangement of that ' +
          'price series in which they could disagree. Adding them together adds arithmetic, ' +
          'not evidence.'
      },
      {
        label: 'CORRELATION', note: 'Every pair is above 0.85. The grader\'s threshold is ' +
          '<code>|r| >= 0.70</code>, so the whole set collapses to an <b>effective independent ' +
          'count of 1</b>. Two agreeing witnesses beat one only if they were not in the room ' +
          'together.'
      },
      {
        label: 'FIVE AXES', note: 'What a factor has to clear before it is allowed to weigh ' +
          'anything. Four of these ask whether it <i>could</i> predict. Only the last one asks ' +
          'whether it <i>does</i> — and against the noise floor for the sample you actually ' +
          'have, not the sample you wish you had.'
      },
      {
        label: 'WHAT THIS COUNTS', note: 'The whole of SniperSight\'s rank: five terms, capped ' +
          'at 100. It orders the deck when several setups exist. It is <b>not</b> a probability, ' +
          'nothing is calibrated against outcomes, and no threshold on it gates a trade. The ' +
          'confluence block recorded next to every setup carries a <code>score</code> field that ' +
          'is deliberately emitted as 0 and consumed by nothing, waiting for a factor to earn it.'
      }
    ],
    svg: function (step) {
      const s = clampStep(this, step);
      const W = 640, H = 300;
      let b = '';
      if (s === 0 || s === 1) {
        b += T(30, 22, s === 0 ? 'CONFLUENCE  5 / 5' : 'CONFLUENCE  5 / 5  — from one input',
          { fill: s === 0 ? C.green : C.amber, size: 13, ls: '.14em' });
        CF_FACTORS.forEach((n, i) => {
          const yy = 50 + i * 38;
          b += rect(300, yy, 300, 28, { fill: 'rgba(0,255,170,.07)', stroke: 'rgba(0,255,170,.28)', r: 6 });
          b += T(312, yy + 19, n, { fill: C.fg2, size: 11, ls: '.10em' });
          b += T(588, yy + 19, 'BULLISH', { fill: C.green, size: 10, anchor: 'end', ls: '.12em' });
          if (s === 1) {
            b += '<path d="M 190 165 C 240 165, 250 ' + (yy + 14) + ', 296 ' + (yy + 14) +
              '" fill="none" stroke="' + C.amber + '" stroke-width="1.2" opacity=".7"/>';
          }
        });
        if (s === 1) {
          b += rect(30, 140, 160, 50, { fill: 'rgba(255,194,102,.09)', stroke: C.amber, r: 8 });
          b += T(110, 162, 'ONE PRICE SERIES', { fill: C.amber, size: 10.5, anchor: 'middle', ls: '.10em' });
          b += T(110, 178, '4H closes', { fill: C.fg3, size: 9.5, anchor: 'middle' });
          b += T(30, 226, 'Five measurements of one thing are one measurement',
            { fill: C.fg2, size: 11 });
          b += T(30, 244, 'with five error bars stacked on top of each other.',
            { fill: C.fg2, size: 11 });
        }
        return svgRoot(W, H, b, 'five agreeing indicators');
      }
      if (s === 2) {
        b += T(30, 22, 'PAIRWISE CORRELATION', { fill: C.fg2, size: 11, ls: '.14em' });
        const cell = 40, ox = 150, oy = 46;
        CF_FACTORS.forEach((n, i) => {
          b += T(ox - 8, oy + i * cell + 24, n, { fill: C.fg4, size: 9, anchor: 'end' });
          b += T(ox + i * cell + cell / 2, oy - 8, n.slice(0, 3),
            { fill: C.fg4, size: 8.5, anchor: 'middle' });
        });
        CF_R.forEach((row, i) => row.forEach((r, j) => {
          const hot = i !== j && Math.abs(r) >= 0.70;
          b += rect(ox + j * cell, oy + i * cell, cell - 3, cell - 3, {
            fill: i === j ? 'rgba(255,255,255,.05)'
              : hot ? 'rgba(248,113,113,' + (0.10 + (r - .7) * 0.9).toFixed(2) + ')' : 'rgba(0,0,0,.3)',
            stroke: hot ? 'rgba(248,113,113,.45)' : C.line, r: 4
          });
          b += T(ox + j * cell + (cell - 3) / 2, oy + i * cell + 24, i === j ? '—' : r.toFixed(2),
            { fill: i === j ? C.fg4 : C.red, size: 9.5, anchor: 'middle' });
        }));
        b += T(30, 262, 'threshold |r| >= 0.70', { fill: C.fg4, size: 9.5 });
        b += T(30, 280, 'EFFECTIVE INDEPENDENT FACTORS: 1', { fill: C.red, size: 12, ls: '.10em' });
        b += T(360, 280, 'shape is illustrative; the measured case was 26 -> ~5',
          { fill: C.fg4, size: 8.5 });
        return svgRoot(W, H, b, 'correlation matrix');
      }
      if (s === 3) {
        b += T(30, 22, 'WHAT A FACTOR MUST CLEAR — engine/factorstats.py',
          { fill: C.fg2, size: 11, ls: '.08em' });
        CF_AXES.forEach((a, i) => {
          const yy = 50 + i * 46;
          b += T(30, yy + 12, String(i + 1), { fill: C.fg4, size: 11 });
          b += T(52, yy + 12, a[0], { fill: i === 4 ? C.cyan : C.fg2, size: 11, ls: '.12em' });
          b += T(210, yy + 12, a[1], { fill: C.fg3, size: 10 });
          b += T(52, yy + 28, a[2], { fill: C.fg4, size: 9 });
          b += line(30, yy + 36, W - 30, yy + 36, { stroke: C.line, op: .6 });
        });
        b += T(30, 288, 'Axes 1-4 ask whether it could predict. Axis 5 asks whether it does.',
          { fill: C.cyan, size: 10 });
        return svgRoot(W, H, b, 'the five grading axes');
      }
      b += T(30, 22, 'SNIPERSIGHT\'S RANK — engine/setups.py', { fill: C.fg2, size: 11, ls: '.08em' });
      let yy = 52, tot = 0;
      CF_RANK.forEach(r => {
        tot += r[1];
        b += T(30, yy + 12, r[0], { fill: C.fg2, size: 11 });
        b += rect(330, yy, 200 * (r[1] / 50), 14, { fill: C.cyan, r: 3, op: .7 });
        b += T(548, yy + 12, '+' + r[1], { fill: C.fg, size: 11, anchor: 'end' });
        if (r[2]) b += T(30, yy + 27, r[2], { fill: C.fg4, size: 8.5 });
        yy += 42;
      });
      b += line(30, yy, W - 30, yy, { stroke: C.line });
      b += T(30, yy + 20, 'maximum ' + Math.min(100, tot) + '  (capped at 100)  ·  a RANKING, not a probability',
        { fill: C.fg, size: 11 });
      b += T(30, yy + 38, 'Five terms. Nothing gates on it. Nothing claims it is calibrated.',
        { fill: C.fg4, size: 9.5 });
      return svgRoot(W, Math.max(H, yy + 50), b, 'the rank breakdown');
    }
  };

  /* ─────────── 3.8 the setup card ─────────── */
  /* One concrete setup, arithmetically consistent with setup-v0.7-draft:
       zone      DEMAND 60,410.00 - 61,240.00   (0.25 x ATR wide, ATR 3,320)
       confirm   a bar that dipped to 60,180 and closed back above 61,240
                 in the top third of its own range
       stop      min(60,180, 60,410) - 0.15 x 3,320 = 59,682.00
       entry     the next bar's open, 61,510.00      (MARKET_NEXT_OPEN)
       risk      1,828.00
       target    nearest pool 68,400 -> capped at entry + 3R = 66,994.00
       R:R       3.00 exactly, because the cap bound
       rank      50 base + 15 volume + 15 R:R + 10 HTF = 90
       size      $200 / 1,828 = 0.10941 units -> $6,730 notional -> 0.67x */
  const CARD = {
    symbol: 'BTC-USD', tf: '4H', strategy: 'PULLBACK', dir: 'LONG', rank: 90,
    entry: 61510, tp: 66994, sl: 59682, rr: '3.00',
    why: 'BULL_TREND regime · pullback into DEMAND zone 60,410.00-61,240.00 · confirmed by a ' +
      'close back above the zone on 2.10x volume · 1D agrees · TP 66,994.00 · R:R 3.00',
    risk: 'APPROVED · risks $200.00 · 0.10941 units · $6,730 notional · 0.67x'
  };

  WIDGETS.setupCard = {
    id: 'setupCard',
    title: 'Anatomy of a setup card',
    caption: 'every line, and where it came from',
    steps: [
      {
        label: 'THE CARD', note: 'One row on the Command deck. Nothing on it is prose — every ' +
          'field is a value some engine wrote, and every one of them is checkable against the ' +
          'chart in front of you.'
      },
      {
        label: 'MARKET', note: 'Symbol and timeframe. A 4H setup is a 4H idea: its zone was ' +
          'built from 4H swings, its ATR is a 4H ATR, and its stop is 4H-sized. The strategy ' +
          'name tells you which playbook matched — PULLBACK is a continuation trade, REVERSAL ' +
          'is not.'
      },
      {
        label: 'DIRECTION & RANK', note: 'Direction comes from the zone type, not from a view: ' +
          'demand means long, supply means short. Rank is the five-term score from the previous ' +
          'chapter. Read it as <b>which of these to look at first</b>, never as how likely any ' +
          'of them is.'
      },
      {
        label: 'THE BRACKET', note: 'Entry is the next bar\'s open after the confirming close — ' +
          'a price that demonstrably traded, so no fill has to be assumed. Stop sits just ' +
          'beyond the confirming bar\'s own low, which is a level the market visibly rejected. ' +
          'Target is the nearest unbroken liquidity pool beyond entry, <b>capped at 3R</b>. An ' +
          'R:R of exactly 3.00 means the cap bound, not that structure happened to land there.'
      },
      {
        label: 'THE WHY LINE', note: 'Assembled from the facts that produced the setup, not ' +
          'written by hand. Each clause is falsifiable: "1D agrees" means the daily regime had ' +
          'already confirmed as bullish at that moment; "2.10x volume" means the confirming ' +
          'bar traded 2.1 times its previous 20-bar average. If a clause is not true on the ' +
          'chart, that is a bug worth reporting.'
      },
      {
        label: 'THE VERDICT', note: 'A separate engine\'s answer to a separate question. The ' +
          'strategy layer decides whether this is a trade; the risk authority decides whether ' +
          'the <b>account</b> can take it right now. Merging them would hide which one said no ' +
          '— and "nothing found" and "found, all refused" call for completely different ' +
          'responses.'
      }
    ],
    svg: function (step) {
      const s = clampStep(this, step);
      const W = 640, H = 300;
      const zones = [
        null,
        { x: 24, y: 44, w: 150, h: 52 },
        { x: 180, y: 44, w: 120, h: 52 },
        { x: 24, y: 104, w: 592, h: 46 },
        { x: 24, y: 158, w: 592, h: 58 },
        { x: 24, y: 224, w: 592, h: 46 }
      ];
      let b = '';
      b += rect(16, 30, W - 32, 252, { fill: 'rgba(0,0,0,.35)', stroke: C.line, r: 10 });
      b += T(24, 22, 'COMMAND · SETUP DECK', { fill: C.fg4, size: 9, ls: '.20em' });

      b += T(34, 64, CARD.symbol.replace('-USD', ''), { fill: C.fg, size: 14 });
      b += T(34, 82, CARD.tf + '  ·  ' + CARD.strategy, { fill: C.fg4, size: 9.5, ls: '.14em' });
      b += rect(188, 52, 56, 18, { fill: 'rgba(0,255,170,.10)', r: 9 });
      b += T(216, 65, CARD.dir, { fill: C.green, size: 9.5, anchor: 'middle', ls: '.14em' });
      b += T(188, 84, 'rank ' + CARD.rank, { fill: C.fg4, size: 9.5, ls: '.14em' });

      b += T(34, 130, 'entry', { fill: C.fg4, size: 9.5 });
      b += T(80, 130, nf(CARD.entry), { fill: C.fg, size: 12 });
      b += T(180, 130, 'tp', { fill: C.fg4, size: 9.5 });
      b += T(202, 130, nf(CARD.tp), { fill: C.green, size: 12 });
      b += T(302, 130, 'sl', { fill: C.fg4, size: 9.5 });
      b += T(322, 130, nf(CARD.sl), { fill: C.red, size: 12 });
      b += T(422, 130, 'R:R', { fill: C.fg4, size: 9.5 });
      b += T(452, 130, CARD.rr, { fill: C.fg2, size: 12 });
      b += T(500, 130, '(3R cap bound)', { fill: C.fg4, size: 8.5 });

      /* the why line wraps by hand: SVG text has no flow */
      const words = CARD.why.split(' ');
      let ln = '', lines = [];
      words.forEach(w => {
        if ((ln + ' ' + w).length > 78) { lines.push(ln); ln = w; } else ln = ln ? ln + ' ' + w : w;
      });
      lines.push(ln);
      lines.slice(0, 3).forEach((l, i) => {
        b += T(34, 180 + i * 15, l, { fill: C.fg3, size: 9.5 });
      });

      b += rect(34, 234, 74, 18, { fill: 'rgba(0,255,170,.10)', r: 9 });
      b += T(71, 247, 'APPROVED', { fill: C.green, size: 9, anchor: 'middle', ls: '.12em' });
      b += T(120, 247, 'risks $200.00  ·  0.10941 units  ·  $6,730 notional  ·  0.67x',
        { fill: C.fg3, size: 9.5 });

      const z = zones[s];
      if (z) {
        b += rect(z.x, z.y, z.w, z.h, { stroke: C.cyan, w: 1.6, r: 8, fill: 'rgba(34,211,238,.06)' });
      }
      b += T(24, 294, s === 0 ? 'what it does not tell you: whether it will work'
        : 'engine/setups.py · setup-v0.7-draft  +  engine/risk.py · risk-v0.7-draft',
        { fill: C.fg4, size: 9.5 });
      return svgRoot(W, H, b, 'setup card anatomy, step ' + (s + 1));
    }
  };

  function clampStep(spec, i) {
    const n = spec.steps.length;
    const v = Number(i);
    if (!isFinite(v)) return 0;
    return Math.max(0, Math.min(n - 1, Math.trunc(v)));
  }

  /* ═══════════════════════════════════════════════════════════════════════
     4. chapters

     Same four sections every time. `mechanic` says what the code does,
     `why` says why that mechanism works, `mistakes` are flip cards, `widget`
     names the thing you can manipulate. `source` names the file and algo
     version the copy was read out of.
     ═══════════════════════════════════════════════════════════════════════ */

  const t = (k, txt) => '<span class="term" data-t="' + k + '">' + txt + '</span>';

  const CHAPTERS = [
    /* ───────────── 1 ───────────── */
    {
      id: 'swings', n: 1, title: 'Swings',
      question: 'Why do only some turning points matter?',
      source: 'engine/swings.py · swing-v0.8-draft',
      widget: 'swingTiers',
      mechanic:
        '<p>A ' + t('swing', 'swing') + ' is a turning point: a high where price stopped ' +
        'rising, or a low where it stopped falling. SniperSight finds them in four passes, ' +
        'and each pass throws most of the previous one away.</p>' +
        '<table class="lsn-tbl"><tbody>' +
        '<tr><td>MICRO</td><td>A five-candle fractal. A bar is a swing high when its high is ' +
        'strictly greater than the highs of the two bars before it and the two bars after it. ' +
        'Ties produce nothing. Because it needs the two bars after, a swing is not knowable ' +
        'until the second one closes, and the engine stamps it confirmed only then.</td></tr>' +
        '<tr><td>LOCAL</td><td>A micro swing survives if price reversed away from it by at ' +
        'least <code>0.75 x ATR14</code> before the next opposite-type micro swing. ATR is ' +
        'measured at the swing\'s own bar, so the test scales itself.</td></tr>' +
        '<tr><td>CANDIDATE</td><td>Collapse the locals into a strictly alternating high / low ' +
        'list, then keep the ones more extreme than the same-type pivot two places to the left ' +
        '<em>and</em> two places to the right.</td></tr>' +
        '<tr><td>DOMINANT</td><td>Run that same test again, on the survivors.</td></tr>' +
        '</tbody></table>' +
        '<p>Then a score out of 114 decides the label, from seven components: margin over its ' +
        'neighbours (18 points), reversal size in ATR (24), how long the level held before ' +
        'price traded through it (14), volume at the turn, log-scaled (12), liquidity it ' +
        'harvested (8), structure it caused or was later broken by (26), and 12 for surviving ' +
        'the second recursion. <b>55 or more is ' + t('major', 'MAJOR') + ', 30 or more is ' +
        'INTERMEDIATE</b>, and below 30 it stays a local wiggle with no higher-tier ' +
        t('fact', 'fact') + ' written at all.</p>' +
        '<p>The tiers are load-bearing. On 1D and 1W, structure breaks key off MAJOR swings ' +
        'only; on 4H, 1H and 15m they key off INTERMEDIATE. Zones and liquidity pools are ' +
        'built from INTERMEDIATE and above. Get the tier wrong and everything downstream ' +
        'moves.</p>',
      why:
        '<p>A turning point is where one side ran out of inventory. For price to stop rising, ' +
        'every resting buy order at that price had to be filled and no new ones arrived — the ' +
        'buyers were finished. That is information, and the more it cost to exhaust them, the ' +
        'more of it there is.</p>' +
        '<p>The 0.75 ATR filter is that whole idea compressed into one number. ATR is what this ' +
        'market moves in an average bar. A reversal smaller than three quarters of that is ' +
        'inside the noise the market makes anyway; you cannot distinguish it from a bar that ' +
        'happened to close where it did. A reversal larger than it required something to change ' +
        'hands.</p>' +
        '<p>The recursion answers a question a fixed lookback cannot: <b>important compared to ' +
        'what?</b> A 20-bar pivot on 15m and a 20-bar pivot on 1W are not the same object. By ' +
        'asking each pivot to beat its own neighbours, and then asking the survivors to do it ' +
        'again, the test scales to whatever timeframe it runs on without a single extra ' +
        'parameter to tune. Parameters you do not have cannot be overfitted.</p>' +
        '<p>And the score exists because geometry on its own lies. A pivot can be perfectly ' +
        'shaped and mean nothing if nothing happened there. Look at which two components are ' +
        'heaviest: reversal size at 24 and structural impact at 26. Both measure consequence, ' +
        'not shape. A modest high that later caused two breaks of structure outranks a taller ' +
        'high that caused none — because the market\'s own subsequent behaviour is the only ' +
        'vote that counts.</p>',
      mistakes: [
        {
          wrong: '"Every three-bar pivot is a swing."',
          right: 'Five bars, strictly, and then everything under 0.75 ATR of reversal is thrown ' +
            'away. Step the widget: 27 fractals in, one dominant pivot out.'
        },
        {
          wrong: '"I can see the swing high on the chart right now."',
          right: 'You can see a candidate. It is not confirmed until two more bars close. Every ' +
            'fact here carries the moment it became knowable, and nothing downstream is allowed ' +
            'to use it earlier than that.'
        },
        {
          wrong: '"A bigger swing is a more important swing."',
          right: 'Size is 24 of the available points. Consequence — what broke because of it — ' +
            'is 26. The engine will rank a modest high that flipped the trend above a spike ' +
            'that did nothing.'
        },
        {
          wrong: '"The tiers are just labels."',
          right: 'A 1D break only fires off a MAJOR swing. A zone only exists off INTERMEDIATE ' +
            'or better. The tier decides whether anything downstream sees the swing at all.'
        }
      ]
    },

    /* ───────────── 2 ───────────── */
    {
      id: 'structure', n: 2, title: 'Structure',
      question: 'Who is in control, and when did that change?',
      source: 'engine/structure.py · structure-v0.8-draft',
      widget: 'wickVsClose',
      mechanic:
        '<p>Two labels and one rule.</p>' +
        '<p>Every swing is labelled against the previous swing of the same type. A high above ' +
        'the last high is <b>HH</b>, below it is <b>LH</b>. A low above the last low is ' +
        '<b>HL</b>, below it is <b>LL</b>.</p>' +
        '<p>A break happens when a <b>closed</b> candle closes beyond the level of the most ' +
        'recent confirmed swing on that side, by more than <code>max(1 tick, 0.05 x ATR)</code>. ' +
        'A wick through the level is not a break. Ever.</p>' +
        '<table class="lsn-tbl"><tbody>' +
        '<tr><td>' + t('bos', 'BOS') + '</td><td>Break of Structure. The break went the same ' +
        'way as the current structural direction, or the direction was NEUTRAL. ' +
        'Continuation.</td></tr>' +
        '<tr><td>' + t('choch', 'CHoCH') + '</td><td>Change of Character. The break went ' +
        'against it. The first warning that the trend may be over.</td></tr>' +
        '</tbody></table>' +
        '<p>Two further rules stop the engine double-counting. <b>Causality:</b> a level can ' +
        'only be broken from the moment it confirmed, so the engine walks bars forward in time ' +
        'and admits each swing as it becomes knowable. <b>Consumption:</b> once a side breaks, ' +
        'that level is spent — that side cannot break again until a new swing, formed after the ' +
        'break bar, confirms there.</p>',
      why:
        '<p>A level is not a line. It is a place where orders are.</p>' +
        '<p>Above a swing high sit two kinds of order: stop-losses belonging to everyone who is ' +
        'short, and buy-stops belonging to everyone waiting for a breakout. Both are buy ' +
        'orders, both are resting, and both execute automatically on touch. That is why price ' +
        'is drawn there — it is the nearest pool of guaranteed fills, and anyone who needs to ' +
        'move real size goes where the fills are.</p>' +
        '<p>Which is exactly why a wick is not a break. A wick through the level means those ' +
        'orders were consumed and then price came back. Someone took the liquidity and rejected ' +
        'the price. Had the move been funded by genuine demand, the fills would have paid for ' +
        'continuation rather than a return.</p>' +
        '<p>A close is a different event. A close beyond the level is the market agreeing, for ' +
        'an entire bar, on a price it previously refused — with everyone who wanted to fade it ' +
        'having had the whole bar to do so. The tolerance on top exists because a close half a ' +
        'tick past the level is a rounding error, not a decision. Five percent of an average ' +
        'bar\'s range is the smallest amount that means anything.</p>' +
        '<p>The consumption rule prevents the most common misreading in this whole subject: the ' +
        'same high being "broken" four bars running while price chops around it. It broke once. ' +
        'After that it is not a level any more, it is history.</p>',
      mistakes: [
        {
          wrong: '"The wick took out the high, so structure broke."',
          right: 'The single most expensive mistake in this subject, and the reason the widget ' +
            'below exists. Most retail structure indicators count wicks as breaks. This one ' +
            'does not, and neither should you.'
        },
        {
          wrong: '"It closed above, so it is a break."',
          right: 'It has to close above by more than max(1 tick, 0.05 ATR). Drag the widget\'s ' +
            'wick slider down and watch a genuine closing bar stop counting.'
        },
        {
          wrong: '"A CHoCH confirms the reversal."',
          right: 'A CHoCH means the trend is breaking, not that a new one exists. The regime ' +
            'engine reads it as TRANSITION — an unsettled state, not a new direction.'
        },
        {
          wrong: '"A 15m CHoCH inside a daily uptrend is a reversal."',
          right: 'It is a pullback with a small break in it. This engine classifies every ' +
            'timeframe separately and does not require them to agree, so that judgement is ' +
            'yours to make.'
        }
      ]
    },

    /* ───────────── 3 ───────────── */
    {
      id: 'zones', n: 3, title: 'Zones',
      question: 'Why does price react at the same area twice?',
      source: 'engine/zones.py · zone-v0.9-draft',
      widget: 'zoneLifecycle',
      mechanic:
        '<p>Every INTERMEDIATE or MAJOR swing creates a ' + t('zone', 'zone') + '.</p>' +
        '<table class="lsn-tbl"><tbody>' +
        '<tr><td>' + t('demand', 'DEMAND') + '</td><td>A floor, below price, anchored at a ' +
        'swing LOW: the band from the low up to <code>low + 0.25 x ATR</code>.</td></tr>' +
        '<tr><td>' + t('supply', 'SUPPLY') + '</td><td>A ceiling, above price, anchored at a ' +
        'swing HIGH: the band from <code>high - 0.25 x ATR</code> up to the high.</td></tr>' +
        '</tbody></table>' +
        '<p>The zone exists from the moment its swing confirmed, not from the moment the swing ' +
        'printed. Then it has a lifecycle, and each transition has an exact rule:</p>' +
        '<ul>' +
        '<li><b>FRESH</b> — created, never touched.</li>' +
        '<li><b>TOUCHED</b> — first touch <em>episode</em>. An episode is price entering the ' +
        'band having been outside it. Ten bars in a row inside the band is one episode, not ' +
        'ten.</li>' +
        '<li><b>TESTED</b> — second episode.</li>' +
        '<li><b>WEAKENED</b> — third and beyond.</li>' +
        '<li><b>BROKEN</b> — a candle <b>closes</b> beyond the far edge by more than ' +
        '<code>max(1 tick, 0.05 x ATR)</code>. The same close-not-wick rule as structure.</li>' +
        '</ul>' +
        '<p>Every transition records a strength score, which is the average of two numbers. ' +
        '<b>Formation quality</b> is fixed at creation: 50, plus 10 for each other same-type ' +
        'zone anchored inside this band (capped at 30), plus a timeframe weight (1W 20, 1D 15, ' +
        '4H 10, 1H and 15m 5). <b>Freshness</b> decays: 100, minus 25 per touch episode, minus ' +
        'one point per 100 bars of age up to 25, and zero once broken. Formation quality never ' +
        'rises — a zone cannot become better than it was born, only used up.</p>',
      why:
        '<p>A zone marks where a lot of inventory changed hands quickly. Somebody had enough ' +
        'size resting there to stop a trend and turn it.</p>' +
        '<p>Orders that size do not fill in one print; they fill in slices. When price leaves ' +
        'faster than the slices complete, part of that order is still unfilled. It is still ' +
        'there, still resting, still at that price. That is the mechanism, and it is why a ' +
        'return to the area gets a reaction rather than indifference.</p>' +
        '<p>It also explains the decay, exactly. Every touch fills more of what was left. The ' +
        'first return meets an order book that mostly still holds the original interest; the ' +
        'third meets the remainder. Which is why the engine counts <b>episodes</b> and not ' +
        'bars: what consumes the resting orders is a fresh approach, not time spent sitting ' +
        'inside the band.</p>' +
        '<p>It explains the width too. Nobody\'s resting orders sit on one exact price — they ' +
        'are spread over a small band. A quarter of an average bar\'s range is a defensible ' +
        'estimate of that spread, and because it is measured in ATR it is the right width on a ' +
        '15-minute chart and on a weekly one without changing the number.</p>' +
        '<p>And it explains why breaking requires a close. Price wicking through a demand zone ' +
        'is the zone doing its job: absorbing sellers and rejecting the price. Price closing ' +
        'below it means the resting bids are gone. Those are different events, and only the ' +
        'second one kills the zone.</p>',
      mistakes: [
        {
          wrong: '"A wick into the zone invalidated it."',
          right: 'A wick into the zone is a touch, which is the zone working. Only a close ' +
            'beyond the far edge, past the tolerance, breaks it.'
        },
        {
          wrong: '"The third test is the strong one."',
          right: 'It is the weakest. Freshness has lost 75 of its 100 points by then. FRESH is ' +
            'the best state a zone will ever be in.'
        },
        {
          wrong: '"Price sat in the zone for eight bars, so that is eight tests."',
          right: 'One episode. The counter only moves when price re-enters from outside. Step ' +
            'the widget to TESTED and count the bars.'
        },
        {
          wrong: '"Strength 47 means a 47% chance."',
          right: 'It means quality and freshness averaged. It is evidence recorded so you can ' +
            'compare two zones, and it makes no claim about probability at all.'
        }
      ]
    },

    /* ───────────── 4 ───────────── */
    {
      id: 'liquidity', n: 4, title: 'Liquidity',
      question: 'Why does price reach a level and immediately reverse?',
      source: 'engine/liquidity.py · liq-v0.8-draft',
      widget: 'sweepVsBreakout',
      mechanic:
        '<p>A <b>pool</b> is two or more INTERMEDIATE-or-better swing highs (or lows) at ' +
        'effectively the same price: within <code>0.10 x ATR</code> of each other, formed ' +
        'within 100 bars of each other. The pool\'s level is the extreme of the cluster — the ' +
        'highest of the highs, the lowest of the lows. It exists from the later swing\'s ' +
        'confirmation.</p>' +
        '<p>Overlapping clusters collapse into one pool. If a third high qualifies into an ' +
        'existing cluster it joins it rather than spawning a second pool at the same price, ' +
        'because two pools at one level would look like two targets when there is one.</p>' +
        '<p>Two ways a pool ends:</p>' +
        '<ul>' +
        '<li><b>' + t('sweep', 'SWEEP') + '</b> — a closed bar trades beyond the level but ' +
        'closes back inside it. High above the level, close at or below it. Recorded as SWEPT, ' +
        'outcome REJECTED.</li>' +
        '<li><b>BROKEN</b> — a bar <b>closes</b> beyond the level by more than ' +
        '<code>max(1 tick, 0.05 x ATR)</code>. The pool is consumed and the scan for it ' +
        'stops.</li>' +
        '</ul>' +
        '<p>The same close-versus-wick distinction as structure, applied to a different ' +
        'object.</p>',
      why:
        '<p>This is where the word ' + t('liquidity', 'liquidity') + ' earns its keep, and it ' +
        'is worth being literal about it.</p>' +
        '<p>Everyone who is short has a stop-loss above the recent high. Everyone waiting to ' +
        'buy a breakout has an order above the recent high. <b>Both of those are buy orders.</b> ' +
        'Two equal highs mean two generations of traders parked their orders at the same price, ' +
        'so the pile is bigger and more certain.</p>' +
        '<p>Now the mechanism, and it is the opposite of what the picture suggests. Somebody ' +
        'who needs to <b>sell</b> a large amount has a problem: selling pushes price down and ' +
        'worsens their own fill. They need buyers. The largest guaranteed cluster of buying ' +
        'available anywhere on the chart is the stop-losses and breakout orders sitting above ' +
        'the equal highs. So price goes up, through the high, those orders fire automatically, ' +
        'the seller is filled into that forced buying — and then price falls, because the ' +
        'buying that took it up there has been spent and there was never anything else behind ' +
        'it.</p>' +
        '<p>That is the shape of a sweep exactly: through the level, closed back inside. The ' +
        'mirror below a low is identical — stops belonging to longs and breakdown orders are ' +
        'both sell orders, which is where a large buyer goes to get filled.</p>' +
        '<p><b>So a sweep is not a failed breakout. It is a successful fill.</b> The reason it ' +
        'reverses so reliably is that trading in the opposite direction was the entire purpose ' +
        'of going there. Which is why this engine records a sweep as REJECTED rather than as a ' +
        'break — and why the difference between the two is, again, only the close.</p>' +
        '<p>Equal highs specifically, rather than any high: the tighter the cluster, the more ' +
        'certain that everybody\'s order is at the same number. A tenth of an average bar is ' +
        'close enough that no ordinary candle could separate them.</p>',
      mistakes: [
        {
          wrong: '"A sweep is a failed breakout."',
          right: 'A sweep is a completed fill. Somebody went there and got exactly what they ' +
            'came for.'
        },
        {
          wrong: '"Price took the highs, so I should go long."',
          right: 'That is the trade the sweep exists to catch. The close is what tells the two ' +
            'apart, and it costs you one bar to wait for it.'
        },
        {
          wrong: '"Liquidity means volume."',
          right: 'Different word. Here it means resting orders at a known price, which is why ' +
            'pools are built from equal highs and lows and not from a volume reading.'
        },
        {
          wrong: '"The pool is the target."',
          right: 'It is <em>a</em> target. SniperSight takes the nearest unbroken pool beyond ' +
            'entry as the take-profit precisely because that is where the fills are, falls back ' +
            'to the nearest opposing swing when there is no pool, and emits no setup at all ' +
            'when there is neither.'
        }
      ]
    },

    /* ───────────── 5 ───────────── */
    {
      id: 'regime', n: 5, title: 'Regime',
      question: 'What kind of market is this, and what is allowed in it?',
      source: 'engine/regime.py · regime-v0.8-draft',
      widget: 'regimeMap',
      mechanic:
        '<p>Six states, classified from structure facts and nothing else: the last break, the ' +
        'most recent high label, the most recent low label.</p>' +
        '<table class="lsn-tbl"><tbody>' +
        '<tr><td>BULL_TREND</td><td>last break BOS / BULL, latest high HH, latest low HL</td></tr>' +
        '<tr><td>BEAR_TREND</td><td>last break BOS / BEAR, latest high LH, latest low LL</td></tr>' +
        '<tr><td>WEAKENING_BULL</td><td>the bull break still stands, but only one of HH / HL ' +
        'agrees</td></tr>' +
        '<tr><td>WEAKENING_BEAR</td><td>the bear break still stands, but only one of LH / LL ' +
        'agrees</td></tr>' +
        '<tr><td>TRANSITION</td><td>the last break was a CHoCH</td></tr>' +
        '<tr><td>RANGE</td><td>anything else, including no break yet</td></tr>' +
        '</tbody></table>' +
        '<p>A ' + t('regime', 'regime') + ' fact is written only when the classification ' +
        '<em>changes</em>. Timeframes are classified independently: 4H can be BULL_TREND while ' +
        '1D is RANGE, and nothing in this engine forces them to agree. Three further states — ' +
        'COMPRESSION, EXPANSION, DISORDERED — are specified and not built; they need volatility ' +
        'facts that do not exist yet, and this page will keep saying so until they do.</p>' +
        '<p><b>The playbook mapping is the part that decides whether you ever see a ' +
        t('setup', 'setup') + ':</b></p>' +
        '<ul>' +
        '<li>BULL_TREND or WEAKENING_BULL, and price touches a DEMAND zone → PULLBACK LONG, ' +
        'base rank 50.</li>' +
        '<li>BEAR_TREND or WEAKENING_BEAR, and price touches a SUPPLY zone → PULLBACK SHORT, ' +
        'base rank 50.</li>' +
        '<li>TRANSITION, a zone touch, <em>and</em> a liquidity sweep nearby → REVERSAL, base ' +
        'rank 40.</li>' +
        '<li>RANGE → nothing. TRANSITION without a sweep → nothing.</li>' +
        '</ul>' +
        '<p>That last line is the single largest source of ' + t('rejection', 'rejections') +
        ' in this system. When the deck is empty it is usually not because nothing was found; ' +
        'it is because what was found landed in a state with no play.</p>',
      why:
        '<p>The classification is built from structure rather than from indicators, and the ' +
        'reason is that structure is a record of decisions while an indicator is a restatement ' +
        'of price. A moving average crossing tells you price moved. HH plus HL plus a break ' +
        'that held tells you buyers made a higher low — they were willing to pay more than last ' +
        'time, before they had to.</p>' +
        '<p>The WEAKENING states matter far more than they look. They are the interval between ' +
        '"the trend is intact" and "the trend has broken", and that interval is where trends ' +
        'actually end. A high that fails to exceed the last one while lows are still rising is ' +
        'not a reversal, and it is not a healthy trend either. Naming it stops you from ' +
        'treating a decaying trend as a live one. Note also that the engine still allows the ' +
        'pullback trade there, at the same base rank — which is a judgement call you are now ' +
        'equipped to disagree with.</p>' +
        '<p>RANGE having no playbook is a position, not an oversight. Trend-following into a ' +
        'range is the classic way to lose money slowly: every entry sits near an edge that is ' +
        'about to reject it. The honest response to a sideways market is not to trade it worse, ' +
        'it is to not trade it.</p>' +
        '<p>REVERSAL requiring a sweep is the same discipline. A change of character on its own ' +
        'is a break that has not proven anything. Requiring a sweep as well means the reversal ' +
        'has to have been <em>paid for</em> — somebody had to get filled — before the engine ' +
        'will act on it. The cost of that discipline is visible in how rarely the REVERSAL ' +
        'playbook fires, and that cost is deliberate.</p>',
      mistakes: [
        {
          wrong: '"The regime is the trend."',
          right: 'It is a classification of the last few structure facts. It can change on one ' +
            'candle, and it says nothing about how long the state will last.'
        },
        {
          wrong: '"4H says BULL_TREND, so I am long."',
          right: 'A 4H bull trend inside a 1D bear trend is a bounce in a downtrend. Nothing ' +
            'here checks the higher timeframe for you on the regime itself, so you have to.'
        },
        {
          wrong: '"Nothing fired, so the scanner is broken."',
          right: 'Check the regime first. RANGE and un-swept TRANSITION have no playbook by ' +
            'design, and the market spends most of its time in them.'
        },
        {
          wrong: '"WEAKENING means get out."',
          right: 'It means one of the two conditions stopped agreeing. That is evidence, and ' +
            'it is the earliest evidence this classifier can give you.'
        }
      ]
    },

    /* ───────────── 6 ───────────── */
    {
      id: 'risk', n: 6, title: 'Risk and R',
      question: 'How big should this trade be?',
      source: 'engine/risk.py · risk-v0.7-draft',
      widget: 'sizeFromStop',
      mechanic:
        '<p>You do not choose a position size. You choose where the idea is wrong, and the size ' +
        'follows from that.</p>' +
        '<ul>' +
        '<li>' + t('riskPerTrade', 'Risk per trade') + ' is 2% of current equity. On a $10,000 ' +
        'account, $200.</li>' +
        '<li>Position size is <code>risk / stop distance</code>. A $1 stop buys 200 units; an ' +
        '$8 stop buys 25.</li>' +
        '<li>Both lose exactly $200 at the stop. That is the entire point.</li>' +
        '<li>The stop itself is a ' + t('structuralStop', 'structural stop') + ' — just beyond ' +
        'the confirming bar\'s own extreme, a level the market has visibly rejected. Never a ' +
        'percentage, and never widened to make a size work.</li>' +
        '</ul>' +
        '<p>The envelope around it is enforced by one portfolio-wide pass in strict time order, ' +
        'because risk is a property of the account and not of a chart: 4% total open risk, 2 ' +
        'concurrent positions, a 6% realised loss in a UTC day that halts new entries for that ' +
        'day (' + t('killSwitch', 'the kill switch') + '), and a separate total-' +
        t('drawdown', 'drawdown') + ' halt measured from the account peak. Open positions still ' +
        'settle through all of them — refusing to close a position is not a safety feature.</p>' +
        '<p>' + t('leverage', 'Leverage') + ' is capped by <b>cutting the size</b>, never by ' +
        'moving the stop; when the cap binds, the decision is recorded as REDUCED with the ' +
        'reason attached. If the reduction would take the trade below a quarter of its intended ' +
        'size it is refused instead, because a token position carries a full trade\'s fees ' +
        'without the substance.</p>' +
        '<p>Everything produces an APPROVED, REDUCED or REJECTED decision with machine-readable ' +
        'reasons, stored as a fact beside the setup. <b>A refusal is as auditable as a ' +
        'fill.</b></p>' +
        '<p>One ' + t('rMultiple', 'R') + ' is what you risked. +2R is twice your risk; −1R is ' +
        'the stop doing its job. Results is denominated this way throughout, so a $200 trade ' +
        'and a $50 trade are comparable and nothing flatters itself by being bigger.</p>',
      why:
        '<p>Sizing from the stop makes losses interchangeable. If every loss is 1R, a run of ' +
        'them is arithmetic rather than an emergency, and the account afterwards is still ' +
        'recognisably the same account. Sizing from a fixed number of units does the opposite: ' +
        'the size of your loss is decided by whatever the stop distance happened to be, so the ' +
        'trades you understand least — the volatile ones, with the wide stops — are the ones ' +
        'that hurt most.</p>' +
        '<p>There is an identity underneath this worth carrying around: <b>implied leverage = ' +
        'risk% divided by stop%</b>. Risking 2% behind a 2% stop is 1x, on any asset, at any ' +
        'price. Risking 2% behind a 0.5% stop is 4x — and notice that the leverage was not a ' +
        'decision you made, it was a consequence of a tight stop. This is precisely why the cap ' +
        'has to cut size rather than widen the stop. The stop is the trade\'s definition of ' +
        'being wrong; move it to fit a position and the trade no longer has one.</p>' +
        '<p>The daily halt exists because the dangerous state is not a loss, it is the state a ' +
        'person is in after three of them. Six percent is about three full stop-outs, so it ' +
        'trips on a bad day and not on an ordinary one.</p>' +
        '<p>And the caps are coupled deliberately: 4% is exactly two 2% trades, and the daily ' +
        'halt is about three. Change one and the others stop meaning what they meant. That is ' +
        'why the risk numbers are displayed on Rules but not editable there — and also ' +
        'because changing them would re-size the entire forward record, which is a different ' +
        'engine wearing the same version number.</p>',
      mistakes: [
        {
          wrong: '"I will risk 2% and use 10x leverage."',
          right: 'Those are not two settings. Leverage is what falls out of your risk and your ' +
            'stop distance. Choose the stop; the rest is arithmetic.'
        },
        {
          wrong: '"The stop is too far away, I will move it closer."',
          right: 'Then it is no longer where the idea is wrong, and the number it produces is ' +
            'no longer a loss you planned. Move the size, never the stop.'
        },
        {
          wrong: '"A tight stop is a safer trade."',
          right: 'It is a bigger position and a higher chance of being stopped by noise. It is ' +
            'also fee-dominated: fees are charged on notional, so a tight stop can turn a 3:1 ' +
            'gross trade into a guaranteed net loser. The engine refuses those — risk must be ' +
            'at least twice the estimated round-trip cost.'
        },
        {
          wrong: '"I am up 4R, I am good at this."',
          right: '4R over four trades is noise. The question Results asks is whether ' +
            t('expectancy', 'expectancy') + ' is distinguishable from zero, and answering it ' +
            'takes far more trades than feel like enough.'
        }
      ]
    },

    /* ───────────── 7 ───────────── */
    {
      id: 'confluence', n: 7, title: 'Confluence',
      question: 'When five things agree, how many things agree?',
      source: 'engine/setups.py · setup-v0.7-draft  +  engine/factorstats.py',
      widget: 'confluenceStack',
      mechanic:
        '<p>' + t('confluence', 'Confluence') + ' means separate reasons pointing the same way. ' +
        'The word doing all the work is <em>separate</em>.</p>' +
        '<p>SniperSight\'s ' + t('rank', 'rank') + ' is five terms and nothing else:</p>' +
        '<table class="lsn-tbl"><tbody>' +
        '<tr><td>base</td><td>50 for a PULLBACK, 40 for a REVERSAL</td></tr>' +
        '<tr><td>+20</td><td>a liquidity sweep within the last 10 bars, in the direction of the ' +
        'trade</td></tr>' +
        '<tr><td>+15</td><td>volume on the confirming bar above 1.5x its previous 20-bar ' +
        'average</td></tr>' +
        '<tr><td>+15</td><td>R:R at or above 2.5</td></tr>' +
        '<tr><td>+10</td><td>' + t('htfAlignment', 'the higher timeframe agrees') +
        ' — 4H defers to 1D, 1D to 1W</td></tr>' +
        '</tbody></table>' +
        '<p>Capped at 100. It is a <b>ranking</b>, used to order the deck when several setups ' +
        'exist. It is deliberately not a probability, nothing claims it is calibrated, and no ' +
        'threshold on it gates a trade.</p>' +
        '<p>A wider block of evidence is recorded next to every setup — higher-timeframe ' +
        'regime and whether it aligned, zone strength and quality and cluster size, the volume ' +
        'ratio, whether a sweep was nearby, bars since the last structure break, the uncapped ' +
        'target distance in R — and it carries a <code>score</code> field that is emitted as 0 ' +
        'and consumed by nothing. The field exists so a later version can populate it without a ' +
        'migration. <b>Recording first and grading second is the whole discipline.</b></p>' +
        '<p>The grader is a separate read-only engine, and it asks five questions of every ' +
        'factor: how often it fires, how much it varies, its share of the composite\'s ' +
        'variance, its pairwise correlation with every other factor (<code>|r| >= 0.70</code> ' +
        'is overlap), and its correlation with realised R against the noise floor of ' +
        '<code>±1.96 / √n</code>.</p>',
      why:
        '<p>This chapter exists because the previous version of this project shipped 26 ' +
        'confluence factors and believed it was stacking 26 confirmations. Pairwise correlation ' +
        'showed they collapsed into roughly five independent signals, each counted three to six ' +
        'times under a different name. Every "very strong confluence" reading was one opinion ' +
        'shouted repeatedly.</p>' +
        '<p>The mechanism is not subtle once you have seen it. RSI, MACD, a moving-average ' +
        'slope, momentum and rate-of-change are all functions of the same closing prices. When ' +
        'price rises they all say bullish, because there was never any arrangement of that ' +
        'price series in which they could have disagreed. Adding them together adds arithmetic, ' +
        'not evidence. It <em>feels</em> like five confirmations and it is one measurement with ' +
        'five error bars stacked on top of each other.</p>' +
        '<p>Independence is what makes counting legitimate at all. Two agreeing witnesses are ' +
        'worth more than one only if they were not in the room together.</p>' +
        '<p>Which is why the fifth axis is the one that decides anything. A factor can fire ' +
        'often, vary widely, contribute plenty to the score, and be uncorrelated with ' +
        'everything else — and still have no relationship whatsoever to whether the trade made ' +
        'money. Correlation with outcome, measured against the noise floor for the sample you ' +
        'actually have, is the only axis that answers "does this predict?". The other four ' +
        'answer "could this predict?", which is a much weaker claim than it sounds.</p>' +
        '<p>And that is the reason the rank here is five terms rather than twenty-six, and the ' +
        'reason nothing is allowed to gate on it. A number that decides trades has to first ' +
        'prove that it predicts them. This one has not been asked to yet, so it is only ' +
        'permitted to sort.</p>',
      mistakes: [
        {
          wrong: '"Five indicators agree, so it is a strong setup."',
          right: 'Ask what they are computed from. If it is all the same closing prices, that ' +
            'is one opinion with five names.'
        },
        {
          wrong: '"Rank 90 means a 90% chance."',
          right: 'It is 50 + 15 + 15 + 10: four fixed bonuses added to a base. It cannot be a ' +
            'probability, and nothing here has been calibrated against outcomes.'
        },
        {
          wrong: '"More factors is a better model."',
          right: 'With correlated features and a few hundred trades, more factors fit the noise ' +
            'better. Fitting is not predicting.'
        },
        {
          wrong: '"The factor works, I have seen it."',
          right: 'A correlation sitting inside the ±1.96/√n noise floor feels exactly like that ' +
            'from the inside. That is what the floor is for.'
        }
      ]
    },

    /* ───────────── 8 ───────────── */
    {
      id: 'card', n: 8, title: 'Reading a setup card',
      question: 'What is this card telling me, and what is it not?',
      source: 'engine/setups.py · setup-v0.7-draft  +  engine/risk.py · risk-v0.7-draft',
      widget: 'setupCard',
      mechanic:
        '<p>Every line, and where it comes from.</p>' +
        '<table class="lsn-tbl"><tbody>' +
        '<tr><td>symbol · timeframe</td><td>Which market, and which chart the structure was ' +
        'measured on. A 4H setup is a 4H idea, with a 4H-sized stop.</td></tr>' +
        '<tr><td>strategy</td><td>PULLBACK or REVERSAL — the playbook that matched. It tells ' +
        'you what the trade is betting on.</td></tr>' +
        '<tr><td>direction</td><td>Decided by the zone type, not by an opinion. Demand means ' +
        'long, supply means short.</td></tr>' +
        '<tr><td>rank</td><td>The five-term score from the previous chapter. Which to look at ' +
        'first, never how likely.</td></tr>' +
        '<tr><td>' + t('entry', 'entry') + '</td><td>The <b>next bar\'s open</b> after the ' +
        'confirming close — a price that demonstrably traded, so no fill has to be ' +
        'assumed.</td></tr>' +
        '<tr><td>' + t('sl', 'stop') + '</td><td>Just beyond the confirming bar\'s own extreme, ' +
        'plus a small ATR buffer. The price at which the level has failed.</td></tr>' +
        '<tr><td>' + t('tp', 'target') + '</td><td>The nearest unbroken liquidity pool beyond ' +
        'entry, or the nearest opposing INTERMEDIATE/MAJOR swing if there is no pool, then ' +
        '<b>capped at 3R</b>. Both the capped and the uncapped values are recorded.</td></tr>' +
        '<tr><td>' + t('rr', 'R:R') + '</td><td>Reward over risk in price units. Below 1.5 the ' +
        'setup is refused outright.</td></tr>' +
        '<tr><td>why</td><td>A sentence assembled from the facts that produced the setup. Not ' +
        'written by hand.</td></tr>' +
        '<tr><td>verdict</td><td>The risk authority\'s decision, which is separate from the ' +
        'setup existing: APPROVED with a dollar risk and a unit count, REDUCED with a reason, ' +
        'or REJECTED with a reason — in which case the card is dimmed and the trade is not ' +
        'available.</td></tr>' +
        '</tbody></table>' +
        '<p>Before it becomes a card at all, the setup passes through a lifecycle: ' +
        t('forming', 'FORMING') + ' when price is approaching the zone, CONFIRMING once it has ' +
        'touched, and VALIDATED only when a closed bar proves the level held — engaging the ' +
        'zone, closing back out of it, and closing in the top third of its own range. If that ' +
        'does not happen within three bars, or the zone breaks first, the setup is CANCELLED ' +
        'rather than traded. See ' + t('confirmation', 'confirmation') + '.</p>' +
        '<p>An armed setup lives four bars. If price has not reached the entry by then, the ' +
        'conditions that produced it are stale and it expires rather than sitting there looking ' +
        'valid.</p>' +
        '<p><b>What the card does not tell you: whether it will work.</b></p>',
      why:
        '<p>A card that showed only entry, target and stop would be an instruction. This one ' +
        'shows its inputs, which makes it an argument you can check.</p>' +
        '<p>Every element is falsifiable from the chart in front of you. "BULL_TREND regime" ' +
        'means there was a bull BOS and the last two labels were HH and HL — go and look. ' +
        '"Pullback into DEMAND zone 60,410–61,240" names the exact band, which was built off a ' +
        'specific swing low you can find. "TP 66,994" says there is a pool of equal highs ' +
        'beyond that, or a cap that bound. If any of it is not on the chart, something is wrong ' +
        'with the engine and you are now in a position to say so — which is the difference ' +
        'between using a tool and obeying one.</p>' +
        '<p>The verdict chip is separate on purpose. The strategy layer\'s job is to find ' +
        'trades; the risk authority\'s job is to decide whether the <em>account</em> can take ' +
        'this one right now. They answer different questions, and a system that merges them ' +
        'hides which one said no. It also makes "nothing found" and "found, all refused" ' +
        'visibly different states — and those call for completely different responses from ' +
        'you.</p>' +
        '<p>The confirmation step is the newest and most consequential rule on the card. In the ' +
        'previous version, entry fired the instant price touched the zone, and 59% of stop-outs ' +
        'happened on the very bar that filled the entry — because total risk was about half an ' +
        'ATR while the bar that touches an ATR-anchored zone has a range of roughly one ATR by ' +
        'construction. The trigger bar and the killing bar were the same bar. Waiting for a ' +
        'close means the wick that would have stopped you has already printed, and it hands you ' +
        'a stop the market visibly rejected instead of an arbitrary offset.</p>',
      mistakes: [
        {
          wrong: '"Rank 90 beats rank 70, so take it."',
          right: 'It is the order to look in. Both still need the same reading, and the reading ' +
            'is what this chapter is for.'
        },
        {
          wrong: '"It says REJECTED but the setup looks great."',
          right: 'Then the account cannot take it: too much open risk, the concurrency cap, the ' +
            'daily halt, or a stop that would sit past liquidation. The reason is printed on ' +
            'the card. It is not a suggestion to override.'
        },
        {
          wrong: '"R:R 4.0 means a good trade."',
          right: 'It means the target is four times further than the stop. In this book the ' +
            'median planned R:R ran 6.4 against a median best-case excursion of 1.53R — a high ' +
            'ratio is often the signature of a target that was out of reach. That is why ' +
            'targets are now capped at 3R.'
        },
        {
          wrong: '"The why line is marketing."',
          right: 'It is generated from the facts the setup used. If it is wrong, that is a bug ' +
            'worth reporting, not a phrase worth ignoring.'
        }
      ]
    }
  ];

  /* ═══════════════════════════════════════════════════════════════════════
     5. first-run orientation

     Four steps, per SPEC-confirmed-entry.md §5.2, rewritten against what this
     build actually does. Step 2 carries the load: right now silence reads as a
     fault, and it is the filter working.
     ═══════════════════════════════════════════════════════════════════════ */

  const ORIENT_KEY = 'ss.orientation.v1';
  /* The last line the operator reads on their first visit. It is the handle on
     everything else: one hover teaches one word, and there are 47 of them. */
  const ORIENT_CLOSER = 'Everything underlined explains itself — hover it.';
  const ORIENT_STEPS = [
    {
      title: 'Pick your market',
      html: '<p>Crypto, on one venue at a time. The venue is not cosmetic: a <b>spot</b> ' +
        'account is long-only at 1x, so every short the playbook finds is refused before it ' +
        'is sized. A <b>perpetuals</b> account can short and can use leverage, and pays ' +
        t('funding', 'funding') + ' while a position is held.</p>' +
        '<p>The universe is picked by the scanner, not by you: a symbol has to have enough ' +
        'history and enough volume before it is watched at all.</p>'
    },
    {
      title: 'The scanner watches',
      quiet: true,
      html: '<p>It re-reads the market on a loop and only speaks up when something is ' +
        'genuinely tradeable: a zone touched, in a matching ' + t('regime', 'regime') + ', ' +
        'confirmed by a candle that closed back out of it, clearing the R:R and cost gates, ' +
        'and approved by the risk authority.</p>' +
        '<p><b>Quiet is normal — expect roughly one setup a day.</b> An empty deck almost ' +
        'always means the market was in a state with no playbook, not that anything is ' +
        'broken. Diagnostics shows exactly where candidates died, and Learn chapter 5 ' +
        'explains why RANGE has no play.</p>'
    },
    {
      title: 'When a setup appears',
      html: '<p>The card names its reasoning, its bracket and its risk: what the ' +
        t('regime', 'regime') + ' was, which zone, what confirmed it, the ' +
        t('entry', 'entry') + ', ' + t('tp', 'target') + ' and ' + t('sl', 'stop') + ', and ' +
        'the ' + t('rr', 'R:R') + '.</p>' +
        '<p>Open it on the Chart to move any of the three levels. Size recalculates from the ' +
        'stop as you drag, so you can see immediately what a wider stop costs you in position ' +
        'size. Chapter 8 of Learn walks the card line by line.</p>'
    },
    {
      title: 'Nothing here is real',
      html: '<p>This is ' + t('paper', 'paper') + ' trading: the same code, the same ' +
        'decisions, no real orders. Live order submission is locked, and it stays locked ' +
        'until the forward record earns it.</p>' +
        '<p>Everything on Results is measured from the current ' + t('baseline', 'baseline') +
        ' forward. Results from an older engine version are kept but never mixed in.</p>'
    }
  ];

  /* ═══════════════════════════════════════════════════════════════════════
     6. DOM — mounting. Everything above this line runs under node.
     ═══════════════════════════════════════════════════════════════════════ */

  function mountWidget(host, spec) {
    /* A widget that throws must say so. A silent blank rectangle in the middle
       of a lesson is indistinguishable from a lesson that has no widget. */
    const state = {
      spec: spec, index: 0,
      param: spec.param ? spec.param.value : null,
      el: host,
      steps: spec.steps
    };

    host.className = 'ss-wgt';
    host.innerHTML =
      '<div class="ss-wgt-head">' +
      '<span class="ss-wgt-title">' + esc(spec.title) + '</span>' +
      '<span class="ss-wgt-cap">' + esc(spec.caption || '') + '</span></div>' +
      '<div class="ss-wgt-stage' + (spec.layout === 'twin' ? ' twin' : '') + '"></div>' +
      (spec.param
        ? '<div class="ss-wgt-param"><label for="' + spec.id + '-p">' + esc(spec.param.label) +
        '</label><input id="' + spec.id + '-p" type="range" min="' + spec.param.min +
        '" max="' + spec.param.max + '" step="' + spec.param.step + '" value="' +
        spec.param.value + '"><output></output></div>'
        : '') +
      '<div class="ss-wgt-steps"></div>' +
      '<div class="ss-wgt-note"></div>';

    const stage = host.querySelector('.ss-wgt-stage');
    const noteEl = host.querySelector('.ss-wgt-note');
    const stepsEl = host.querySelector('.ss-wgt-steps');
    const slider = spec.param ? host.querySelector('input[type=range]') : null;
    const out = spec.param ? host.querySelector('output') : null;

    spec.steps.forEach((s, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'ss-step';
      b.textContent = s.label;
      b.addEventListener('click', () => state.go(i));
      stepsEl.appendChild(b);
    });
    const nav = document.createElement('span');
    nav.className = 'ss-step-nav';
    ['‹ PREV', 'NEXT ›'].forEach((label, k) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'ss-step';
      b.textContent = label;
      b.addEventListener('click', () => state.go(state.index + (k ? 1 : -1)));
      nav.appendChild(b);
    });
    stepsEl.appendChild(nav);

    function draw() {
      try {
        stage.innerHTML = spec.svg(state.index, state.param);
      } catch (err) {
        stage.innerHTML = '<div class="ss-wgt-fail">This widget failed to draw: ' +
          esc(err && err.message ? err.message : String(err)) +
          '<br>The lesson text above still stands; the diagram does not.</div>';
      }
      noteEl.innerHTML = spec.steps[state.index].note || '';
      Array.prototype.forEach.call(stepsEl.querySelectorAll('button'), (b, i) => {
        if (i < spec.steps.length) b.classList.toggle('on', i === state.index);
      });
      if (out) out.textContent = Number(state.param).toFixed(1) + ' ' + (spec.param.unit || '');
    }

    state.go = function (i) {
      state.index = clampStep(spec, i);
      /* a step may pin the parameter — "a near stop" is not a step you can read
         while the slider says something else */
      const pinned = spec.steps[state.index].param;
      if (pinned != null) {
        state.param = pinned;
        if (slider) slider.value = String(pinned);
      }
      draw();
      return state;
    };
    state.next = () => state.go(state.index + 1);
    state.prev = () => state.go(state.index - 1);
    state.setParam = function (v) {
      state.param = Number(v);
      if (slider) slider.value = String(v);
      draw();
      return state;
    };

    if (slider) slider.addEventListener('input', e => state.setParam(e.target.value));
    draw();
    return state;
  }

  function chapterHTML(ch) {
    return '<section class="lsn-ch" id="lsn-' + ch.id + '">' +
      '<div class="lsn-ch-head">' +
      '<span class="lsn-ch-n">' + String(ch.n).padStart(2, '0') + '</span>' +
      '<span class="lsn-ch-t">' + esc(ch.title) + '</span>' +
      '<span class="lsn-ch-q">' + esc(ch.question) + '</span>' +
      '<span class="lsn-src">' + esc(ch.source) + '</span>' +
      '</div>' +
      '<div class="lsn-sec"><h3>// CORE MECHANIC</h3>' + ch.mechanic + '</div>' +
      '<div class="lsn-sec lsn-why"><h3>// WHY IT WORKS</h3>' + ch.why + '</div>' +
      '<div class="lsn-sec"><h3>// COMMON MISTAKES</h3>' +
      '<div class="lsn-mistakes">' + ch.mistakes.map(m =>
        '<button type="button" class="lsn-flip" aria-expanded="false">' +
        '<span class="lsn-flip-tag">tap to see why</span>' +
        '<span class="lsn-flip-face lsn-flip-front">' + esc(m.wrong) + '</span>' +
        '<span class="lsn-flip-face lsn-flip-back">' + m.right + '</span></button>').join('') +
      '</div></div>' +
      '<div class="lsn-sec"><h3>// TRY IT</h3><div data-widget="' + ch.widget + '"></div></div>' +
      '</section>';
  }

  function bootLearn() {
    const root = document.getElementById('learnRoot');
    if (!root) return;                       // surface not present in this build

    root.innerHTML =
      '<div class="lsn">' +
      '<nav class="lsn-rail" aria-label="chapters">' +
      '<span class="lsn-rail-cap">chapters</span>' +
      CHAPTERS.map(c => '<a href="#lsn-' + c.id + '" data-ch="' + c.id + '"><i>' +
        String(c.n).padStart(2, '0') + '</i>' + esc(c.title) + '</a>').join('') +
      '</nav>' +
      '<div class="lsn-doc">' +
      '<div class="lsn-preamble">' +
      '<p>Eight chapters, all the same shape: <b>what the engine does</b>, <b>why that ' +
      'mechanism works</b>, <b>what people get wrong</b>, and something you can take apart. ' +
      'No prior trading knowledge is assumed anywhere on this page.</p>' +
      '<p>Every chapter names the engine file and the algo version it was written against. ' +
      'If a version here is behind the one in the status bar, <b>the chapter is stale</b> — ' +
      'said out loud, because a lesson that quietly describes a rule the code no longer ' +
      'implements is worse than no lesson.</p>' +
      '<p>Every underlined word explains itself. Hover it, or tap it on a phone.</p>' +
      '</div>' +
      CHAPTERS.map(chapterHTML).join('') +
      '</div></div>';

    /* widgets */
    CHAPTERS.forEach(ch => {
      const host = root.querySelector('[data-widget="' + ch.widget + '"]');
      if (!host) return;
      const spec = WIDGETS[ch.widget];
      if (!spec) {
        host.className = 'ss-wgt-fail';
        host.textContent = 'Widget "' + ch.widget + '" is missing from this build.';
        return;
      }
      mountWidget(host, spec);
    });

    /* flip cards */
    root.addEventListener('click', e => {
      const card = e.target.closest('.lsn-flip');
      if (!card) return;
      const open = card.classList.toggle('open');
      card.setAttribute('aria-expanded', open ? 'true' : 'false');
      card.querySelector('.lsn-flip-tag').textContent = open ? 'why it is wrong' : 'tap to see why';
    });

    /* rail: click scrolls, scroll highlights */
    const rail = root.querySelector('.lsn-rail');
    const setActive = id =>
      rail.querySelectorAll('a').forEach(a => a.classList.toggle('on', a.dataset.ch === id));

    rail.addEventListener('click', e => {
      const a = e.target.closest('a[data-ch]');
      if (!a) return;
      e.preventDefault();
      const target = document.getElementById('lsn-' + a.dataset.ch);
      if (!target) return;
      /* light it now rather than waiting for the smooth scroll to settle — a
         click with no acknowledgement for half a second reads as a dead link */
      setActive(a.dataset.ch);
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    /* Scroll spy. Deliberately NOT an IntersectionObserver: the chapters live
       inside `.stage`, which is the scroll container, and the surface starts at
       display:none — an observer set up against a hidden subtree only fires
       once the page is compositing, which left the rail dead on first paint.
       Reading positions on scroll is cheaper to reason about and always right. */
    const sections = Array.prototype.slice.call(root.querySelectorAll('.lsn-ch'));
    const scroller = root.closest('.stage') || document.scrollingElement || document.body;
    let queued = false;
    function spy() {
      queued = false;
      const anchor = (scroller.getBoundingClientRect
        ? scroller.getBoundingClientRect().top : 0) + 120;
      let active = sections[0];
      for (const s of sections) {
        if (s.getBoundingClientRect().top <= anchor) active = s; else break;
      }
      if (active) setActive(active.id.replace('lsn-', ''));
    }
    /* Throttled on a timer rather than requestAnimationFrame. rAF is suspended
       whenever the page is not being painted — a background tab, or a window
       the operator has covered — and a rail that silently stops tracking is
       exactly the kind of "looks broken" this surface exists to remove. */
    const onScroll = () => {
      if (queued) return;
      queued = true;
      setTimeout(spy, 60);
    };
    scroller.addEventListener('scroll', onScroll, { passive: true });
    addEventListener('resize', onScroll, { passive: true });
    /* light the first chapter immediately — a rail with nothing lit reads as
       broken navigation rather than as "you are at the top" */
    spy();
  }

  /* ─────────── orientation ─────────── */

  let storageOk = true;
  function seen() {
    try { return localStorage.getItem(ORIENT_KEY) === 'done'; }
    catch (e) { storageOk = false; return false; }
  }
  function markSeen(v) {
    try { v ? localStorage.setItem(ORIENT_KEY, 'done') : localStorage.removeItem(ORIENT_KEY); }
    catch (e) { storageOk = false; }
  }

  function renderOrient(root, open) {
    if (!open) {
      root.innerHTML = '<div class="orient-min">' +
        '<button type="button" class="btn" id="orientOpen" ' +
        'title="show the four-step orientation again">? &nbsp;Orientation</button></div>';
      root.querySelector('#orientOpen').addEventListener('click', () => {
        markSeen(false);
        renderOrient(root, true);
      });
      return;
    }
    root.innerHTML =
      '<div class="orient">' +
      '<div class="orient-head">' +
      '<h2>Start here</h2>' +
      '<span class="orient-sub">four steps · about a minute</span>' +
      '<button type="button" class="btn orient-x" id="orientDismiss">Got it</button>' +
      '</div>' +
      '<div class="orient-body">' +
      ORIENT_STEPS.map((s, i) =>
        '<div class="orient-step' + (s.quiet ? ' quiet' : '') + '">' +
        '<span class="orient-n">STEP ' + (i + 1) + '</span>' +
        '<h3>' + esc(s.title) + '</h3>' + s.html + '</div>').join('') +
      '</div>' +
      '<div class="orient-foot">' +
      '<p><b>' + esc(ORIENT_CLOSER) + '</b> The Learn surface goes further: eight chapters on ' +
      'what the engine does and why it works.</p>' +
      '<span class="orient-acts">' +
      '<a class="btn" href="#learn">Open Learn</a>' +
      '<button type="button" class="btn btn-cyan" id="orientDone">Got it</button>' +
      '</span></div>' +
      (storageOk ? '' :
        '<div class="orient-warn">This browser is blocking local storage, so dismissing ' +
        'this card will not stick — it will be back on the next reload.</div>') +
      '</div>';
    const close = () => { markSeen(true); renderOrient(root, false); };
    root.querySelector('#orientDismiss').addEventListener('click', close);
    root.querySelector('#orientDone').addEventListener('click', close);
  }

  function bootOrient() {
    const root = document.getElementById('orientRoot');
    if (!root) return;
    const wasSeen = seen();          // called first so `storageOk` is known
    renderOrient(root, !wasSeen);
  }

  /* ─────────── stylesheet, then boot ─────────── */

  function boot() {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = '/static/lessons.css?v=1';
    /* Loud fallback: unstyled lesson content is readable but looks broken, and
       "looks broken" is precisely the impression this whole surface exists to
       remove. Say which file is missing. */
    css.addEventListener('error', () => {
      const r = document.getElementById('learnRoot');
      if (r) r.insertAdjacentHTML('afterbegin',
        '<div style="border:1px solid var(--amber);background:rgba(255,194,102,.08);' +
        'color:var(--amber);border-radius:10px;padding:12px;margin-bottom:14px;' +
        'font-family:var(--f-mono);font-size:11px">' +
        '/static/lessons.css did not load. The chapters below are unstyled, not broken.</div>');
    });
    document.head.appendChild(css);

    try { bootLearn(); }
    catch (err) {
      const r = document.getElementById('learnRoot');
      if (r) r.innerHTML = '<div class="empty">Learn failed to render: ' +
        esc(err && err.message ? err.message : String(err)) + '</div>';
    }
    try { bootOrient(); }
    catch (err) {
      /* orientation is additive — a failure here must not blank Command */
      const r = document.getElementById('orientRoot');
      if (r) r.innerHTML = '<div class="orient-min"><span class="t-mono" ' +
        'style="color:var(--amber)">orientation failed to render: ' +
        esc(err && err.message ? err.message : String(err)) + '</span></div>';
    }
  }

  const API = {
    chapters: CHAPTERS,
    widgets: WIDGETS,
    orientation: {
      steps: ORIENT_STEPS,
      key: ORIENT_KEY,
      closer: ORIENT_CLOSER,
      isDismissed: seen,
      open: function () {
        const r = typeof document !== 'undefined' && document.getElementById('orientRoot');
        if (r) { markSeen(false); renderOrient(r, true); }
      },
      dismiss: function () {
        const r = typeof document !== 'undefined' && document.getElementById('orientRoot');
        markSeen(true);
        if (r) renderOrient(r, false);
      }
    },
    /* exported so tests can hold the JS port to the same truth table the Python
       classifier is written from */
    classifyRegime: classifyRegime,
    zoneQuality: zoneQuality,
    zoneFreshness: zoneFreshness,
    zoneStrength: zoneStrength,
    mountWidget: mountWidget
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else root.SSLessons = API;

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
    else boot();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
