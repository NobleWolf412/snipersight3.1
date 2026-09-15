from decimal import Decimal

from engine import store, tradevisuals


def test_subdollar_and_tiny_price_levels_remain_distinguishable():
    for levels in (['.14012', '.13985', '.141', '.13984'], ['.000000013', '.000000014']):
        f = tradevisuals.price_format(levels)
        labels = [f"{Decimal(p):.{f['precision']}f}" for p in levels]
        assert len(set(labels)) == len(levels)
        assert f['precision'] > 2


def test_extreme_entry_and_exit_candles_do_not_inflate_profit(tmp_path):
    con = store.connect(tmp_path/'visual.db')
    for i, high in enumerate(['1000', '102', '104', '1000']):
        con.execute('INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)',
                    ('ENAUSDT', '15m', 9000+i*900, '100', high, '95', '100', '1', 'test', 15000))
    con.commit()
    t = dict(symbol='ENAUSDT', timeframe='15m', filled_at=9000, closed_at=11700,
             entry='100', quantity='10', planned_stop='98', exit_price='98', direction='LONG', origin='BOT', grade_eligible=True)
    x = tradevisuals.excursion(con, t, now=20000)
    assert Decimal(x['peak_gain_usd']) == 40
    assert Decimal(x['given_back_usd']) == 40
    assert x['peak_price'] == '104'
    assert x['full_candles'] == 2
    t['exit_price'] = '105'
    x = tradevisuals.excursion(con, t, now=20000)
    assert x['peak_price'] == '105' and x['peak_at'] == 11700
    assert Decimal(x['peak_gain_usd']) == 50
    assert Decimal(x['given_back_usd']) == 0
    con.execute('DELETE FROM candles WHERE open_ts=9900')
    con.commit()
    assert tradevisuals.excursion(con, t, now=20000)['state'] == 'PARTIAL'
    con.execute("UPDATE candles SET high='Infinity' WHERE open_ts=10800")
    con.commit()
    assert tradevisuals.excursion(con, t, now=20000)['state'] == 'UNAVAILABLE'
    t['grade_eligible'] = False
    assert tradevisuals.excursion(con, t, now=20000)['state'] == 'UNAVAILABLE'
    con.close()
