from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "13_plot_sem_path_diagrams.py"
SCRIPT_DIR = SCRIPT_PATH.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SPEC = importlib.util.spec_from_file_location("gleam_plot_sem_path_diagrams", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class TestPlotSemPathDiagrams(unittest.TestCase):
    def test_format_node_label_drops_recoverywin_prefix(self):
        self.assertEqual(
            MODULE.format_node_label("recoverywin_temperature_2m_mean"),
            "TMP",
        )
        self.assertEqual(MODULE.format_node_label("prepeak_temperature_2m_mean"), "TMP")
        self.assertEqual(MODULE.format_node_label("shock_total_precipitation_mean"), "PRE")
        self.assertEqual(MODULE.format_node_label("recoverywin_total_evaporation_mean"), "EVA")
        self.assertEqual(MODULE.format_node_label("recoverywin_total_precipitation_mean"), "PRE")
        self.assertEqual(MODULE.format_node_label("recoverywin_lai_total_mean"), "LAI")
        self.assertEqual(MODULE.format_node_label("event_duration"), "DUR")
        self.assertEqual(MODULE.format_node_label("event_intensity"), "INT")
        self.assertEqual(MODULE.format_node_label("t_recover_to_baseline_abs_peak"), "t_recover")

    def test_build_edge_records_reads_coefficients_and_labels(self):
        estimates = pd.DataFrame(
            {
                "lval": ["mid", "target", "target", "target"],
                "op": ["~", "~", "~", "~~"],
                "rval": ["x1", "mid", "x2", "target"],
                "Estimate": [0.5, 0.4, -0.25, 0.4],
                "p-value": [0.0, 0.01, 0.002, 0.0],
            }
        )

        edges = MODULE.build_edge_records(estimates)

        self.assertEqual(len(edges), 3)
        self.assertEqual(edges[0]["src"], "x1")
        self.assertEqual(edges[0]["dst"], "mid")
        self.assertIn("+0.500", edges[0]["label"])
        self.assertEqual(edges[1]["src"], "mid")
        self.assertEqual(edges[1]["dst"], "target")
        self.assertEqual(edges[2]["src"], "x2")
        self.assertIn("-0.250", edges[2]["label"])

    def test_choose_connectionstyle_uses_arc_for_long_cross_panel_edge(self):
        self.assertEqual(
            MODULE.choose_connectionstyle("a", "b", (0.08, 0.50), (0.92, 0.50)),
            "arc3,rad=0.22",
        )
        self.assertEqual(
            MODULE.choose_connectionstyle("a", "b", (0.08, 0.92), (0.50, 0.50)),
            "arc3,rad=0.0",
        )

    def test_parse_summary_metrics_extracts_rows_and_holdout_r2(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "demo_sem_summary.txt"
            summary_path.write_text(
                "\n".join(
                    [
                        "biome=Forest",
                        "rows=318380",
                        "target_equation_r2_holdout_split=0.6890406608581543",
                    ]
                ),
                encoding="utf-8",
            )

            metrics = MODULE.parse_summary_metrics(summary_path)

            self.assertEqual(metrics["biome"], "Forest")
            self.assertEqual(metrics["rows"], "318380")
            self.assertEqual(metrics["target_equation_r2_holdout_split"], "0.6890406608581543")

    def test_derive_overview_metadata_uses_sem_parent_scope_name(self):
        sem_dir = Path("/tmp/prepeak_event_shap_sem_20260420/sem_by_biome")
        basename, title = MODULE.derive_overview_metadata(sem_dir)
        self.assertEqual(basename, "prepeak_event_sem_path_diagrams_overview.png")
        self.assertEqual(title, "Prepeak Event SEM Path Diagrams")

    def test_derive_overview_metadata_uses_parent_name_for_by_biome_dirs(self):
        sem_dir = Path("/tmp/sem_prepeak_event_mechanism_20260420/by_biome")
        basename, title = MODULE.derive_overview_metadata(sem_dir)
        self.assertEqual(basename, "sem_prepeak_event_mechanism_sem_path_diagrams_overview.png")
        self.assertEqual(title, "Sem Prepeak Event Mechanism SEM Path Diagrams")

    def test_build_mechanism_layout_returns_fixed_positions(self):
        nodes = [
            "prepeak_total_precipitation_mean",
            "prepeak_total_evaporation_mean",
            "prepeak_temperature_2m_mean",
            "prepeak_strd_mean",
            "prepeak_ssrd_mean",
            "prepeak_VPD_mean",
            "prepeak_lai_total_mean",
            "prepeak_SMrz_mean",
            "t_recover_to_baseline_abs_peak",
        ]
        positions = MODULE.build_mechanism_layout(nodes, "t_recover_to_baseline_abs_peak")
        self.assertIsNotNone(positions)
        self.assertAlmostEqual(positions["prepeak_total_precipitation_mean"][0], 0.10, places=2)
        self.assertAlmostEqual(positions["prepeak_VPD_mean"][0], 0.40, places=2)
        self.assertAlmostEqual(positions["t_recover_to_baseline_abs_peak"][0], 0.86, places=2)

    def test_compute_label_position_separates_distinct_edges_in_mechanism_layout(self):
        positions = {
            "recoverywin_total_evaporation_mean": (0.10, 0.45),
            "recoverywin_strd_mean": (0.10, 0.68),
            "recoverywin_lai_total_mean": (0.56, 0.45),
            "t_recover_to_baseline_abs_peak": (0.86, 0.45),
        }
        p1 = MODULE.compute_edge_label_position(
            positions["recoverywin_total_evaporation_mean"],
            positions["t_recover_to_baseline_abs_peak"],
            MODULE.get_connection_rad("recoverywin_total_evaporation_mean", "t_recover_to_baseline_abs_peak"),
        )
        p2 = MODULE.compute_edge_label_position(
            positions["recoverywin_strd_mean"],
            positions["recoverywin_lai_total_mean"],
            MODULE.get_connection_rad("recoverywin_strd_mean", "recoverywin_lai_total_mean"),
        )
        self.assertFalse(np.allclose(p1, p2))

    def test_compute_label_position_pushes_eva_to_target_label_toward_target_side(self):
        positions = {
            "recoverywin_total_evaporation_mean": (0.10, 0.45),
            "recoverywin_strd_mean": (0.10, 0.68),
            "recoverywin_lai_total_mean": (0.56, 0.45),
            "t_recover_to_baseline_abs_peak": (0.86, 0.45),
        }
        eva_to_target = MODULE.compute_edge_label_position_for_nodes(
            "recoverywin_total_evaporation_mean",
            "t_recover_to_baseline_abs_peak",
            positions["recoverywin_total_evaporation_mean"],
            positions["t_recover_to_baseline_abs_peak"],
        )
        strd_to_lai = MODULE.compute_edge_label_position_for_nodes(
            "recoverywin_strd_mean",
            "recoverywin_lai_total_mean",
            positions["recoverywin_strd_mean"],
            positions["recoverywin_lai_total_mean"],
        )
        self.assertGreater(eva_to_target[0], 0.60)
        self.assertGreater(eva_to_target[0], strd_to_lai[0] + 0.15)

    def test_format_edge_label_splits_value_and_significance(self):
        self.assertEqual(MODULE.format_edge_label("+0.397***"), "+0.397\n***")
        self.assertEqual(MODULE.format_edge_label("-0.031***"), "-0.031\n***")
        self.assertEqual(MODULE.format_edge_label("+0.042"), "+0.042")

    def test_compute_edge_linewidth_scales_with_effect_size(self):
        low = MODULE.compute_edge_linewidth(0.03, 0.50)
        high = MODULE.compute_edge_linewidth(0.50, 0.50)
        self.assertLess(low, high)


if __name__ == "__main__":
    unittest.main()
