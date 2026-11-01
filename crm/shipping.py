"""Versandkosten. Eine Quelle: assets/js/shipping-config.js.

Frontend und CRM lesen dieselben Zahlen. Der Client schickt keinen Versandpreis.
"""
import re
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'assets' / 'js' / 'shipping-config.js'


def _load():
    text = CONFIG.read_text(encoding='utf-8')

    def num(name):
        match = re.search(r'%s\s*:\s*([0-9]+(?:\.[0-9]+)?)' % name, text)
        if not match:
            raise RuntimeError('missing %s in %s' % (name, CONFIG))
        return float(match.group(1))

    return num('SHIPPING_FEE_CHF'), num('FREE_SHIPPING_THRESHOLD_CHF'), num('VAT_RATE')


SHIPPING_FEE_CHF, FREE_SHIPPING_THRESHOLD_CHF, VAT_RATE = _load()


def shipping_for(subtotal):
    """Waren-Zwischensumme. Ab der Schwelle 0, sonst die Pauschale. Beides inkl. MwSt."""
    goods = round(float(subtotal or 0), 2)
    if goods >= round(float(FREE_SHIPPING_THRESHOLD_CHF), 2):
        return 0.0
    return round(float(SHIPPING_FEE_CHF), 2)
