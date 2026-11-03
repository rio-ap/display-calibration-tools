import unittest

import laptop_color_tuner as tuner


class MatrixTests(unittest.TestCase):
    def test_identity_matrix(self):
        self.assertEqual(
            tuner.compute_matrix(1.0, 1.0, 1.0, 1.0),
            tuner.IDENTITY,
        )

    def test_identity_ctm_sequence(self):
        self.assertEqual(
            tuner.ctm_values(tuner.IDENTITY),
            [0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1],
        )

    def test_gain_only(self):
        matrix = tuner.compute_matrix(0.90, 1.00, 1.10, 1.0)
        self.assertAlmostEqual(matrix[0][0], 0.90)
        self.assertAlmostEqual(matrix[1][1], 1.00)
        self.assertAlmostEqual(matrix[2][2], 1.10)
        self.assertAlmostEqual(matrix[0][1], 0.0)
        self.assertAlmostEqual(matrix[0][2], 0.0)

    def test_saturation_identity(self):
        self.assertEqual(tuner.saturation_matrix(1.0), tuner.IDENTITY)

    def test_saturation_preserves_neutral_luma(self):
        matrix = tuner.saturation_matrix(0.0)
        for row in matrix:
            self.assertAlmostEqual(sum(row), 1.0)
        self.assertAlmostEqual(matrix[0][0], tuner.LUMA[0])
        self.assertAlmostEqual(matrix[1][0], tuner.LUMA[0])
        self.assertAlmostEqual(matrix[2][0], tuner.LUMA[0])

    def test_fixed_point_known_values(self):
        self.assertEqual(tuner.to_fixed(1.0), (0, 1))
        self.assertEqual(tuner.to_fixed(0.5), (0x80000000, 0))
        self.assertEqual(tuner.to_fixed(-1.0), (0, 0xFFFFFFFF))

    def test_ctm_has_eighteen_values(self):
        values = tuner.ctm_values(tuner.compute_matrix(0.95, 0.98, 1.0, 1.05))
        self.assertEqual(len(values), 18)
        self.assertTrue(all(0 <= value <= 0xFFFFFFFF for value in values))

    def test_row_sums_stay_near_one_for_neutral(self):
        matrix = tuner.compute_matrix(0.95, 0.98, 1.0, 1.0)
        for row in matrix:
            self.assertAlmostEqual(sum(row), round(sum(row), 6), places=6)
        self.assertAlmostEqual(sum(matrix[0]), 0.95)
        self.assertAlmostEqual(sum(matrix[1]), 0.98)
        self.assertAlmostEqual(sum(matrix[2]), 1.0)


if __name__ == "__main__":
    unittest.main()
