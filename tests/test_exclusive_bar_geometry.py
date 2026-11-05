import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ExclusiveBarGeometryTests(unittest.TestCase):
    def test_cpp_geometry_cases(self):
        with tempfile.TemporaryDirectory(prefix=".test-bar-geometry-", dir=ROOT) as tmp:
            binary = pathlib.Path(tmp) / "exclusive-bar-geometry"
            subprocess.run(
                ["c++", "-std=c++23", str(ROOT / "tests/exclusive_bar_geometry.cpp"), "-o", str(binary)],
                check=True,
                cwd=ROOT,
            )
            subprocess.run([str(binary)], check=True, cwd=ROOT)


if __name__ == "__main__":
    unittest.main()
