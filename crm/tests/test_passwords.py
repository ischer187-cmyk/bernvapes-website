"""Password hashes: scrypt when present, PBKDF2 when hashlib.scrypt is missing (LibreSSL)."""
import unittest
import harness
import auth

class PasswordTests(unittest.TestCase):
    def test_roundtrip_and_legacy_scrypt_shape(self):
        stored = auth.hash_password('ein-langes-passwort')
        self.assertTrue(stored.startswith('scrypt$') or stored.startswith('pbkdf2$'))
        self.assertNotIn('ein-langes-passwort', stored)
        self.assertTrue(auth.verify_password('ein-langes-passwort', stored))
        self.assertFalse(auth.verify_password('anderes-passwort', stored))
        self.assertFalse(auth.verify_password('ein-langes-passwort', ''))
        self.assertFalse(auth.verify_password('ein-langes-passwort', 'klartext'))

    def test_pbkdf2_when_scrypt_is_missing_and_old_scrypt_still_verifies(self):
        legacy = None
        if auth._scrypt() is not None:
            legacy = auth.hash_password('altes-passwort-1')
            self.assertTrue(legacy.startswith('scrypt$'))
            self.assertEqual(len(legacy.split('$')), 3)
        had = hasattr(auth.hashlib, 'scrypt')
        saved = getattr(auth.hashlib, 'scrypt', None)
        try:
            if had:
                delattr(auth.hashlib, 'scrypt')
            self.assertIsNone(auth._scrypt())
            fresh = auth.hash_password('neues-passwort-9')
            self.assertTrue(fresh.startswith('pbkdf2$'))
            kind, rounds, salt, digest = fresh.split('$')
            self.assertEqual(kind, 'pbkdf2')
            self.assertGreaterEqual(int(rounds), 600000)
            self.assertTrue(auth.verify_password('neues-passwort-9', fresh))
            self.assertFalse(auth.verify_password('falsches-passwort', fresh))
            if legacy:
                self.assertFalse(auth.verify_password('altes-passwort-1', legacy))
        finally:
            if had:
                setattr(auth.hashlib, 'scrypt', saved)
        self.assertTrue(auth.verify_password('neues-passwort-9', fresh))
        if legacy:
            self.assertTrue(auth.verify_password('altes-passwort-1', legacy))
            self.assertFalse(auth.verify_password('neues-passwort-9', legacy))

if __name__ == '__main__':
    unittest.main()
