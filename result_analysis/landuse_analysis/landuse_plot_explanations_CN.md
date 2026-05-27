# 土地利用类型分组图件说明

## 图件位置

所有图件位于：

`/home/xulc/flash_drought/process/result_analysis/landuse_analysis/plots`

每个通量均输出了 4 张图：

- `*_directional_change_abs_mean_by_landuse.png`
- `*_t_response_mean_by_landuse.png`
- `*_t_impact_mean_by_landuse.png`
- `*_t_recover_mean_by_landuse.png`

其中：

- `GPP`、`NEE` 和 `RECO` 现在都按可用数据绘制四种情景
- 若个别图中某一情景缺席，应以对应汇总表中的事件数为准核查

## 一、如何读图

### 1. 横轴

横轴为 MODIS `LC_Type1` 中保留的“一般有植被或常用于陆地生态分析”的土地利用类型。

为避免非典型植被区干扰当前图件解读，绘图时已经去除：

- `Water Bodies`
- `Snow and Ice`
- `Barren or Sparsely Vegetated`

因此当前图中展示的类别包括：

- `Evergreen Needleleaf Forest`
- `Evergreen Broadleaf Forest`
- `Deciduous Needleleaf Forest`
- `Deciduous Broadleaf Forest`
- `Mixed Forests`
- `Closed Shrublands`
- `Open Shrublands`
- `Woody Savannas`
- `Savannas`
- `Grasslands`
- `Permanent Wetlands`
- `Croplands`
- `Urban and Built-up`
- `Cropland and Natural Vegetation Mosaic`

### 2. 颜色

颜色代表不同干旱情景：

- `flash+SMrz`
- `flash+SMs`
- `nonflash+SMrz`
- `nonflash+SMs`

### 3. 纵轴

不同图的纵轴含义不同：

- `directional_change_abs_mean`
  - `GPP`、`RECO` 表示平均下降值 `drop_abs`
  - `NEE` 表示平均不利变化值 `rise_abs`
- `t_response_mean` 表示平均响应时间
- `t_impact_mean` 表示平均影响持续时间
- `t_recover_mean` 表示平均恢复时间

因此：

- 柱越高，不代表一定“更严重”，要结合指标本身解释
- 在 `directional_change_abs_mean` 图中，越高表示干旱造成的不利变化越强
- 在时间类图中，越高表示过程越慢、持续越长或恢复越慢

## 二、GPP 图件解读

### 1. `gpp_directional_change_abs_mean_by_landuse.png`

这张图反映不同土地利用类型中，GPP 在不同干旱情景下的平均下降值。

从汇总表看，最显著的高值主要出现在：

- `Evergreen Broadleaf Forest`
- `Deciduous Broadleaf Forest`
- `Mixed Forests`
- `Croplands`
- `Cropland and Natural Vegetation Mosaic`

说明森林和农田系统中的 GPP 对干旱冲击更敏感，生产力下降更强。

同时在多数土地利用类型中：

- `flash+SMs` 的下降值往往大于 `nonflash+SMs`

说明骤旱在 GPP 上更强调“快速且更深的塌陷”。

### 2. `gpp_t_response_mean_by_landuse.png`

这张图反映不同土地利用类型中，GPP 对干旱开始做出响应所需的时间。

整体上可以看到：

- `flash` 通常明显短于 `nonflash`
- 森林、农田、草地和稀树草原类型在 `nonflash` 下响应时间往往更长

这说明慢旱更偏“累积到阈值后再响应”，而骤旱则更快触发 GPP 抑制。

### 3. `gpp_t_impact_mean_by_landuse.png`

这张图反映 GPP 受干旱影响持续多久。

典型特征是：

- `nonflash` 几乎在所有主要土地利用类型中都高于 `flash`
- `Croplands`、`Deciduous Broadleaf Forest`、`Grasslands` 等类型下影响持续时间更长

说明慢旱在生产端造成更明显的拖尾效应。

### 4. `gpp_t_recover_mean_by_landuse.png`

这张图用于比较不同土地利用类型的恢复难度。

整体上：

