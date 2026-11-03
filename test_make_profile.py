import hashlib
import json
import os
import struct
import tempfile
import unittest

import make_profile


class VcgtTests(unittest.TestCase):
    def test_vcgt_size_and_header(self):
        data = make_profile.make_vcgt(0.95, 1.05, 1.10)
        self.assertEqual(len(data), 18 + 3 * 256 * 2)
        self.assertEqual(data[:4], b"vcgt")
        self.assertEqual(struct.unpack(">I", data[8:12])[0], 0)
        self.assertEqual(struct.unpack(">HHH", data[12:18]), (3, 256, 2))

    def test_vcgt_curves_are_monotonic_and_clamped(self):
        data = make_profile.make_vcgt(0.95, 1.05, 1.10)
        for channel in range(3):
            values = struct.unpack(">256H", data[18 + channel * 512 : 18 + (channel + 1) * 512])
            self.assertTrue(all(values[i] <= values[i + 1] for i in range(255)))
            self.assertEqual(values[0], 0)
        red = struct.unpack(">256H", data[18:530])
        green = struct.unpack(">256H", data[530:1042])
        blue = struct.unpack(">256H", data[1042:1554])
        self.assertEqual(red[-1], round(0.95 * 65535))
        self.assertEqual(green[-1], 65535)
        self.assertEqual(blue[-1], 65535)


class ProfileTests(unittest.TestCase):
    def test_built_profile_is_structurally_valid(self):
        with open(make_profile.SOURCE_PROFILE, "rb") as handle:
            source = handle.read()
        profile = make_profile.build_profile(source, 0.95, 1.05, 1.10)
        self.assertEqual(struct.unpack(">I", profile[0:4])[0], len(profile))
        self.assertEqual(struct.unpack(">I", profile[128:132])[0], 15)
        tags = dict(make_profile.parse_tags(profile))
        self.assertIn(b"vcgt", tags)
        self.assertEqual(len(tags[b"vcgt"]), 1554)
        self.assertEqual(tags[b"vcgt"][:4], b"vcgt")

    def test_profile_id_matches_zeroed_profile(self):
        with open(make_profile.SOURCE_PROFILE, "rb") as handle:
            source = handle.read()
        profile = bytearray(make_profile.build_profile(source, 0.95, 1.05, 1.10))
        stored = bytes(profile[84:100])
        profile[84:100] = b"\x00" * 16
        self.assertEqual(stored, hashlib.md5(profile).digest())

    def test_build_profile_from_1024_entry_luts(self):
        with open(make_profile.SOURCE_PROFILE, "rb") as handle:
            source = handle.read()
        lut = [round(index * 65535 / 1023) for index in range(1024)]
        profile = make_profile.build_profile_from_luts(source, lut, lut, lut)
        tags = dict(make_profile.parse_tags(profile))
        self.assertEqual(len(tags[b"vcgt"]), 18 + 3 * 1024 * 2)
        self.assertEqual(struct.unpack(">H", tags[b"vcgt"][14:16])[0], 1024)


class SavedReferenceTests(unittest.TestCase):
    def test_rejects_non_unit_saturation(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(
                {
                    "gains": {"red": 0.95, "green": 1.05, "blue": 1.10},
                    "saturation": 1.10,
                },
                handle,
            )
            path = handle.name
        try:
            with self.assertRaises(ValueError):
                make_profile.load_saved_gains(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
