import unittest

import monitors

SAMPLE = """\
Screen 0: minimum 320 x 200, current 3840 x 2280, maximum 16384 x 16384
eDP-1 connected primary 1920x1200+0+1080 (normal left inverted right x axis y axis) 302mm x 188mm
   1920x1200     60.00*+
HDMI-1 disconnected (normal left inverted right x axis y axis)
DP-2 connected 1920x1080+0+0 (normal left inverted right x axis y axis) 477mm x 268mm
   1920x1080     60.00*+
"""


class MonitorTests(unittest.TestCase):
    def test_parse_connected_outputs(self):
        result = monitors.parse_monitors(SAMPLE)
        self.assertEqual([item.name for item in result], ["eDP-1", "DP-2"])
        self.assertTrue(result[0].primary)
        self.assertTrue(result[0].internal)
        self.assertFalse(result[1].primary)
        self.assertFalse(result[1].internal)
        self.assertEqual((result[0].width, result[0].height), (1920, 1200))

    def test_default_prefers_internal(self):
        result = monitors.parse_monitors(SAMPLE)
        self.assertEqual(monitors.default_output(result), "eDP-1")

    def test_default_uses_primary_when_no_internal(self):
        result = monitors.parse_monitors(
            "DP-1 connected primary 2560x1440+0+0 (normal)\n"
            "HDMI-1 connected 1920x1080+2560+0 (normal)\n"
        )
        self.assertEqual(monitors.default_output(result), "DP-1")

    def test_label_contains_details(self):
        result = monitors.parse_monitors(SAMPLE)
        self.assertIn("internal", result[0].label())
        self.assertIn("primary", result[0].label())


if __name__ == "__main__":
    unittest.main()
