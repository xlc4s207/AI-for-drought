# 全特征 SHAP 机制解释补充与现有讨论稿对照（中文）

本说明基于 `dual_precip_shap_20260418/shap_by_biome` 下五个 biome 的 `dependence_plot_data.parquet`、`feature_importance.csv` 和 `run_summary.txt`，重点补充除 `recoverywin_total_precipitation_mean`（PRE）与 `recoverywin_ssrd_mean`（SSRD）之外其余特征的 SHAP 解释，并与现有稿件 `all_features_shap_mechanism_cn.md` 的主要结论进行核对。这里的判断以分箱中位数 SHAP 曲线为准，因此适合用于机制讨论与相对比较，但不应被当作严格的因果函数。

从特征重要性看，除 PRE 与 SSRD 外，跨 biome 最稳定且最值得强调的特征主要有四类。第一类是 `recoverywin_VPD_mean`，它在五个 biome 中都表现为最稳定的正向胁迫信号。Cropland、Forest、Grassland 与 Shrubland 都近似单调递增，Savanna 虽然在高端略有钝化，但整体仍是 VPD 增大、SHAP 增大的结构。Forest 的斜率最强，左端平滑 SHAP 约为 `-6.35`，右端可升至 `+10.34`，明显高于其他 biome，说明森林恢复对大气水分需求最敏感。这个结论与现有 `all_features_shap_mechanism_cn.md` 的核心判断是一致的，因此 VPD 部分可以基本保留，只需在行文中再强调一句：Savanna 的高端钝化与 Shrubland 的局部非线性不改变 VPD 作为跨 biome 共同限速因子的主结论。

第二类是 `recoverywin_temperature_2m_mean` 与 `recoverywin_strd_mean`。温度在五个 biome 中总体都呈现“低温对应正 SHAP、高温对应负 SHAP”的结构，只是 Cropland 的高温端趋于平缓，Grassland 与 Shrubland 的温度斜率最陡，分别从约 `+11.07` 和 `+12.27` 下降到负值区间，说明草地和灌丛恢复对冷季或低温背景的生长季限制最强。`recoverywin_strd_mean` 在五个 biome 中也都呈显著递减关系，Forest、Grassland、Savanna 和 Shrubland 的右端负 SHAP 幅度都很大，说明高 STRD 主要对应更暖湿、恢复更活跃的背景。这一点与现有稿件总体一致，但建议将原稿中关于 STRD 的物理表述进一步收紧：更稳妥的写法是把 STRD 视为“温度—水汽联合背景指标”，而不是直接把长波辐射本身作为单一生理驱动解释。

第三类是 `prepeak_total_precipitation_mean`，它在 biome 间方向差异很明显。Cropland 呈显著负相关，Forest 为弱 U 型或高端略回升，Grassland 只在极低值端为负、之后整体较弱，Savanna 在中高值端转为更负，而 Shrubland 则是最清晰的正向上升。这说明 prepeak 降水不能写成统一的“前期越湿、恢复越快”机制，而应该明确拆成两组。对于 Cropland、部分 Forest 与 Savanna，可以写作“较湿的前期背景通常意味着更充足的储水基础，因此恢复时间缩短”；而对于 Shrubland，应单独解释为“相对湿润异常”机制，即干适应系统中罕见的前期偏湿往往对应植被活性被短暂抬高，后续骤旱发生时回归原有干旱基线所需的恢复距离反而更长。现有稿件在这一点上的判断总体正确，尤其是对 Shrubland 方向反转的强调是应当保留的。

第四类是 `recoverywin_total_evaporation_mean`、`recoverywin_wind_speed_mean`、`recoverywin_SMrz_mean` 与 `recoverywin_lai_total_mean`。这四个特征更容易混入样本结构信号，因此论文里不应写得过满。蒸散 `recoverywin_total_evaporation_mean` 在 Forest 与 Savanna 中呈明显递增结构，即从强蒸散端的负 SHAP 过渡到弱蒸散端的正 SHAP，这支持“强蒸散代表恢复期系统仍较活跃、恢复更快”的解释；但在 Cropland、Grassland 与 Shrubland 中它更接近倒 U 或弱非单调，因此更合适的表述应是：蒸散在部分 biome 中可以作为系统活性的复合指标，但在干旱或农田系统中同时也携带截断事件、干透样本和管理背景的信息，因此不具备统一方向。现有稿件在 Forest/Savanna 上的解释基本成立，但对 Cropland 与 Shrubland 的叙述应更谨慎，避免写成过于强的统一机制。

