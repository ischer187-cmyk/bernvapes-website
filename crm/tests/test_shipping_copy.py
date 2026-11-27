import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ShippingConfigCopyTests(unittest.TestCase):
    def test_crm_copy_matches_frontend_config(self):
        self.assertEqual(
            (ROOT / 'assets' / 'js' / 'shipping-config.js').read_text(encoding='utf-8'),
            (ROOT / 'crm' / 'shipping-config.js').read_text(encoding='utf-8'),
            'crm/shipping-config.js muss eine exakte Kopie von assets/js/shipping-config.js sein')


if __name__ == '__main__':
    unittest.main()
