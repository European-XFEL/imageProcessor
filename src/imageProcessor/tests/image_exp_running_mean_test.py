import unittest
import time
import numpy as np

from ..ImageAverager import ImageExponentialRunnningAverage


class ImageAverage_ExpAverage_TestCase(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_averaging_method(self):
        # Test constructor
        exp_avg = ImageExponentialRunnningAverage()
        self.assertIsNone(exp_avg.mean)

        image = 1024*np.ones([480,640,3], dtype=np.uint16)


        # Test updating and shape
        exp_avg.append(image, 10)
        self.assertEqual( exp_avg.shape.tolist(), [480, 640, 3])
        exp_avg.append(0.5*image, 10)
        exp_avg.append(0.5*image, 10)
        self.assertEqual( exp_avg.shape.tolist(), [480, 640, 3])
        self.assertAlmostEqual( exp_avg.mean[8,8,2], 926.72 )

        # Test clear average
        exp_avg.clear()
        self.assertIsNone(exp_avg.mean)


        # Test a long averaging run
        exp_avg.clear()
        for ii in range(100):
            exp_avg.append(0.5*image, 10)
        self.assertAlmostEqual( exp_avg.mean[8,8,2], 512.0, 0.1 )





if __name__ == '__main__':
    unittest.main()
