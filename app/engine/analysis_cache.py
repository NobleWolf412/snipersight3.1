"""Process-local memo of successful, deterministic descriptive engine runs.

No trade, expiry, quality or account decision is cached. Candle content is
hashed, not just its timestamp: repairing an old bar must invalidate the run.
"""
import hashlib
import json

from . import (fvg, liquidity, ma, momentum, ranges, regime, research,
               researchsignals, sessions, setups, store, structure, swings,
               volatility, volprofile, volume, zones)


def dependencies():
    swing = (('swing', swings.SWING_VERSION),)
    return {
        swings: (('structure', swings.PRIOR_STRUCTURE), ('liquidity', swings.PRIOR_LIQ)),
        structure: swing, zones: swing, liquidity: swing,
        regime: (('structure', structure.STRUCTURE_VERSION),),
        ranges: swing, momentum: swing,
        research: (('structure', structure.STRUCTURE_VERSION),
                   ('liquidity', liquidity.LIQ_VERSION),
                   ('ma', ma.MA_VERSION), ('momentum', momentum.MOMENTUM_VERSION)),
        researchsignals: (('setup', setups.SETUP_VERSION),
                          ('order_block', research.ORDER_BLOCK_VERSION),
                          ('structure_sequence', research.STRUCTURE_SEQUENCE_VERSION),
                          ('stoch_rsi', research.STOCH_RSI_VERSION),
                          ('hidden_divergence', research.HIDDEN_DIVERGENCE_VERSION),
                          ('open_interest_signal', research.OPEN_INTEREST_SIGNAL_VERSION)),
        ma: (), volatility: (), volume: (), fvg: (), volprofile: (), sessions: (),
    }


OUTPUT_KIND = {swings: 'swing', structure: 'structure', zones: 'zone',
               liquidity: 'liquidity', regime: 'regime', ranges: 'range',
               momentum: 'momentum', ma: 'ma', volatility: 'volatility',
               volume: 'volume', fvg: 'fvg', volprofile: 'volprofile', sessions: 'sessions',
               research: ('order_block', 'structure_sequence', 'stoch_rsi',
                          'hidden_divergence'),
               researchsignals: 'research_snapshot'}


class AnalysisCache:
    def __init__(self):
        self.successful = {}
        self.pending = {}
        self.connection = None
        self.candle_hashes = {}
        self.skipped = 0
        self.executed = 0

    def begin_symbol(self):
        self.candle_hashes = {}

    def signature(self, con, mod, symbol, tf):
        if self.connection is not con:
            self.connection = con
            self.successful.clear()
            self.pending.clear()
            self.candle_hashes.clear()
        deps = dependencies().get(mod)
        if deps is None:
            return None
        key = (symbol, tf)
        if key not in self.candle_hashes:
            rows = [dict(row) for row in store.get_candles(con, symbol, tf)]
            # imported_at changes on an identical re-import without changing
            # an engine's inputs. All price/volume/source values remain exact.
            for row in rows:
                row.pop('imported_at', None)
            self.candle_hashes[key] = hashlib.sha256(
                json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        versions = tuple(sorted((k, v) for k, v in vars(mod).items()
                                if k.endswith('_VERSION') and isinstance(v, str)))
        revisions = []
        for kind, version in deps:
            revisions.append(tuple(con.execute(
                'SELECT COUNT(*),COALESCE(MAX(id),0) FROM facts WHERE symbol=? AND tf=? AND kind=? AND algo_version=?',
                (symbol, tf, kind, version)).fetchone()))
        # Facts are append-only. Count/max-id also detect removal/rebuild of
        # this engine's output by maintenance outside this process.
        output_kinds = OUTPUT_KIND[mod]
        if isinstance(output_kinds, str):
            output_kinds = (output_kinds,)
        output = tuple(tuple(con.execute(
            'SELECT COUNT(*),COALESCE(MAX(id),0) FROM facts WHERE symbol=? AND tf=? AND kind=?',
            (symbol, tf, kind)).fetchone()) for kind in output_kinds)
        return (self.candle_hashes[key], versions, tuple(revisions), output)

    def unchanged(self, con, mod, symbol, tf):
        signature = self.signature(con, mod, symbol, tf)
        key = (mod.__name__, symbol, tf)
        if signature is not None and self.successful.get(key) == signature:
            self.skipped += 1
            return True
        self.successful.pop(key, None)
        self.pending[key] = signature
        self.executed += 1
        return False

    def remember(self, con, mod, symbol, tf):
        key = (mod.__name__, symbol, tf)
        before = self.pending.pop(key, None)
        signature = self.signature(con, mod, symbol, tf)
        # Engine output may grow. Inputs may not: another process can append
        # upstream facts while run() is working. Such a revision has not been
        # proven processed and must get a fresh run next time.
        if before is not None and signature is not None and before[:-1] == signature[:-1]:
            self.successful[key] = signature
