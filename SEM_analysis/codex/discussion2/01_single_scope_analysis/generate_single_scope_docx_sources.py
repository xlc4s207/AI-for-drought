#!/usr/bin/env python3
"""Generate HTML sources for single-scope SEM/SHAP discussion Word documents."""

from __future__ import annotations

from html import escape
from pathlib import Path


BASE = Path("/home/xulc/flash_drought/process/SEM_analysis/codex/discussion2/01_single_scope_analysis")


DOC_CONFIGS = [
    {
        "md": BASE / "gpp_prepeak_event_analysis_cn.md",
        "html": BASE / "gpp_prepeak_event_analysis_docx_source.html",
        "title": "GPP 前置预测口径单独解释分析",
        "overview_path": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/sem_prepeak_event_mechanism_20260420/sem_prepeak_event_mechanism_sem_path_diagrams_overview.png",
        "overview_caption": "图 1. GPP 前置预测口径的 SEM 路径图总览。整体上，峰值前辐射背景、蒸散与水分异常共同塑造了后续恢复记忆。",
        "overview_beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Forest/feature_importance_beeswarm.png",
        "overview_beeswarm_caption": "图 2. Forest 的 SHAP beeswarm。该图代表性地展示了 GPP 前置预测口径中峰值前辐射和蒸散变量的高排序地位。",
        "sem_label": "SEM 路径图",
        "biomes": [
            {
                "name": "Forest",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Forest/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/sem_prepeak_event_mechanism_20260420/by_biome/GPP_code1_Forest_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Forest/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 5. Forest 中 SSRD 的 dependence plot。较高峰值前短波辐射对应更短恢复时间，是最强的负向前置记忆信号。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Forest/dependence_plots/prepeak_total_evaporation_mean.png",
                "dep2_caption": "图 6. Forest 中 EVA 的 dependence plot。较高峰值前蒸散对应更长恢复尾部，反映出更强的水分消耗记忆。",
            },
            {
                "name": "Grassland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Grassland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/sem_prepeak_event_mechanism_20260420/by_biome/GPP_code1_Grassland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Grassland/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 9. Grassland 中 SSRD 的 dependence plot。峰值前短波辐射越强，后续恢复越快，指向生长季活跃背景的记忆作用。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Grassland/dependence_plots/prepeak_total_precipitation_mean.png",
                "dep2_caption": "图 10. Grassland 中 PRE 的 dependence plot。峰值前降水增强通常对应更长恢复时间，提示更大偏离基线幅度。",
            },
            {
                "name": "Savanna",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Savanna/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/sem_prepeak_event_mechanism_20260420/by_biome/GPP_code1_Savanna_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Savanna/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 13. Savanna 中 SSRD 的 dependence plot。辐射背景仍是最显著的负向控制项。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Savanna/dependence_plots/prepeak_total_evaporation_mean.png",
                "dep2_caption": "图 14. Savanna 中 EVA 的 dependence plot。蒸散增强会放大恢复记忆并延长恢复尾部。",
            },
            {
                "name": "Cropland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Cropland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/sem_prepeak_event_mechanism_20260420/by_biome/GPP_code1_Cropland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Cropland/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 17. Cropland 中 SSRD 的 dependence plot。农田系统对峰值前辐射背景依旧高度敏感。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Cropland/dependence_plots/prepeak_total_evaporation_mean.png",
                "dep2_caption": "图 18. Cropland 中 EVA 的 dependence plot。较高蒸散会显著放大恢复尾部长度。",
            },
            {
                "name": "Shrubland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Shrubland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/sem_prepeak_event_mechanism_20260420/by_biome/GPP_code1_Shrubland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Shrubland/dependence_plots/prepeak_total_precipitation_mean.png",
                "dep1_caption": "图 21. Shrubland 中 PRE 的 dependence plot。较湿润的峰值前背景更容易对应较长恢复时间。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/gpp_code1_flash_smrz_onsetpeak_clean/prepeak_event_shap_sem_20260420/shap_by_biome/Shrubland/dependence_plots/prepeak_ssrd_mean.png",
                "dep2_caption": "图 22. Shrubland 中 SSRD 的 dependence plot。辐射信号相对存在，但弱于降水异常的前置记忆作用。",
            },
        ],
    },
    {
        "md": BASE / "reco_prepeak_event_analysis_cn.md",
        "html": BASE / "reco_prepeak_event_analysis_docx_source.html",
        "title": "RECO 前置预测口径单独解释分析",
        "overview_path": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/sem_prepeak_event_mechanism_sem_path_diagrams_overview.png",
        "overview_caption": "图 1. RECO 前置预测口径的 SEM 路径图总览。整体上，峰值前辐射、蒸散与温度背景共同构成呼吸恢复记忆。",
        "overview_beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Wetland/feature_importance_beeswarm.png",
        "overview_beeswarm_caption": "图 2. Wetland 的 SHAP beeswarm。湿地是 RECO 前置预测口径中统计信号最强的 biome，可代表这一框架的高敏感性特征排序。",
        "sem_label": "SEM 路径图",
        "biomes": [
            {
                "name": "Forest",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Forest/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/by_biome/RECO_code1_Forest_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Forest/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 5. Forest 中 SSRD 的 dependence plot。峰值前短波辐射仍是森林 RECO 恢复记忆最强的负向信号。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Forest/dependence_plots/prepeak_total_evaporation_mean.png",
                "dep2_caption": "图 6. Forest 中 EVA 的 dependence plot。蒸散增强对应更长恢复时间，反映热湿背景对呼吸偏离的累积作用。",
            },
            {
                "name": "Grassland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Grassland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/by_biome/RECO_code1_Grassland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Grassland/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 9. Grassland 中 SSRD 的 dependence plot。峰值前能量背景显著影响 RECO 恢复时间。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Grassland/dependence_plots/prepeak_total_precipitation_mean.png",
                "dep2_caption": "图 10. Grassland 中 PRE 的 dependence plot。前期降水异常会放大后续恢复尾部。",
            },
            {
                "name": "Savanna",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Savanna/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/by_biome/RECO_code1_Savanna_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Savanna/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 13. Savanna 中 SSRD 的 dependence plot。稀树草原 RECO 对峰值前辐射背景高度敏感。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Savanna/dependence_plots/prepeak_total_precipitation_mean.png",
                "dep2_caption": "图 14. Savanna 中 PRE 的 dependence plot。湿润异常会对应更长的呼吸恢复尾部。",
            },
            {
                "name": "Cropland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Cropland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/by_biome/RECO_code1_Cropland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Cropland/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 17. Cropland 中 SSRD 的 dependence plot。辐射增强仍然是最清晰的负向前置信号。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Cropland/dependence_plots/prepeak_total_evaporation_mean.png",
                "dep2_caption": "图 18. Cropland 中 EVA 的 dependence plot。较高峰值前蒸散通常预示更长的 RECO 恢复时间。",
            },
            {
                "name": "Shrubland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Shrubland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/by_biome/RECO_code1_Shrubland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Shrubland/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 21. Shrubland 中 SSRD 的 dependence plot。干旱适应系统仍保留明显的辐射记忆。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Shrubland/dependence_plots/prepeak_total_precipitation_mean.png",
                "dep2_caption": "图 22. Shrubland 中 PRE 的 dependence plot。湿润背景异常会显著拉长呼吸恢复尾部。",
            },
            {
                "name": "Wetland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Wetland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_prepeak_event_mechanism_20260421/by_biome/RECO_code1_Wetland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Wetland/dependence_plots/prepeak_ssrd_mean.png",
                "dep1_caption": "图 25. Wetland 中 SSRD 的 dependence plot。湿地对峰值前辐射异常呈现极强统计响应。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/prepeak_event_shap_sem_20260421/shap_by_biome/Wetland/dependence_plots/prepeak_total_evaporation_mean.png",
                "dep2_caption": "图 26. Wetland 中 EVA 的 dependence plot。蒸散背景也会共同塑造呼吸恢复记忆。",
            },
        ],
    },
    {
        "md": BASE / "reco_recoverywin_analysis_cn.md",
        "html": BASE / "reco_recoverywin_analysis_docx_source.html",
        "title": "RECO 过程解释口径单独解释分析",
        "overview_path": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/process_recoverywin_sem_path_diagrams_overview.png",
        "overview_caption": "图 1. RECO 过程解释口径的 SEM 路径图总览。恢复期补水、累计蒸散、温度与大气需求构成了主要过程框架。",
        "overview_beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Forest/feature_importance_beeswarm.png",
        "overview_beeswarm_caption": "图 2. Forest 的 SHAP beeswarm。该图代表性地展示了 RECO 过程解释口径下恢复期环境变量的高解释力排序。",
        "sem_label": "SEM 路径图",
        "biomes": [
            {
                "name": "Forest",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Forest/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/by_biome/RECO_code1_Forest_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Forest/dependence_plots/recoverywin_ssrd_mean.png",
                "dep1_caption": "图 5. Forest 中 SSRD 的 dependence plot。恢复期辐射背景变化会显著改变 RECO 恢复尾部。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Forest/dependence_plots/recoverywin_total_precipitation_mean.png",
                "dep2_caption": "图 6. Forest 中 PRE 的 dependence plot。恢复期补水增强往往对应更长的呼吸恢复尾部。",
            },
            {
                "name": "Grassland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Grassland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/by_biome/RECO_code1_Grassland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Grassland/dependence_plots/recoverywin_total_precipitation_mean.png",
                "dep1_caption": "图 9. Grassland 中 PRE 的 dependence plot。恢复期降水是草地 RECO 恢复的最直接信号。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Grassland/dependence_plots/recoverywin_strd_mean.png",
                "dep2_caption": "图 10. Grassland 中 STRD 的 dependence plot。长波背景同样参与调节呼吸恢复速度。",
            },
            {
                "name": "Savanna",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Savanna/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/by_biome/RECO_code1_Savanna_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Savanna/dependence_plots/recoverywin_total_precipitation_mean.png",
                "dep1_caption": "图 13. Savanna 中 PRE 的 dependence plot。恢复期补水是稀树草原 RECO 恢复的首要近端信号。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Savanna/dependence_plots/recoverywin_wind_speed_mean.png",
                "dep2_caption": "图 14. Savanna 中 WIND 的 dependence plot。风速变化反映了大气耦合对恢复尾部的调节。",
            },
            {
                "name": "Cropland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Cropland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/by_biome/RECO_code1_Cropland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Cropland/dependence_plots/01_recoverywin_total_precipitation_mean_dependence.png",
                "dep1_caption": "图 17. Cropland 中 PRE 的 dependence plot。农田 RECO 对恢复期补水呈现最显著的正向响应。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Cropland/dependence_plots/08_recoverywin_ssrd_mean_dependence.png",
                "dep2_caption": "图 18. Cropland 中 SSRD 的 dependence plot。辐射背景也显著影响农田系统恢复时间。",
            },
            {
                "name": "Shrubland",
                "beeswarm": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Shrubland/feature_importance_beeswarm.png",
                "sem": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/sem_recoverywin_gpp_precipEsum_vpd_hybrid_pruned_20260415/by_biome/RECO_code1_Shrubland_flash_SMrz_path_diagram.png",
                "dep1": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Shrubland/dependence_plots/09_recoverywin_strd_mean_dependence.png",
                "dep1_caption": "图 21. Shrubland 中 STRD 的 dependence plot。长波背景是灌丛 RECO 恢复的关键负向信号。",
                "dep2": "/home/xulc/flash_drought/process/SEM_analysis/codex/GLEAM/results/reco_code1_flash_smrz_mswepE_clean/shap_process_recoverywin_precipEmean_sample50k_by_biome/Shrubland/dependence_plots/01_recoverywin_total_precipitation_mean_dependence.png",
                "dep2_caption": "图 22. Shrubland 中 PRE 的 dependence plot。恢复期补水会显著延长呼吸返回基线的时间。",
            },
        ],
    },
]


