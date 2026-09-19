"""Read-only, manifest-pinned explanations. Never decides or places a trade."""
import json
from decimal import Decimal

from engine import costs, htfcontext, importer, setups, store, zones
from engine.swings import compute_atr


def mini_chart(candles, bottom, top, boundary):
    """Decimal geometry keeps the browser a renderer, not a price authority."""
    if not candles or bottom is None or top is None:
        return None
    candles = candles[-16:]
    low = min(Decimal(bottom), *(Decimal(c['low']) for c in candles))
    high = max(Decimal(top), *(Decimal(c['high']) for c in candles))
    span = high - low or Decimal('1')
    def y(price):
        return str((Decimal(132) - (Decimal(price)-low)/span*108).quantize(Decimal('.01')))
    bars = []
    for i, candle in enumerate(candles):
        op, close = Decimal(candle['open']), Decimal(candle['close'])
        bars.append(dict(x=20+i*18, high=y(candle['high']), low=y(candle['low']),
                         body_top=y(max(op, close)), body_height=str(max(Decimal('1'), abs(Decimal(y(op))-Decimal(y(close))))),
                         rising=close>=op))
    return dict(bars=bars, zone_y=y(top), zone_height=str(Decimal(y(bottom))-Decimal(y(top))),
                boundary_y=y(boundary), last_y=y(candles[-1]['close']))


