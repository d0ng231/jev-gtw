import base64
import unittest
from urllib.parse import quote

from jev_gtw.signals import categories


class SignalTests(unittest.TestCase):
    def test_obfuscated_identifiers_are_detected_without_releasing_decoded_data(self):
        email='synthetic.person@example.test'
        variants=[email,quote(email,safe=''),quote(quote(email,safe=''),safe=''),
                  email.replace('@','&#64;'),email.replace('@',r'\u0040'),
                  email.replace('@','\u200b@'),
                  ''.join(chr(ord(c)+0xFEE0) if 0x21 <= ord(c) <= 0x7e else c for c in email),
                  base64.b64encode(email.encode()).decode()]
        for value in variants:
            with self.subTest(value=value):self.assertIn('CONTACT',categories(value))
        self.assertIn('ID_NUMBER',categories('M\u200bRN: SIM-991'))

    def test_literal_environment_reference_is_not_a_credential(self):
        for text in ['password: ${APP_PASSWORD}', 'api_key: "${API_KEY}"', 'def auth(password): return password']:
            self.assertNotIn('CREDENTIAL',categories(text))
        for text in ['password: ENV_REF', 'password: ${APP_PASSWORD}secret', 'account_password = "fictional-password"']:
            self.assertIn('CREDENTIAL',categories(text))

    def test_public_encodings_and_schema_names_do_not_imply_private_values(self):
        for text in ['SGVsbG8gd29ybGQ=', 'columns: [mrn, patient_name, email]', 'format=application%2Fjson']:
            self.assertEqual(categories(text),())

    def test_normalization_is_bounded(self):
        self.assertIn('ENCODING_LIMIT',categories('\uff21'*128001))


if __name__=='__main__':unittest.main()
