"""bexio invoice and customer creation.

The feature flag BEXIO_WRITE_ENABLED defaults to off. This module has no HTTP
client and never calls the bexio API, even if the flag is turned on.
"""
import os

def writes_enabled():
    return os.environ.get('BEXIO_WRITE_ENABLED', '0').strip().lower() in ('1', 'true', 'yes', 'on')

class BexioBilling:
    def create_customer(self, company):
        return self._refuse('customer', company.get('name') if isinstance(company, dict) else None)

    def create_invoice(self, order):
        return self._refuse('invoice', order.get('order_id') if isinstance(order, dict) else None)

    def _refuse(self, kind, ref):
        if not writes_enabled():
            return {'created': False, 'status': 'disabled', 'kind': kind, 'ref': ref,
                    'detail': 'BEXIO_WRITE_ENABLED is off. No bexio request was made.'}
        return {'created': False, 'status': 'refused', 'kind': kind, 'ref': ref,
                'detail': 'bexio write API is not implemented. No bexio request was made.'}
