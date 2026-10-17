import unittest
from stage264_diagnose_tqsdk import redact


class RedactionTests(unittest.TestCase):
    def test_known_credentials_and_dynamic_tokens_never_survive(self):
        secrets = ['user@example.com', 'pass-very-secret', 'token-dynamic-1234']
        text = redact('user@example.com pass-very-secret token-dynamic-1234', secrets)
        for value in secrets:
            self.assertNotIn(value, text)

    def test_unknown_urls_emails_and_long_token_shapes_are_removed(self):
        text = redact('alice@example.org https://service.invalid/path?access_token=abc ' + 'Z'*48, [])
        self.assertNotIn('alice@', text)
        self.assertNotIn('access_token', text)
        self.assertNotIn('Z'*48, text)

    def test_public_permission_reason_is_preserved(self):
        message = 'get_kline_data_series 数据获取方式仅限专业版用户使用'
        self.assertEqual(redact(message, []), message)


if __name__ == '__main__':
    unittest.main()