- `Closed Shrublands`
- `Grasslands`
- 部分灌丛和草地相关类型

恢复时间更长。

这说明在水分本就受限或环境更极端的类型中，GPP 恢复通常更慢。

## 三、NEE 图件解读

### 1. `nee_directional_change_abs_mean_by_landuse.png`

这张图中的高值表示：

- 干旱后 `NEE` 上升更明显
- 即碳汇减弱更强，或更接近碳源化

高值主要出现在：

- `Deciduous Broadleaf Forest`
- `Evergreen Needleleaf Forest`
- `Open Shrublands`

这说明这些土地利用类型中，干旱更容易削弱净碳汇功能。

### 2. `nee_t_response_mean_by_landuse.png`

读取方式与 GPP 一样，但解释要注意：

- `NEE` 是 GPP 与 RECO 共同作用后的综合结果

因此这张图更多反映“净碳交换系统何时开始明显偏离原状态”，而不只是单一生产或呼吸过程。

通常：

- `flash` 更快
- `nonflash` 更慢

说明净碳汇的削弱在慢旱下更偏累积型。

### 3. `nee_t_impact_mean_by_landuse.png`

这张图反映净碳交换异常持续多久。

如果某类土地利用的 `nonflash` 柱明显更高，说明：

- 慢旱会让该类型在更长时间内维持碳汇减弱状态

这在灌丛、草地、农田等类型中尤其值得关注。

### 4. `nee_t_recover_mean_by_landuse.png`

这张图可以用来识别哪些土地利用类型的净碳汇恢复最慢。

如果恢复时间长，说明干旱结束后系统仍需更长时间才能回到原有净交换状态。

在解释时要记住：

- `NEE` 恢复慢，不一定意味着生产恢复慢，也可能意味着呼吸和生产恢复不同步

## 四、RECO 图件解读

### 1. `reco_directional_change_abs_mean_by_landuse.png`

这张图反映不同土地利用类型中，生态系统呼吸受到干旱后下降的强度。

高值主要出现在：

- `Evergreen Broadleaf Forest`
- `Deciduous Broadleaf Forest`
- `Mixed Forests`
- `Woody Savannas`

说明这些类型中的呼吸过程在干旱下也会出现明显抑制。

### 2. `reco_t_response_mean_by_landuse.png`

这张图可用来判断呼吸过程对干旱的启动响应速度。

通常表现为：

- `flash` 较快
- `nonflash` 较慢

但不同于 GPP，某些灌丛和开阔植被类型下 RECO 可能更快做出变化，反映出呼吸对环境胁迫的直接调节。

### 3. `reco_t_impact_mean_by_landuse.png`

这张图在当前结果中很重要，因为：

- 很多土地利用类型里 `nonflash` 的 `t_impact` 明显高于 `flash`

说明 RECO 在慢旱下更容易表现为长时间持续偏离，而不是短时冲击。

### 4. `reco_t_recover_mean_by_landuse.png`

这张图用于识别呼吸恢复最慢的土地利用类型。

如果某类型 `t_recover` 特别高，说明土壤和植被呼吸过程在干旱过后恢复较慢，存在更强的后效应。

当前结果中：

- 部分灌丛与草地

是值得重点关注的慢恢复类型。

## 五、综合如何写进正文

如果你要把这些图写进论文或报告，可以按下面逻辑描述：

1. 先说明不同土地利用类型对干旱的敏感性不同，森林、农田、灌丛和草地在三类通量上表现出明显差异。
2. 再说明 `flash` 与 `nonflash` 的分工：
   - `flash` 更偏快速触发和更强瞬时变化
   - `nonflash` 更偏长持续时间和慢恢复
3. 最后按通量区分：
   - `GPP` 更突出生产力下降
   - `NEE` 更突出净碳汇减弱
   - `RECO` 更突出长期拖尾影响

## 六、解释边界

- `1982-2000` 使用 `2001` 土地利用图代替，这是一种近似
- 当前图件已经主动去除了 `Water Bodies`、`Snow and Ice` 和 `Barren or Sparsely Vegetated` 三类，以减少非典型植被区对视觉解读的干扰
