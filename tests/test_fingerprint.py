import unittest

from roottrace.fingerprint import make_fingerprint, normalize_message


class FingerprintTests(unittest.TestCase):
    def test_volatile_numbers_do_not_change_normalized_message(self):
        a = normalize_message("Timeout after 1200 ms on attempt 3")
        b = normalize_message("Timeout after 9000 ms on attempt 8")
        self.assertEqual(a, b)

    def test_fingerprint_is_stable(self):
        a = make_fingerprint("infra", "timeout", "TimeoutError", "a.py", "t", "timeout after 1200")
        b = make_fingerprint("infra", "timeout", "TimeoutError", "a.py", "t", "timeout after 9999")
        self.assertEqual(a, b)