class Reader:
    def __init__(self, con, now):
        self.con, self.now = con, now
        self.candles = {}

    def guide(self, setup_id):
        record = self.con.execute(
            "SELECT symbol,tf,payload,confirmed_at FROM facts WHERE kind='setup' AND algo_version=? "
            "AND json_extract(payload,'$.setup_id')=? ORDER BY confirmed_at DESC,id DESC LIMIT 1",
            (setups.SETUP_VERSION, setup_id)).fetchone()
        if not record:
            return None
        symbol, tf, raw, updated = record
        payload = json.loads(raw)
        manifest = store.get_manifest(self.con, payload.get('manifest_hash') or '')
        manifest = manifest or {}
        inputs = manifest.get('inputs', {})
        version = inputs.get('zone')
        # The fallback only supplies chart bounds. Rule/progress claims below
        # require the recorded manifest and explicitly report missing evidence.
        zone = self.con.execute(
            "SELECT payload FROM facts WHERE kind='zone' AND symbol=? AND tf=? AND algo_version=? "
            "AND json_extract(payload,'$.zone_id')=? AND json_extract(payload,'$.event')='CREATED' "
            "ORDER BY confirmed_at DESC,id DESC LIMIT 1",
            (symbol, tf, version or zones.ZONE_VERSION, payload.get('zone_id'))).fetchone()
        bounds = json.loads(zone[0]) if zone else {}
        bottom, top = bounds.get('bottom'), bounds.get('top')
        long = payload.get('direction') == 'LONG'
        boundary = top if long else bottom
        seconds = importer.TF_SECONDS.get(tf)
        result = dict(setup_id=setup_id, updated_at=updated, as_of=self.now, state=payload.get('state'),
                      zone_bottom=bottom, zone_top=top, confirmation_boundary=boundary,
                      confirmation_deadline=payload.get('confirm_deadline_ts'), entry_deadline=payload.get('expires_at_ts'),
                      stop=payload.get('sl'), cancel_reason=payload.get('cancel_reason'), available=False,
                      confirmation='The recorded confirmation rules are unavailable for this setup.',
                      skip_if='The zone-break threshold includes a changing volatility/tick buffer; the zone edge alone is not that threshold.')
        if not (version and seconds and bottom is not None and top is not None and
                manifest.get('confirm_max_bars') and manifest.get('rejection_fraction') is not None):
            result['unavailable_reason'] = 'Recorded rules or area prices are missing. Confirmation progress cannot be verified.'
            return result
        bars = int(manifest['confirm_max_bars'])
        fraction = Decimal(manifest['rejection_fraction'])
        band = importer.price_text((1-fraction)*100)
        edge, end = ('above', 'top') if long else ('below', 'bottom')
        result.update(available=True, direction=payload.get('direction'), timeframe=tf,
                      intended_trade=('Long · Support bounce' if long else 'Short · Resistance rejection'),
                      confirmation=f'A completed {tf} candle must touch the area, close strictly {edge} {boundary}, and finish in the {end} {band}% of its own range.',
                      conditions=[f"{'Low at or below' if long else 'High at or above'} {boundary}",
                                  f'Close strictly {edge} {boundary}', f'Close in the {end} {band}% of that candle’s range'],
                      max_followup_bars=bars,
                      expiry_action='Cancel this setup if no candle confirms in time. It does not remain ready for entry.',
                      after_confirmation='A confirming candle still needs a valid trade plan, acceptable costs and account risk checks.')
        if version == zones.ZONE_VERSION:
            pct = importer.price_text(zones.TOL_ATR*100)
            result['skip_if'] = (f"A completed candle closes {'below '+bottom if long else 'above '+top}, beyond the area by more than the larger of one price tick or {pct}% of the candle’s average trading range (ATR). This buffer changes with each candle.")
        else:
            result['skip_if'] = 'The recorded zone must break before confirmation. Its buffered break rule is unavailable for this older zone version.'
        candles = self._candles(symbol, tf, seconds)
        last = candles[-1] if candles else None
        result.update(last_price=last['close'] if last else None,
                      last_closed_at=last['open_ts']+seconds if last else None,
                      data_stale=not last or last['open_ts']+2*seconds <= self.now,
                      mini_chart=mini_chart(candles, bottom, top, boundary))
        deadline = payload.get('confirm_deadline_ts')
        if payload.get('state') == 'CONFIRMING' and deadline:
            touch_close = deadline-bars*seconds
            available = {c['open_ts']+seconds for c in candles}
            steps = [dict(closes_at=touch_close+(i+1)*seconds,
                          complete=touch_close+(i+1)*seconds in available) for i in range(bars)]
            result.update(steps=steps, completed_followup_bars=sum(s['complete'] for s in steps),
                          touch_close=touch_close, window_ended=self.now>=deadline,
                          next_close_at=next((s['closes_at'] for s in steps if s['closes_at']>self.now), None),
                          missing_candles=any(not s['complete'] and s['closes_at']<=self.now for s in steps))
        # Only describe regime evidence that was known when this setup was
        # recorded. Do not turn TRANSITION into an invented directional trend.
        context = []
        for timeframe in (tf, setups.HTF_LADDER.get(tf)):
            if not timeframe:
                continue
            regime = self.con.execute(
                "SELECT payload FROM facts WHERE symbol=? AND tf=? AND kind='regime' AND algo_version=? "
                "AND confirmed_at<=? ORDER BY confirmed_at DESC,id DESC LIMIT 1",
                (symbol, timeframe, inputs.get('regime'), updated)).fetchone()
            if not regime:
                continue
            p = json.loads(regime[0])
            words = {'BULL_TREND':'bullish structure', 'BEAR_TREND':'bearish structure',
                     'WEAKENING_BULL':'weakening bullish structure', 'WEAKENING_BEAR':'weakening bearish structure',
                     'RANGE':'mixed structure / range'}
            description = words.get(p.get('regime'))
            if p.get('regime') == 'TRANSITION':
                direction = (p.get('evidence', {}).get('last_break') or {}).get('direction')
                description = {'BULL':'structure turning bullish', 'BEAR':'structure turning bearish'}.get(direction, 'structure changed; direction not recorded')
            if description:
                context.append(f'{timeframe} {description}')
        result['market_context'] = '; '.join(context) if context else 'Directional structure evidence was not recorded.'
        return result

    def evidence(self, setup_id, levels=True):
        """What supports and conflicts with this trade, for the operator to judge.

        Three parts, never combined into a score: the confluence the engine
        RECORDED when the setup confirmed, the checks it actually REQUIRED, and
        the higher-timeframe picture NOW. There is deliberately no total, no
        count of green marks and no ranking — see `confluence_rows`.
        """
        record = self.con.execute(
            "SELECT symbol,tf,payload,confirmed_at FROM facts WHERE kind='setup' AND algo_version=? "
            "AND json_extract(payload,'$.setup_id')=? ORDER BY confirmed_at DESC,id DESC LIMIT 1",
            (setups.SETUP_VERSION, setup_id)).fetchone()
        if not record:
            return None
        symbol, tf, raw, _updated = record
        payload = json.loads(raw)
        direction = payload.get('direction')
        seconds = importer.TF_SECONDS.get(tf)
        out = dict(setup_id=setup_id, symbol=symbol, timeframe=tf, direction=direction,
                   strategy=payload.get('strategy'), state=payload.get('state'),
                   note='Recorded evidence, not predictions. None of these factors has '
                        'been graded against results yet, so no score is given.')
        if direction not in ('LONG', 'SHORT') or not seconds:
            out['confluence_reason'] = 'This setup has no recorded direction or timeframe.'
            return out

        recent = self._candles(symbol, tf, seconds)
        atr_now = _last_atr(recent)
        price = recent[-1]['close'] if recent else None

        # Present from VALIDATED onward: later states (EXPIRED, and the rest)
        # carry the confirmation-time block forward unchanged. Keying on the
        # block rather than on state == VALIDATED is what keeps the panel on a
        # setup the operator is reviewing after its window closed.
        if isinstance(payload.get('confluence'), dict):
            out['factors'] = confluence_rows(payload)
            out['required'], out['economics'] = self._plan_checks(symbol, tf, seconds, payload)
            out['recorded_context'] = _recorded_context(payload)
        else:
            # Confluence is written only when a setup confirms — before that
            # there is no entry, stop or target for it to be ABOUT. Say so
            # rather than invent an early reading.
            out['confluence_reason'] = ('Recorded when this setup confirms. Until a candle '
                                        'confirms it there is no trade plan to measure.')

        if price is None:
            out['higher_timeframe'] = None
            out['higher_timeframe_reason'] = 'No completed candles to measure from.'
            return out
        htf = htfcontext.read(self.con, symbol, tf, direction, price, self.now,
                              atr=atr_now, levels=levels)
        htf['price'] = str(price)
        # Reversal fades a move at a zone, so counter-trend is its NORMAL case.
        # Say that beside the plain counter-trend reading, so it is not read as
        # an alarm — but never beside the running-move case, which is the one
        # worth an alarm.
        if payload.get('strategy') == 'REVERSAL' and htf['stance']['label'] == 'COUNTER_TREND':
            htf['stance']['strategy_note'] = 'Reversal trades are counter-trend by design; this is its normal case.'
        out['higher_timeframe'] = htf
        return out

    def _candles(self, symbol, tf, seconds):
        key = (symbol, tf)
        if key not in self.candles:
            cursor = self.con.execute(
                'SELECT * FROM candles WHERE symbol=? AND tf=? AND open_ts+?<=? ORDER BY open_ts DESC LIMIT 64',
                (symbol, tf, seconds, self.now))
            names = [column[0] for column in cursor.description]
            self.candles[key] = [dict(zip(names, c)) for c in cursor][::-1]
        return self.candles[key]

    def _plan_checks(self, symbol, tf, seconds, payload):
        """The gates this plan passed, and reward/risk before and after costs.

        Costs come from `costs.estimated_round_trip_cost` — the function the
        engine's own economics gate calls — so this is that authority read at
        the confirming bar, not a second cost model. The ATR is rebuilt from
        the stored candles up to that bar, so the figure is an estimate that
        can differ slightly from the gate's; it is labelled as one, and a
        VALIDATED setup is reported as having passed regardless, because it did.
        """
        entry, sl, tp = (_dec(payload.get(k)) for k in ('entry', 'sl', 'tp'))
        required = [dict(check='A completed candle confirmed the rejection', passed=True,
                         value=payload.get('confirmed_bar_ts'))]
        economics = dict(rr_gross=payload.get('rr'), minimum_rr=str(setups.MIN_RR))
        required.append(dict(check=f'Reward at least {setups.MIN_RR}× the risk', passed=True,
                             value=payload.get('rr')))
        if None in (entry, sl, tp) or entry == sl:
            economics['reason'] = 'The recorded plan is incomplete; costs cannot be estimated.'
            return required, economics
        rows = self.con.execute(
            'SELECT high,low,close,open_ts FROM candles WHERE symbol=? AND tf=? AND open_ts<=? '
            'ORDER BY open_ts DESC LIMIT 300', (symbol, tf, payload.get('confirmed_bar_ts') or 0)).fetchall()
        atr = _last_atr([dict(high=r[0], low=r[1], close=r[2]) for r in rows[::-1]])
        risk, reward = abs(entry - sl), abs(tp - entry)
        if atr is None:
            economics['reason'] = 'Not enough candle history at confirmation to estimate costs.'
            return required, economics
        cost = costs.estimated_round_trip_cost(entry, atr, costs.profile_for(symbol),
                                               symbol=symbol, tf_seconds=seconds)
        economics.update(
            estimated_cost=importer.price_text(cost),
            rr_net=str(((reward - cost) / risk).quantize(Q2)),
            # The cost in the operator's unit, R. Computed here so the browser
            # never divides one money figure by another (rule 9).
            cost_r=str((cost / risk).quantize(Q2)),
            risk_to_cost=str((risk / cost).quantize(Q2)) if cost else None,
            minimum_risk_to_cost=str(setups.MIN_RISK_COST_MULT),
            basis='Estimated fees, slippage and funding for the expected hold, at the confirming candle.')
        required.append(dict(check=f'Risk at least {setups.MIN_RISK_COST_MULT}× the estimated costs',
                             passed=True, value=economics['risk_to_cost']))
        return required, economics


