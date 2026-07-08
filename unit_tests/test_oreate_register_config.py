from __future__ import annotations

import unittest
from pathlib import Path

from services.register import oreate_register


class OreateRegisterConfigTest(unittest.TestCase):
    def test_register_config_file_stays_inside_project_data_dir(self) -> None:
        project_root = Path(__file__).resolve().parents[1]

        self.assertEqual(oreate_register.register_config_file, project_root / "data" / "register.json")


if __name__ == "__main__":
    unittest.main()