def parse_markdown(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = ""
    intro_parts: list[str] = []
    table_lines: list[str] = []
    body_lines: list[str] = []
    state = "title"

    for line in lines:
        if state == "title" and line.startswith("# "):
            title = line[2:].strip()
            state = "intro"
            continue
        if state == "intro":
            if line.lstrip().startswith("|"):
                state = "table"
                table_lines.append(line)
            else:
                intro_parts.append(line)
            continue
        if state == "table":
            if line.lstrip().startswith("|"):
                table_lines.append(line)
            else:
                state = "body"
                body_lines.append(line)
            continue
        body_lines.append(line)

    intro_paragraphs = split_paragraphs(intro_parts)
    body_paragraphs = split_paragraphs(body_lines)
    biome_map: dict[str, list[str]] = {}
    overall: list[str] = []

    for paragraph in body_paragraphs:
        matched = False
        compound_prefixes = [
            ("Grassland 和 Savanna", ["Grassland", "Savanna"]),
            ("Grassland 与 Savanna", ["Grassland", "Savanna"]),
            ("Cropland 与 Shrubland", ["Cropland", "Shrubland"]),
            ("Cropland 和 Shrubland", ["Cropland", "Shrubland"]),
        ]
        for prefix, names in compound_prefixes:
            if paragraph.startswith(prefix):
                for name in names:
                    biome_map.setdefault(name, []).append(paragraph)
                matched = True
                break
        if matched:
            continue
        for biome in ("Forest", "Grassland", "Savanna", "Cropland", "Shrubland", "Wetland"):
            if paragraph.startswith(f"{biome} "):
                biome_map.setdefault(biome, []).append(paragraph)
                matched = True
                break
        if not matched:
            overall.append(paragraph)

    return {
        "title": title,
        "intro": intro_paragraphs,
        "table": parse_table(table_lines),
        "biome_paragraphs": biome_map,
        "overall": overall,
    }


def split_paragraphs(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            if current:
                paragraphs.append(" ".join(part.strip() for part in current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(part.strip() for part in current))
    return paragraphs


def parse_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    clean = [line.strip() for line in lines if line.strip()]
    header = [cell.strip() for cell in clean[0].strip("|").split("|")]
    rows = []
    for line in clean[2:]:
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return header, rows


def render_table(header: list[str], rows: list[list[str]]) -> str:
    thead = "".join(f"<th>{escape(cell)}</th>" for cell in header)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>")
    return "<table><tr>" + thead + "</tr>" + "".join(body) + "</table>"


def figure_grid(figures: list[tuple[str, str, str]]) -> str:
    cells = []
    for src, alt, caption in figures:
        cells.append(
            "<td>"
            f'<img src="{src}" alt="{escape(alt)}" />'
            f'<div class="caption">{escape(caption)}</div>'
            "</td>"
        )
    while len(cells) < 2:
        cells.append("<td></td>")
    return '<table class="figure-grid"><tr>' + "".join(cells[:2]) + "</tr></table>"


def biome_heading(index: int, name: str) -> str:
    return f"{index}. {name}"


def render_doc(config: dict) -> str:
    parsed = parse_markdown(config["md"])
    header, rows = parsed["table"]
    intro_html = "".join(f"<p>{escape(p)}</p>" for p in parsed["intro"])
    overall_paragraphs = parsed["overall"]
    overview_text = ""
    if overall_paragraphs:
        overview_text = "".join(f"<p>{escape(p)}</p>" for p in overall_paragraphs[:1])
    if len(overall_paragraphs) > 1:
        overview_tail = overall_paragraphs[1:]
    else:
        overview_tail = []

    sections = []
    for idx, biome in enumerate(config["biomes"], start=2):
        name = biome["name"]
        paragraphs = parsed["biome_paragraphs"].get(name, [])
        leading = paragraphs[:1]
        trailing = paragraphs[1:]
        section_parts = [f"<h2>{escape(biome_heading(idx, name))}</h2>"]
        section_parts.extend(f"<p>{escape(p)}</p>" for p in leading)
        section_parts.append(
            '<table class="figure-grid"><tr>'
            f'<td><img src="{biome["beeswarm"]}" alt="{name} beeswarm" />'
            f'<div class="caption">图 {2 + (idx - 2) * 4 + 1}. {escape(name)} 的 SHAP beeswarm。该图展示了该 biome 的特征重要性分布和变量贡献方向。</div></td>'
            f'<td><img src="{biome["sem"]}" alt="{name} sem path" />'
            f'<div class="caption">图 {2 + (idx - 2) * 4 + 2}. {escape(name)} 的 {escape(config["sem_label"])}。该图用于展示主要结构路径、潜在中介关系及其方向性。</div></td>'
            '</tr><tr>'
            f'<td><img src="{biome["dep1"]}" alt="{name} dependence 1" />'
            f'<div class="caption">{escape(biome["dep1_caption"])}</div></td>'
            f'<td><img src="{biome["dep2"]}" alt="{name} dependence 2" />'
            f'<div class="caption">{escape(biome["dep2_caption"])}</div></td>'
            "</tr></table>"
        )
        section_parts.extend(f"<p>{escape(p)}</p>" for p in trailing)
        sections.append("".join(section_parts))

    overview_fig = figure_grid(
        [
            (config["overview_path"], "overview", config["overview_caption"]),
            (config["overview_beeswarm"], "overview beeswarm", config["overview_beeswarm_caption"]),
        ]
    )
    overview_tail_html = "".join(f"<p>{escape(p)}</p>" for p in overview_tail)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>{escape(config["title"])}</title>
  <style>
    body {{
      font-family: "Arial", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
      font-size: 11pt;
      line-height: 1.55;
      color: #111;
      margin: 1cm;
    }}
    h1, h2, h3 {{
      color: #111;
      page-break-after: avoid;
    }}
    h1 {{
      font-size: 20pt;
      text-align: center;
      margin-bottom: 0.4cm;
    }}
    h2 {{
      font-size: 15pt;
      margin-top: 0.8cm;
      margin-bottom: 0.25cm;
      border-bottom: 1px solid #bbb;
      padding-bottom: 0.08cm;
    }}
    p {{
      text-align: justify;
      margin: 0.18cm 0;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 0.35cm 0 0.45cm 0;
      font-size: 9.5pt;
    }}
    th, td {{
      border: 1px solid #999;
      padding: 0.14cm 0.16cm;
      vertical-align: top;
    }}
    th {{
      background: #e8eef6;
      text-align: center;
      font-weight: 700;
    }}
    .figure-grid {{
      width: 100%;
      border-collapse: collapse;
      margin: 0.25cm 0 0.3cm 0;
    }}
    .figure-grid td {{
      border: none;
      width: 50%;
      padding: 0.08cm;
      vertical-align: top;
      text-align: center;
    }}
    img {{
      max-width: 100%;
      height: auto;
      border: 1px solid #ccc;
    }}
    .caption {{
      font-size: 9pt;
      color: #333;
      margin-top: 0.1cm;
      text-align: left;
    }}
  </style>
</head>
<body>
  <h1>{escape(parsed["title"] or config["title"])}</h1>
  {intro_html}
  <h2>1. 结果概览</h2>
  {overview_text}
  {render_table(header, rows)}
  {overview_fig}
  {overview_tail_html}
  {''.join(sections)}
</body>
</html>
"""


def main() -> None:
    for config in DOC_CONFIGS:
        config["html"].write_text(render_doc(config), encoding="utf-8")
        print(f"Wrote {config['html']}")


if __name__ == "__main__":
    main()
