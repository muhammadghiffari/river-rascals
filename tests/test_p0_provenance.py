"""Traceability gate for the original Batch 2 asset libraries."""

import csv
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = (
    "PR_Coin", "PR_GoldenFish", "PR_Buoy", "PR_Log", "PR_RockSmall",
    "PR_RockMed", "PR_RockLarge", "PR_CheckpointArch", "PR_FinishGate",
    "PR_Signpost", "EN_PineTree", "EN_Bush", "EN_BankTile",
    "EN_RiverStrip", "EN_SkyDay",
)


class P0ProvenanceTests(unittest.TestCase):
    """Require own-work records without blessing older imported assets."""

    def setUp(self) -> None:
        with (ROOT / "assets/PROVENANCE.csv").open(encoding="utf-8", newline="") as stream:
            self.rows = list(csv.DictReader(stream))
        self.original = [
            row for row in self.rows
            if "own work" in row["licence"].lower()
            or "own-made" in row["licence"].lower()
        ]

    def test_every_p0_family_has_an_original_library(self) -> None:
        for family in FAMILIES:
            with self.subTest(family=family):
                self.assertTrue(any(
                    Path(row["file"]).name.startswith(family)
                    and row["file"].endswith(".blend") for row in self.original
                ), f"Missing own-made library provenance: {family}")

    def test_original_records_are_eight_columns_and_traceable(self) -> None:
        self.assertTrue(self.original, "No original P0 provenance records")
        for row in self.original:
            with self.subTest(file=row["file"]):
                self.assertEqual(len(row), 8)
                self.assertNotIn(None, row)
                self.assertTrue(all(isinstance(value, str) and value for value in row.values()))
                self.assertIn("CC0", row["licence"])
                self.assertIn("own", row["licence"].lower())
                self.assertTrue((ROOT / row["file"]).is_file())
                tool = row["source_url_or_tool"].split()[0]
                self.assertTrue((ROOT / tool).is_file(), tool)

    def test_new_asset_libraries_have_unique_records(self) -> None:
        imported = ROOT / "assets/props/PR_RockLarge.blend"
        paths = list((ROOT / "assets/props").glob("*.blend"))
        paths += list((ROOT / "assets/environment").glob("*.blend"))
        for path in paths:
            if path == imported:
                continue
            relative = path.relative_to(ROOT).as_posix()
            with self.subTest(file=relative):
                matches = [row for row in self.original if row["file"] == relative]
                self.assertEqual(len(matches), 1, relative)
