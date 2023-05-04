# To change this template, choose Tools | Templates
# and open the template in the editor.
import os
import os.path as op
import subprocess
import unittest

from karabo.bound import Configurator, Hash, PythonDevice
from simpleImageProcessor import SimpleImageProcessor

BLACKLIST = ['setup.py', '__init__.py']


class SimpleImageProcessor_TestCase(unittest.TestCase):
    def test_proc(self):
        proc = Configurator(PythonDevice).create("SimpleImageProcessor", Hash(
            "Logger.priority", "WARN",
            "deviceId", "SimpleImageProcessor_0"))
        proc.startFsm()

    def test_code_quality(self):

        def get_python_files():
            """Get all python files from this package
            """
            common_dir = op.abspath(op.dirname(SimpleImageProcessor.__file__))
            flake_check = []
            for dirpath, _, filenames in os.walk(common_dir):
                for fn in filenames:
                    if (op.splitext(fn)[-1].lower() == '.py'
                            and fn not in BLACKLIST):
                        path = op.join(dirpath, fn)
                        flake_check.append(path)

            return flake_check

        files = get_python_files()
        for py_file in files:
            command = ['flake8', op.abspath(py_file)]
            subprocess.check_call(command)


if __name__ == '__main__':
    unittest.main()