风速 `recoverywin_wind_speed_mean` 则比现有稿件更稳定。五个 biome 中几乎都是“低风速端正 SHAP、高风速端负 SHAP”的递减曲线，其中 Grassland、Savanna 和 Shrubland 下降最明显。也就是说，风速并不表现为跨 biome 的直接生理胁迫项，而更像是高风—高蒸散需求—低湿润度组合的判别指示。现有稿件把它解释为“联合水气候状态指示器”是合适的，这一部分可以保留，甚至可以写得更明确一些：风速方向之所以与 VPD 的正 SHAP 不一致，并不是因为二者作用相反，而是因为风速在给定 VPD 之外进一步标记出了干热大陆型短事件样本。

土壤水 `recoverywin_SMrz_mean` 是现有稿件中最需要收敛表述的部分。Forest 确实呈现最接近经典供水效应的结构，即中低 SMrz 对应正 SHAP，而高 SMrz 端转向明显负 SHAP，这支持“更多根区土壤水有助于加快恢复”的解释。但 Cropland 与 Savanna 只是宽峰型倒 U，Grassland 为明显递增，Shrubland 则几乎接近平坦并伴随非常窄的取值范围。换言之，SMrz 只有在 Forest 中能较直接地解释为供水机制，在其他 biome 中更多还是生态系统类型差异、湿润—干旱亚区分层和 PRE 共变结构的投影。因此，现有稿件把 Forest 单独指出来是对的，但对于 Grassland 的“反向机制”与 Cropland/Savanna 的“过渡区效应”，建议明确加一句：这些方向更可能反映样本组成，而非土壤水单变量的直接生理作用。

LAI `recoverywin_lai_total_mean` 也属于应当弱化物理解释的变量。它在五个 biome 中重要性都很低，均排在末位附近，而且形态差异很大：Cropland、Grassland 和 Shrubland 大致表现为低值负、高值略正；Savanna 则相反，近似低值正、高值负；Forest 则接近弱倒 U。这意味着 LAI 在当前模型中更适合被解释为“生态系统结构或植被类型分层的辅助变量”，而不适合作为独立机制主角。现有稿件已经提到“LAI 重要性最低、解释应克制”，这个判断是正确的，建议继续保留。

综合来看，`all_features_shap_mechanism_cn.md` 的整体框架是可以保留的，尤其是关于 VPD、温度、STRD 和 prepeak PRE 的大方向判断，与当前重新核验的 `shap_by_biome` 数据基本一致。需要修订的地方主要有三点。第一，SMrz 不能在所有 biome 中被写成同一类供水机制，只有 Forest 比较符合经典供水解释，其余 biome 应明确写为样本结构或亚区分层效应。第二，蒸散 ET 的方向不够稳定，在 Cropland、Grassland 和 Shrubland 中应弱化统一机制措辞，避免过度解释。第三，LAI 与 wind 更应被表述为生态结构或联合气候状态指示量，而不是直接的单变量生理因子。换句话说，现有稿件最值得保留的是“跨 biome 共同限速因子”和“biome 依赖性方向反转”这两个层次，而最需要收敛的是对若干非主导变量的强机制化表述。

如果要把这份结论压缩成论文讨论里的一个更稳妥版本，可以概括为：在 PRE 与 SSRD 之外，VPD、温度和 STRD 构成了跨 biome 最稳健的共同恢复限速因子，而 prepeak PRE、SMrz、ET、LAI 与 wind 的 SHAP 方向则具有更强的 biome 依赖性，反映的是植被类型、水热背景和事件结构共同变化的复合信号。这个写法既能保留现有讨论稿的大框架，又能避免把所有特征都解释成同等强度的直接生理机制。