Q2 = Decimal('0.01')

#: The states a factor can be in. Five, and never collapsed into a number.
SUPPORTS, CONFLICTS, NEUTRAL, UNAVAILABLE, INFO = (
    'SUPPORTS', 'CONFLICTS', 'NEUTRAL', 'UNAVAILABLE', 'INFO')


def _dec(value):
    try:
        return Decimal(str(value)) if value is not None else None
    except ArithmeticError:
        return None


def _last_atr(candles):
    if len(candles) < 15:
        return None
    series = compute_atr(candles)
    return series[-1] if series else None


def _tf_word(tf):
    return 'daily' if tf == '1D' else (tf or 'higher timeframe')


def _recorded_context(payload):
    """What the timeframe above looked like at the confirming candle."""
    phase = payload.get('htf_phase')
    alignment = (payload.get('bias') or {}).get('alignment')
    return dict(htf_phase=phase,
                words=htfcontext.PHASE_WORDS.get(phase) if phase else None,
                alignment=alignment,
                alignment_words={'WITH': 'with this trade', 'AGAINST': 'against this trade',
                                 'MIXED': 'higher timeframes disagreed', 'FLAT': 'no trend above',
                                 'UNKNOWN': 'not enough history'}.get(alignment))


def confluence_rows(payload):
    """Each piece of recorded confluence as its own line. Never a total.

    WHY NO SCORE. `setups.confluence_block` emits `score: 0` on purpose: no
    factor has earned a weight until `factorstats` grades it. A panel that
    added these up — or counted how many are filled in, which is what the
    retired `opportunities._quality` coverage term did — would present an
    ungraded guess as a measurement. This system has twice shipped a filter
    that looked sensible and flipped sign out of sample. So each line says
    what was recorded and which way it points, and the operator judges.

    Only the factors with a direction get SUPPORTS / CONFLICTS. Zone strength,
    bars since the last break and target distance are INFO: recorded, shown,
    not judged.
    """
    c = payload['confluence']
    short = payload.get('direction') == 'SHORT'
    rows = []

    comp = c.get('htf_composite')
    htf = _tf_word(c.get('htf_timeframe'))
    rows.append(dict(key='htf', factor=f'{htf} trend at confirmation',
                     state={'WITH': SUPPORTS, 'AGAINST': CONFLICTS, 'FLAT': NEUTRAL}.get(comp, UNAVAILABLE),
                     value={'WITH': 'with this trade', 'AGAINST': 'against this trade',
                            'FLAT': 'no trend'}.get(comp, 'not recorded'),
                     detail='The structural trend one timeframe up when the setup confirmed.'))

    pd = c.get('premium_discount')
    if pd is None:
        rows.append(dict(key='range_location', factor='Where price sits in the recent range',
                         state=UNAVAILABLE, value='no complete swing range yet',
                         detail='Needs a recent swing high and swing low to measure against.'))
    else:
        pd = int(pd)
        good = pd > 50 if short else pd < 50
        state = NEUTRAL if pd == 50 else (SUPPORTS if good else CONFLICTS)
        rows.append(dict(key='range_location', factor='Where price sits in the recent range',
                         state=state, value=f'{pd}% of the way up',
                         detail=('Shorts sell the upper half of the range, longs buy the lower half.')))

    vr = c.get('volume_expansion')
    if vr is None:
        rows.append(dict(key='volume', factor='Volume on the confirming candle', state=UNAVAILABLE,
                         value='fewer than 20 earlier candles',
                         detail='Needs 20 earlier candles to compare against.'))
    else:
        hot = Decimal(str(vr)) > setups.VOLUME_HOT_RATIO
        rows.append(dict(key='volume', factor='Volume on the confirming candle',
                         state=SUPPORTS if hot else NEUTRAL, value=f'{vr}× its 20-candle average',
                         detail=f'Above {setups.VOLUME_HOT_RATIO}× counts as elevated.'))

    sweep = c.get('sweep_nearby')
    side = 'highs' if short else 'lows'
    rows.append(dict(key='sweep', factor=f'Liquidity taken beyond recent {side}',
                     state=UNAVAILABLE if sweep is None else (SUPPORTS if sweep else NEUTRAL),
                     value='not recorded' if sweep is None else ('yes, just before' if sweep else 'no recent sweep'),
                     detail=f'Price ran recent {side} and came back before the setup.'))

    for key, factor, value, detail in (
            ('zone_strength', 'Zone strength', c.get('zone_strength'),
             'Recorded for every setup. Shown for context; not graded.'),
            ('bars_since_break', 'Candles since the last structure break', c.get('bars_since_break'),
             'How fresh the break this setup follows is.'),
            ('target_distance', 'Structure target distance', (
                None if _dec(c.get('target_distance_r')) is None
                else f"{_dec(c['target_distance_r']).quantize(Q2)} R"),
             'How far the nearest opposing structure is, in units of the risk.')):
        rows.append(dict(key=key, factor=factor, state=INFO if value is not None else UNAVAILABLE,
                         value='not recorded' if value is None else str(value), detail=detail))
    return rows
