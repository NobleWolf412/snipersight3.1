from engine.marketpulse import PulseClient


FEED=b'''<rss version="2.0"><channel><title>Official</title><item><title>Policy update</title><link>https://www.federalreserve.gov/example</link><pubDate>Fri, 11 Sep 2026 12:00:00 GMT</pubDate></item></channel></rss>'''


def test_failed_refresh_is_delayed_then_historical_not_fresh():
    clock=[100]
    fail=[False]
    def fetch(_):
        if fail[0]: raise OSError('offline')
        return FEED
    client=PulseClient(fetcher=fetch,clock=lambda:clock[0])
    assert all(s['status']=='FRESH' for s in client.current()['sources'])
    fail[0]=True;clock[0]=1100
    delayed=client.current()
    assert all(s['status']=='DELAYED' for s in delayed['sources'])
    assert delayed['items'] and not delayed['items'][0]['historical']
    clock[0]=90000
    stale=client.current()
    assert all(s['status']=='UNAVAILABLE' for s in stale['sources'])
    assert stale['items'][0]['historical']


def test_empty_or_unsafe_feed_cannot_claim_headline_coverage():
    client=PulseClient(fetcher=lambda _:b'<html>Access denied</html>',clock=lambda:100)
    result=client.current()
    assert not result['items']
    assert all(s['status']=='UNAVAILABLE' for s in result['sources'])
