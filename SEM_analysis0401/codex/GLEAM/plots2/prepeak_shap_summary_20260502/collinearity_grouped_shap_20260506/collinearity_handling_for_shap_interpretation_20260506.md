# SHAP 输入特征共线性处理说明

## 核心判断

当前 SHAP 输入变量确实存在共线性，最稳定的问题是 TMP-STRD 强相关。这个问题不会使模型预测或 SHAP 图本身失效，但会影响单变量贡献在相关变量之间的分配。因此，后续写作应避免把 SHAP 排名解释为完全独立的因果效应，而应采用机制组解释。

## 共线性诊断摘要

```csv
scenario,scope,n_samples,n_features,top_vif_feature,top_vif_label,top_vif,top_pearson_pair,top_pearson_abs_r,top_spearman_pair,top_spearman_abs_rho,high_vif_features,moderate_vif_features,condition_number
gpp_prepeak,overall,24837,12,prepeak_temperature_2m_mean,TMP,38.08140406188999,TMP vs STRD,0.8452611942767214,TMP vs STRD,0.8467884043714686,TMP; STRD; VPD,EVA; SSRD,15.782341683101397
gpp_recovery,overall,30000,9,recoverywin_temperature_2m_mean,TMP,18.72305830527024,TMP vs STRD,0.920040848503786,TMP vs STRD,0.926033171757587,TMP; STRD,SSRD; EVA; VPD,11.97737060855958
reco_prepeak,overall,29837,12,prepeak_temperature_2m_mean,TMP,16.664111977915777,TMP vs STRD,0.869218608268917,TMP vs STRD,0.9030341852813186,TMP; STRD,EVA; VPD; SSRD,9.895698038011322
reco_recovery,overall,30000,9,recoverywin_temperature_2m_mean,TMP,17.62374115506076,TMP vs STRD,0.92312900953019,TMP vs STRD,0.9290452729536977,TMP; STRD,SSRD; EVA,11.675914207211454
```

## 整体机制组 SHAP 贡献

```csv
metric,mechanism_group,mean_abs_shap,percent,group_rank
GPP,辐射热力组,24.339895423852212,47.401535994442476,1
GPP,水分供给/储存组,12.496220330102465,24.33617842052699,2
GPP,大气需水组,6.67137405883768,12.992388507655086,3
GPP,事件属性组,6.3439844178666025,12.354802701288378,4
GPP,植被状态组,1.49685217527419,2.915094376087071,5
RECO,辐射热力组,26.115060240680343,50.60174852798545,1
RECO,水分供给/储存组,11.907314123801392,23.072162552309337,2
RECO,大气需水组,6.140415823194147,11.897953689515914,3
RECO,事件属性组,5.8019552992410155,11.24213692471107,4
RECO,植被状态组,1.6442621074300263,3.185998305478235,5
```

## 最小修改方案

1. 保留原始 SHAP 图和单变量排序。
2. 新增 VIF、相关矩阵和条件数作为补充材料。
3. 正文使用机制组解释：辐射热力组、大气需水组、水分供给/储存组、事件属性组。
4. SEM 采用分层路径，避免所有高相关变量平行直连恢复时间。
5. 如需更强稳健性，可补 reduced-feature 或 residualized-feature 敏感性模型。
