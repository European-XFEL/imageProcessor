import unittest

from karabo.bound import Configurator, Hash, PythonDevice

from ..ImageProcessor import ImageProcessor


class ImageProcessor_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("ImageProcessor", Hash(
            "Logger.priority", "DEBUG",
            "deviceId", "ImageProcessor_0"))
        proc.startFsm()

    def test_auto_fit_range(self):
        res = ImageProcessor.auto_fit_range(x0=5, y0=5, sx=2, sy=2, sigmas=1,
                                            image_width=10, image_height=10)
        self.assertEqual(res, (0, 10, 0, 10))

        res = ImageProcessor.auto_fit_range(x0=5, y0=5, sx=2, sy=2, sigmas=1,
                                            image_width=10, image_height=10,
                                            min_range=4)
        self.assertEqual(res, (3, 7, 3, 7))

        res = ImageProcessor.auto_fit_range(x0=50, y0=50, sx=2, sy=2, sigmas=1,
                                            image_width=100,image_height=100)
        self.assertEqual(res, (45, 55, 45, 55))

        res = ImageProcessor.auto_fit_range(x0=50, y0=50, sx=5, sy=5, sigmas=3,
                                            image_width=100,image_height=100)
        self.assertEqual(res, (35, 65, 35, 65))

        res = ImageProcessor.auto_fit_range(x0=10, y0=5, sx=2, sy=2, sigmas=3,
                                            image_width=20, image_height=10,
                                            min_range=4)
        self.assertEqual(res, (4, 16, 0, 10))


if __name__ == '__main__':
    unittest.main()
