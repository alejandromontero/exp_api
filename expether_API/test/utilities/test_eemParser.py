import unittest
import env
from utilities.eemParser import eemParser


class TestEemParser(unittest.TestCase):
    def test_parse_simple(self):
        self.assertEqual(
            eemParser.parse(
                "id                    : 0x8cdf9d9122b6"),
            {"id": "0x8cdf9d9122b6"}
            )

    def test_parse_spaces(self):
        self.assertEqual(
            eemParser.parse(
                "model                 : EE I/O Expansion Unit (40G)-4S"),
            {"model": "EE I/O Expansion Unit (40G)-4S"}
        )

    def test_parse_list(self):
        self.assertEqual(
            eemParser.parse(
                "notification_status0  : [u'up', u'down']"),
            {"notification_status0": ["u'up'", "u'down'"]}
        )

    def test_parse_list_complex(self):
        self.assertEqual(
            eemParser.parse(
                "notification_status0  : [u'up', u'down', u'down']"),
            {"notification_status0": ["u'up'", "u'down'", "u'down'"]}
        )


if __name__ == '__main__':
    unittest.main()
