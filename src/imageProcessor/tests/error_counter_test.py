import unittest

from ..common import ErrorCounter


class ErrorCounter_TestCase(unittest.TestCase):
    def test_error_counter(self):
        error_counter = ErrorCounter(window_size=10)

        # Initial values
        self.assertEqual(error_counter.size, 0)
        self.assertAlmostEqual(error_counter.fraction, 0.)
        self.assertEqual(error_counter.alarm, False)

        # Append all successes to counter
        for i in range(20):
            error_counter.append()
        self.assertEqual(error_counter.size, 10)
        self.assertAlmostEqual(error_counter.fraction, 0.)
        self.assertEqual(error_counter.alarm, False)

        # Append one failure (10%)
        error_counter.append(error=True)
        self.assertAlmostEqual(error_counter.fraction, 0.1)
        self.assertEqual(error_counter.alarm, False)

        # Append another failure (20%)
        error_counter.append(error=True)
        self.assertAlmostEqual(error_counter.fraction, 0.2)
        self.assertEqual(error_counter.alarm, True)

        # Increase threshold to 0.25
        error_counter.threshold = 0.25
        self.assertEqual(error_counter.alarm, False)

        # Clear and check again
        error_counter.clear()
        self.assertEqual(error_counter.size, 0)
        self.assertAlmostEqual(error_counter.fraction, 0.)
        self.assertEqual(error_counter.alarm, False)

    def test_epsilon(self):
        error_counter = ErrorCounter(window_size=100, threshold=0.1,
                                     epsilon=0.01)

        # Append all successes to counter
        for i in range(100):
            error_counter.append()
        self.assertEqual(error_counter.alarm, False)

        # Append 10 failures - no alarm yet
        for i in range(10):
            error_counter.append(True)
        # fraction (0.10) < threshold+epsilon (0.11)
        self.assertEqual(error_counter.alarm, False)

        # Append one more failure - enter alarm
        error_counter.append(True)
        # Now fraction (0.11) == threshold+epsilon (0.11)
        self.assertEqual(error_counter.alarm, True)

        # Clear
        error_counter.clear()

        # Append 10 failures - enter alarm
        for i in range(10):
            error_counter.append(True)
        # fraction (1.00) >= threshold+epsilon (0.11)
        self.assertEqual(error_counter.alarm, True)

        # Append 90 successes - still alarm
        for i in range(90):
            error_counter.append()
        # fraction (0.10) >= threshold-epsilon (0.09)
        self.assertEqual(error_counter.alarm, True)

        # Append one more success - leave alarm
        error_counter.append()
        # fraction (0.09) <= threshold-epsilon (0.09)
        self.assertEqual(error_counter.alarm, False)


if __name__ == '__main__':
    unittest.main()
