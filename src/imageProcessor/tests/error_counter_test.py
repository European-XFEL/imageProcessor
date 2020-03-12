import unittest

from ..common import ErrorCounter


class ErrorCounter_TestCase(unittest.TestCase):
    win_size = 30

    def test_error_counter(self):
        error_counter = ErrorCounter(window_size=self.win_size)

        # Initial values
        self.assertEqual(error_counter.size, 0)
        self.assertAlmostEqual(error_counter.fraction, 0.)
        self.assertEqual(error_counter.warn, False)

        # Append all successes to counter
        for _ in range(2 * self.win_size):
            error_counter.append()
        self.assertEqual(error_counter.size, self.win_size)
        self.assertAlmostEqual(error_counter.fraction, 0.)
        self.assertEqual(error_counter.warn, False)

        # Append one failure (10%)
        coeff = 0.1
        for _ in range(int(coeff * self.win_size)):
            error_counter.append(error=True)
        self.assertAlmostEqual(error_counter.fraction, coeff)
        self.assertEqual(error_counter.warn, False)

        # Append another 10% failures (20% in total)
        for _ in range(int(coeff * self.win_size)):
            error_counter.append(error=True)
        self.assertAlmostEqual(error_counter.fraction, coeff * 2.)
        self.assertEqual(error_counter.warn, True)

        # Increase threshold to 0.25
        error_counter.threshold = 0.25
        self.assertEqual(error_counter.warn, False)

        # Clear and check again
        error_counter.clear()
        self.assertEqual(error_counter.size, 0)
        self.assertAlmostEqual(error_counter.fraction, 0.)
        self.assertEqual(error_counter.warn, False)

    def test_epsilon(self):
        error_counter = ErrorCounter(window_size=100, threshold=0.1,
                                     epsilon=0.01)

        # Append all successes to counter
        for _ in range(100):
            error_counter.append()
        self.assertEqual(error_counter.warn, False)

        # Append 10 failures - no warn yet
        for _ in range(10):
            error_counter.append(True)
        # fraction (0.10) < threshold+epsilon (0.11)
        self.assertEqual(error_counter.warn, False)

        # Append one more failure - enter warn
        error_counter.append(True)
        # Now fraction (0.11) == threshold+epsilon (0.11)
        self.assertEqual(error_counter.warn, True)

        # Clear
        error_counter.clear()

        # Append 10 failures - enter warn
        for _ in range(10):
            error_counter.append(True)
        # fraction (1.00) >= threshold+epsilon (0.11)
        self.assertEqual(error_counter.warn, True)

        # Append 90 successes - still warn
        for _ in range(90):
            error_counter.append()
        # fraction (0.10) >= threshold-epsilon (0.09)
        self.assertEqual(error_counter.warn, True)

        # Append one more success - leave warn
        error_counter.append()
        # fraction (0.09) <= threshold-epsilon (0.09)
        self.assertEqual(error_counter.warn, False)

    def test_error_squeezing(self):
        error_counter = ErrorCounter(window_size=self.win_size)

        # Initial values
        self.assertEqual(error_counter.size, 0)
        self.assertAlmostEqual(error_counter.fraction, 0.)
        self.assertEqual(error_counter.warn, False)

        # Append one failure (100%)
        error_counter.append(True)
        self.assertAlmostEqual(error_counter.fraction, 1.0)
        self.assertEqual(error_counter.warn, True)

        # Check error squeezing
        for _ in range(self.win_size):
            error_counter.append(True)
        self.assertEqual(error_counter.size, self.win_size)
        self.assertAlmostEqual(error_counter.fraction, 1.0)
        self.assertEqual(error_counter.warn, True)
        for _ in range(self.win_size):
            error_counter.append()
        self.assertAlmostEqual(error_counter.fraction, 0.0)
        self.assertEqual(error_counter.warn, False)


if __name__ == '__main__':
    unittest.main()
