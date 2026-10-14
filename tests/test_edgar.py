"""The evidence a verdict commits to must be reproducible: SEC's CDN tags each
document with a script whose path changes over time, so the hash is of the
document without that tag, and the tag never changes what the check reads."""
from eth_utils import keccak

from vouchrh import edgar

TAIL = b'<div>40</div><script type="text/javascript"  src="/%s"></script></body></html>'


def test_the_cdn_tag_does_not_change_the_evidence():
    body = b"<html><body><p>Depreciation expense was $1.37 billion.</p>"
    a = body + TAIL % b"RMOci/B/y8/Fsm2/wuMqMZFM/OthYpXf0tJJGNr/MmxYFhMB/FC/oLH14LR2Q"
    b = body + TAIL % b"4k06Qn/dnFL/JpI/pHn/Iugq3uyh/iOOYrc2QkbpcQf3a/SxBdJRdhAQ/bm5/QMTtgcXU"
    assert keccak(a) != keccak(b)
    assert keccak(edgar.canonical(a)) == keccak(edgar.canonical(b))
    assert edgar.canonical(a) == body + b"<div>40</div></body></html>"
    assert edgar.to_text(a.decode()) == edgar.to_text(edgar.canonical(a).decode())


def test_only_the_cdn_tag_goes():
    inline = b'<script type="text/javascript">var x = "<b>";</script>'
    absolute = b'<script type="text/javascript" src="https://example.com/a.js"></script>'
    assert edgar.canonical(inline + absolute) == inline + absolute


def test_a_real_filing_reads_the_same_without_the_tag():
    f = edgar.latest("TSLA")
    raw = f.raw()
    assert edgar.to_text(edgar.canonical(raw).decode("utf-8", "ignore")) == f.text()
