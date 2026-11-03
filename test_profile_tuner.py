import unittest

import profile_tuner
import xrandr_gamma


class LutMathTests(unittest.TestCase):
    def test_identity_lut(self):
        self.assertEqual(profile_tuner.identity_lut(5), [0, 16384, 32768, 49151, 65535])

    def test_channel_lut_neutral_is_identity(self):
        base = [0, 16384, 32768, 49151, 65535]
        self.assertEqual(
            profile_tuner.channel_lut(base, 1.0, 1.0, 1.0, 0.0),
            base,
        )

    def test_channel_lut_gain(self):
        base = [0, 32768, 65535]
        result = profile_tuner.channel_lut(base, 0.5, 1.0, 1.0, 0.0)
        self.assertEqual(result, [0, 16384, 32768])

    def test_channel_lut_black_lift(self):
        result = profile_tuner.channel_lut([0, 65535], 1.0, 1.0, 1.0, 0.10)
        self.assertEqual(result[0], 6554)
        self.assertEqual(result[1], 65535)

    def test_channel_lut_clamps(self):
        result = profile_tuner.channel_lut([0, 65535], 2.0, 1.0, 1.0, 0.0)
        self.assertEqual(result[0], 0)
        self.assertEqual(result[1], 65535)

    def test_resample_endpoints(self):
        self.assertEqual(xrandr_gamma.resample([0, 65535], 5), [0, 16384, 32768, 49151, 65535])

    def test_resample_passthrough(self):
        values = [0, 100, 200, 300, 400]
        self.assertEqual(xrandr_gamma.resample(values, 5), values)


if __name__ == "__main__":
    unittest.main()
