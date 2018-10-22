import unittest

from time import sleep

from ..common import FrameRate


class ImageRate_TestCase(unittest.TestCase):
    frameRate = FrameRate(refresh_interval=1.0)

    def test_init(self):
        self.assertEqual(self.frameRate.rate(), 0.)

    def test_elapsed_time(self):
        self.frameRate.reset()
        sleep(1.0)
        self.assertAlmostEqual(self.frameRate.elapsedTime(), 1.0, delta=0.01)

    def test_reset(self):
        counts = 100
        for _ in range(counts):
            self.frameRate.update()
        self.frameRate.reset()
        self.assertEqual(self.frameRate.rate(), 0.)

    def test_rate(self):
        counts = 100
        self.frameRate.reset()
        for _ in range(counts):
            sleep(1.0 / counts)
            self.frameRate.update()
        self.assertAlmostEqual(self.frameRate.rate(),
                               counts / self.frameRate.elapsedTime(),
                               delta=0.05)

    def test_refresh(self):
        counts = 100
        self.frameRate.reset()
        for _ in range(counts):
            sleep(1.1 / counts)
            self.frameRate.update()
        elapsed_time = self.frameRate.elapsedTime()
        fps = self.frameRate.refresh()
        self.assertAlmostEqual(fps,
                               counts / elapsed_time,
                               delta=0.05)
        self.assertEqual(self.frameRate.rate(), 0.)
        self.assertAlmostEqual(self.frameRate.elapsedTime(), 0., delta=0.01)


if __name__ == '__main__':
    unittest.main()
