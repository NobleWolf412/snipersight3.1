"""Read-only, manifest-pinned explanations. Never decides or places a trade."""
import json
from decimal import Decimal

from engine import importer, setups, store, zones


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
        key = (symbol, tf)
        if key not in self.candles:
            cursor = self.con.execute(
                'SELECT * FROM candles WHERE symbol=? AND tf=? AND open_ts+?<=? ORDER BY open_ts DESC LIMIT 64',
                (symbol, tf, seconds, self.now))
            names = [column[0] for column in cursor.description]
            self.candles[key] = [dict(zip(names, c)) for c in cursor][::-1]
        candles = self.candles[key]
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
