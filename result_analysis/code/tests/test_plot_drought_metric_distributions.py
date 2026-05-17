import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path("/home/xulc/flash_drought/process/result_analysis/code/plot_drought_metric_distributions.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("plot_drought_metric_distributions", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PlotDroughtMetricDistributionTests(unittest.TestCase):
    def test_metric_specs_cover_requested_outputs(self):
        mod = _load_module()
        self.assertEqual(set(mod.METRIC_SPECS.keys()), {"duration", "intensity", "onset_rate", "frequency"})
        self.assertEqual(mod.METRIC_SPECS["duration"].source_var, "duration_mean")
        self.assertEqual(mod.METRIC_SPECS["frequency"].source_var, "mean_annual_frequency")

    def test_scenario_builder_returns_four_scenarios(self):
        mod = _load_module()
        scenarios = mod.build_scenarios()
        self.assertEqual(len(scenarios), 4)
        labels = {(s.soil_layer, s.drought_type) for s in scenarios}
        self.assertEqual(labels, {("SMs", "flash"), ("SMs", "nonflash"), ("SMrz", "flash"), ("SMrz", "nonflash")})


if __name__ == "__main__":
    unittest.main()
