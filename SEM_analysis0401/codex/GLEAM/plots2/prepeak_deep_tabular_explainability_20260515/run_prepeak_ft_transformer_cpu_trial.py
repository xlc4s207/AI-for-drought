#!/usr/bin/env python3
"""CPU-safe FT-Transformer trial for prepeak tabular recovery-time regression.

The script keeps the current event-level table design:
prepeak/event features -> t_recover_to_baseline_abs_peak.

It supports three table-input variants:
- raw_prepeak
- orthogonal_decomposition
- group_pca

Attribution outputs:
- feature ablation is always available once torch is installed.
- integrated gradients is saved when captum is installed.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.util
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

try:
    import torch
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "This FT-Transformer trial requires PyTorch. Install torch in the Flash_dra environment first."
    ) from exc

try:
    from captum.attr import IntegratedGradients
except Exception:  # pragma: no cover
    IntegratedGradients = None


ROOT = Path("/home/xulc/flash_drought")
GLEAM = ROOT / "process/SEM_analysis0401/codex/GLEAM"
PREPEAK_SCRIPT = GLEAM / "plots2/prepeak_shap_nomulticollinearity/run_prepeak_nomulticollinearity_shap.py"
OUT = GLEAM / "plots2/prepeak_deep_tabular_explainability_20260515"
TARGET = "t_recover_to_baseline_abs_peak"
BIOMES = ("Forest", "Grassland", "Savanna", "Cropland", "Shrubland")
METRICS = ("GPP", "RECO")


spec = importlib.util.spec_from_file_location("prepeak_nomulticollinearity_for_deep", PREPEAK_SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to import {PREPEAK_SCRIPT}")
pre = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pre
spec.loader.exec_module(pre)


@dataclass(frozen=True)
class MetricConfig:
    metric: str
    table: Path


TABLES = {
    "GPP": GLEAM / "data/feature_table_prepeak_event_GPP_code1_flash_SMrz_0401.parquet",
    "RECO": GLEAM / "data/feature_table_prepeak_event_RECO_code1_flash_SMrz_0401_mswepE.parquet",
}


class NumericalFeatureTokenizer(nn.Module):
    def __init__(self, n_features: int, d_token: int) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.empty(n_features, d_token))
        self.bias = nn.Parameter(torch.empty(n_features, d_token))
        nn.init.xavier_uniform_(self.weight)
        nn.init.zeros_(self.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x.unsqueeze(-1) * self.weight.unsqueeze(0) + self.bias.unsqueeze(0)


class FTTransformerRegressor(nn.Module):
    def __init__(
        self,
        n_features: int,
        d_token: int = 32,
        n_heads: int = 4,
        n_layers: int = 2,
        dropout: float = 0.10,
    ) -> None:
        super().__init__()
        self.tokenizer = NumericalFeatureTokenizer(n_features, d_token)
        self.cls = nn.Parameter(torch.zeros(1, 1, d_token))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_token,
            nhead=n_heads,
            dim_feedforward=d_token * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.head = nn.Sequential(
            nn.LayerNorm(d_token),
            nn.Linear(d_token, d_token),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_token, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        tokens = self.tokenizer(x)
        cls = self.cls.expand(x.shape[0], -1, -1)
        z = self.encoder(torch.cat([cls, tokens], dim=1))
        return self.head(z[:, 0]).squeeze(-1)


def load_metric_table(metric: str) -> pd.DataFrame:
    return pre.finalize_feature_table(pd.read_parquet(TABLES[metric]))


def build_inputs(df_metric: pd.DataFrame, metric: str, biome: str, input_variant: str, row_limit: int) -> tuple[pd.DataFrame, pd.Series]:
    sub = pre.filter_analysis_subset(
        df_metric,
        metric=metric,
        code_id="code1",
        biome=biome,
        drought_type="flash",
        soil_layer="SMrz",
    )
    if len(sub) > row_limit:
        sub = sub.sample(n=row_limit, random_state=42).sort_index().reset_index(drop=True)
    raw, y = pre.prepare_raw_xy(sub)
    if input_variant == "raw_prepeak":
        X = pre.standardize_raw(raw).astype(np.float32)
    elif input_variant == "orthogonal_decomposition":
        tmp = OUT / "_transform_cache" / input_variant / metric / biome
        tmp.mkdir(parents=True, exist_ok=True)
        X, _ = pre.build_orthogonal_inputs(raw, tmp)
    elif input_variant == "group_pca":
        tmp = OUT / "_transform_cache" / input_variant / metric / biome
        tmp.mkdir(parents=True, exist_ok=True)
        X, _ = pre.build_group_pca_inputs(raw, tmp)
    else:
        raise ValueError(input_variant)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(np.float32)
    return X.reset_index(drop=True), y.reset_index(drop=True).astype(np.float32)


def make_loader(X: np.ndarray, y: np.ndarray, batch_size: int, shuffle: bool) -> DataLoader:
    ds = TensorDataset(torch.from_numpy(X.astype(np.float32)), torch.from_numpy(y.astype(np.float32)))
    return DataLoader(ds, batch_size=batch_size, shuffle=shuffle, num_workers=0)


def train_model(
    X: pd.DataFrame,
    y: pd.Series,
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    torch_threads: int,
) -> tuple[FTTransformerRegressor, dict[str, float], dict[str, np.ndarray]]:
    torch.set_num_threads(torch_threads)
    X_train, X_tmp, y_train, y_tmp = train_test_split(X, y, test_size=0.30, random_state=42)
    X_valid, X_test, y_valid, y_test = train_test_split(X_tmp, y_tmp, test_size=0.50, random_state=43)
    y_scaler = StandardScaler()
    y_train_z = y_scaler.fit_transform(y_train.to_numpy().reshape(-1, 1)).ravel().astype(np.float32)
    y_valid_z = y_scaler.transform(y_valid.to_numpy().reshape(-1, 1)).ravel().astype(np.float32)
    y_test_z = y_scaler.transform(y_test.to_numpy().reshape(-1, 1)).ravel().astype(np.float32)

    model = FTTransformerRegressor(n_features=X.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    loss_fn = nn.MSELoss()
    train_loader = make_loader(X_train.to_numpy(), y_train_z, batch_size, shuffle=True)
    valid_x = torch.from_numpy(X_valid.to_numpy(dtype=np.float32))
    valid_y = torch.from_numpy(y_valid_z)
    best_state = None
    best_valid = math.inf
    patience = 6
    stale = 0
    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        losses = []
        for xb, yb in train_loader:
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            losses.append(float(loss.detach()))
        model.eval()
        with torch.no_grad():
            valid_loss = float(loss_fn(model(valid_x), valid_y))
        history.append({"epoch": epoch, "train_loss": float(np.mean(losses)), "valid_loss": valid_loss})
        if valid_loss < best_valid - 1e-5:
            best_valid = valid_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        if stale >= patience:
            break
    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    arrays = {
        "X_train": X_train.to_numpy(dtype=np.float32),
        "X_valid": X_valid.to_numpy(dtype=np.float32),
        "X_test": X_test.to_numpy(dtype=np.float32),
        "y_train": y_train.to_numpy(dtype=np.float32),
        "y_valid": y_valid.to_numpy(dtype=np.float32),
        "y_test": y_test.to_numpy(dtype=np.float32),
        "y_test_z": y_test_z,
        "y_scaler_mean": y_scaler.mean_,
        "y_scaler_scale": y_scaler.scale_,
    }
    with torch.no_grad():
        pred_z = model(torch.from_numpy(arrays["X_test"])).numpy()
    pred = y_scaler.inverse_transform(pred_z.reshape(-1, 1)).ravel()
    metrics = {
        "r2_test": float(r2_score(arrays["y_test"], pred)),
        "rmse_test": float(mean_squared_error(arrays["y_test"], pred) ** 0.5),
        "mae_test": float(mean_absolute_error(arrays["y_test"], pred)),
        "best_valid_loss_scaled": float(best_valid),
        "epochs_run": int(history[-1]["epoch"]),
        "train_rows": int(len(X_train)),
        "valid_rows": int(len(X_valid)),
        "test_rows": int(len(X_test)),
    }
    arrays["pred_test"] = pred.astype(np.float32)
    arrays["history"] = np.asarray([[h["epoch"], h["train_loss"], h["valid_loss"]] for h in history], dtype=np.float32)
    return model, metrics, arrays


def feature_ablation(
    model: FTTransformerRegressor,
    X_ref: np.ndarray,
    y_ref: np.ndarray,
    pred_ref: np.ndarray,
    feature_names: list[str],
    max_rows: int,
) -> pd.DataFrame:
    n = min(max_rows, len(X_ref))
    X_base = X_ref[:n].copy()
    y_base = y_ref[:n].copy()
    pred_base = pred_ref[:n].copy()
    rows = []
    model.eval()
    base_r2 = r2_score(y_base, pred_base)
    for j, feature in enumerate(feature_names):
        X_mod = X_base.copy()
        X_mod[:, j] = 0.0
        with torch.no_grad():
            pred_mod = model(torch.from_numpy(X_mod.astype(np.float32))).numpy()
        # Fit outputs are in scaled space; convert with a linear correction using
        # the reference prediction scale if needed by comparing delta only.
        # For ablation ranking, mean absolute prediction change is scale-stable
        # when all features are evaluated in the same model.
        delta_scaled = pred_mod - model(torch.from_numpy(X_base.astype(np.float32))).detach().numpy()
        rows.append(
            {
                "feature": feature,
                "mean_abs_prediction_change_scaled": float(np.mean(np.abs(delta_scaled))),
                "base_subset_r2_original": float(base_r2),
            }
        )
    out = pd.DataFrame(rows)
    total = out["mean_abs_prediction_change_scaled"].sum()
    out["percent"] = out["mean_abs_prediction_change_scaled"] / total * 100.0 if total > 0 else np.nan
    return out.sort_values("mean_abs_prediction_change_scaled", ascending=False).reset_index(drop=True)


def integrated_gradients(
    model: FTTransformerRegressor,
    X_ref: np.ndarray,
    feature_names: list[str],
    max_rows: int,
) -> pd.DataFrame | None:
    if IntegratedGradients is None:
        return None
    n = min(max_rows, len(X_ref))
    inputs = torch.from_numpy(X_ref[:n].astype(np.float32))
    baseline = torch.zeros_like(inputs)
    model.eval()
    ig = IntegratedGradients(model)
    attrs = ig.attribute(inputs, baselines=baseline, n_steps=32)
    arr = attrs.detach().numpy()
    rows = [
        {"feature": f, "mean_abs_ig": float(np.mean(np.abs(arr[:, j]))), "mean_ig": float(np.mean(arr[:, j]))}
        for j, f in enumerate(feature_names)
    ]
    out = pd.DataFrame(rows).sort_values("mean_abs_ig", ascending=False).reset_index(drop=True)
    total = out["mean_abs_ig"].sum()
    out["percent"] = out["mean_abs_ig"] / total * 100.0 if total > 0 else np.nan
    return out


def run_one(metric: str, biome: str, input_variant: str, args: argparse.Namespace) -> dict[str, object]:
    df_metric = load_metric_table(metric)
    X, y = build_inputs(df_metric, metric, biome, input_variant, args.row_limit)
    out_dir = OUT / input_variant / metric / biome
    out_dir.mkdir(parents=True, exist_ok=True)
    model, metrics, arrays = train_model(
        X,
        y,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        torch_threads=args.torch_threads,
    )
    torch.save(model.state_dict(), out_dir / "ft_transformer_state_dict.pt")
    pd.DataFrame(arrays["history"], columns=["epoch", "train_loss", "valid_loss"]).to_csv(out_dir / "training_history.csv", index=False)
    pd.DataFrame(
        {
            "y_true": arrays["y_test"],
            "y_pred": arrays["pred_test"],
        }
    ).to_csv(out_dir / "test_predictions.csv", index=False)
    ablation = feature_ablation(model, arrays["X_test"], arrays["y_test"], arrays["pred_test"], X.columns.tolist(), args.attr_rows)
    ablation.to_csv(out_dir / "feature_ablation_importance.csv", index=False)
    ig = integrated_gradients(model, arrays["X_test"], X.columns.tolist(), args.attr_rows)
    if ig is not None:
        ig.to_csv(out_dir / "integrated_gradients_importance.csv", index=False)
    run = {
        "input_variant": input_variant,
        "metric": metric,
        "biome": biome,
        "rows": int(len(X)),
        "features": int(X.shape[1]),
        "feature_names": ",".join(X.columns),
        "torch_threads": args.torch_threads,
        "captum_available": IntegratedGradients is not None,
        **metrics,
    }
    (out_dir / "run_summary.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    return run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", nargs="+", default=list(METRICS))
    parser.add_argument("--biomes", nargs="+", default=list(BIOMES))
    parser.add_argument("--input-variants", nargs="+", default=["raw_prepeak", "orthogonal_decomposition"])
    parser.add_argument("--row-limit", type=int, default=20000)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--lr", type=float, default=8e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--torch-threads", type=int, default=4)
    parser.add_argument("--attr-rows", type=int, default=1000)
    parser.add_argument("--n-jobs", type=int, default=1, help="CPU-safe process parallelism. Use 1-2 on this machine.")
    return parser.parse_args()


def run_task(task: tuple[str, str, str, argparse.Namespace]) -> dict[str, object]:
    input_variant, metric, biome, args = task
    print(f"[RUN] {input_variant} | {metric} | {biome}", flush=True)
    result = run_one(metric, biome, input_variant, args)
    print(f"[DONE] {input_variant} | {metric} | {biome}", flush=True)
    return result


def main() -> None:
    args = parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    tasks = [(input_variant, metric, biome, args) for input_variant in args.input_variants for metric in args.metrics for biome in args.biomes]
    if args.n_jobs <= 1:
        for task in tasks:
            summaries.append(run_task(task))
            pd.DataFrame(summaries).to_csv(OUT / "ft_transformer_trial_model_summary.csv", index=False)
    else:
        with ProcessPoolExecutor(max_workers=args.n_jobs) as executor:
            futures = [executor.submit(run_task, task) for task in tasks]
            for future in as_completed(futures):
                summaries.append(future.result())
                pd.DataFrame(summaries).to_csv(OUT / "ft_transformer_trial_model_summary.csv", index=False)
    pd.DataFrame(summaries).to_csv(OUT / "ft_transformer_trial_model_summary.csv", index=False)
    print(OUT)


if __name__ == "__main__":
    main()
