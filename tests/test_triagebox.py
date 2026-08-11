from __future__ import annotations

import unittest
from email import message_from_string, policy

from workinbox.triagebox import (
    TriageSenderKind,
    normalize_address,
    normalize_message_id,
    parse_message_id_list,
    parse_triage_headers,
    sender_kind,
)


class TriageBoxHeaderTest(unittest.TestCase):
    def test_normalizes_addresses(self) -> None:
        self.assertEqual(
            normalize_address('Example User <Main@Example.COM>'),
            'main@example.com',
        )
        self.assertIsNone(normalize_address(None))

    def test_detects_self_sender_from_configured_addresses(self) -> None:
        self.assertEqual(
            sender_kind(
                'Example User <Alias@Example.COM>',
                ('main@example.com', 'alias@example.com'),
            ),
            TriageSenderKind.SELF,
        )
        self.assertEqual(
            sender_kind('other@example.com', ('main@example.com',)),
            TriageSenderKind.OTHER,
        )

    def test_normalizes_message_ids(self) -> None:
        self.assertEqual(normalize_message_id('<abc@example.com>'), '<abc@example.com>')
        self.assertEqual(normalize_message_id('abc@example.com'), '<abc@example.com>')
        self.assertIsNone(normalize_message_id(''))

    def test_parses_message_id_lists_and_removes_duplicates(self) -> None:
        self.assertEqual(
            parse_message_id_list(
                '<root@example.com> <parent@example.com> <parent@example.com>'
            ),
            ('<root@example.com>', '<parent@example.com>'),
        )

    def test_referenced_message_ids_prioritize_direct_parent_then_newest_reference(self) -> None:
        message = message_from_string(
            '''From: sender@example.com
Message-ID: <reply@example.com>
In-Reply-To: <direct@example.com>
References: <root@example.com> <direct@example.com> <older@example.com>

body
''',
            policy=policy.default,
        )
        headers = parse_triage_headers(message)
        self.assertEqual(
            headers.referenced_message_ids,
            ('<direct@example.com>', '<older@example.com>', '<root@example.com>'),
        )

    def test_parses_workinbox_origin_header(self) -> None:
        message = message_from_string(
            '''From: me@example.com
Message-ID: <request@example.com>
X-WorkInBox-Origin-Message-ID: <origin@example.com>

body
''',
            policy=policy.default,
        )
        headers = parse_triage_headers(message)
        self.assertEqual(headers.from_address, 'me@example.com')
        self.assertEqual(headers.message_id, '<request@example.com>')
        self.assertEqual(headers.origin_message_id, '<origin@example.com>')

    def test_does_not_guess_invalid_multi_token_bare_message_ids(self) -> None:
        self.assertEqual(parse_message_id_list('not an id'), ())


if __name__ == '__main__':
    unittest.main()
