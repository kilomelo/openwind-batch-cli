# Real Data Template

这个目录给你填真实实验数据用，结构已经和当前 `owbatch inspect` / `owbatch run` 的参数约定对齐。

## 目录结构

- `template/bore_template.csv`
- `template/holes_template.csv`
- `template/fingering_template.csv`
- `cases.csv`

## 填写说明

当前版本的共通约定：
- 长度、位置、直径一律按毫米 `mm` 填。
- 当前 CLI 会把 bore / hole 的直径字段按 `diameter=True` 传给 OpenWind。
- 所有表头建议使用简单 ASCII 名称，避免空格和 `#`。
- `case_id` 会参与输出文件名，建议只用字母、数字、下划线、减号。

### `template/bore_template.csv`

列说明：
- `segment`
  段编号或段名。建议从 `1` 开始连续编号，例如 `1`, `2`, `3`。
  作用：
  - 便于在 `cases.csv` 中用 `bore_2_d1` 这类字段覆盖
  - 便于人工阅读和排错
- `x0`
  本段起点轴向位置，单位 mm。
- `x1`
  本段终点轴向位置，单位 mm。
  一般要求：
  - `x1 > x0`
  - 与上一段首尾相接
- `d0`
  在 `x0` 处的内径，单位 mm。
- `d1`
  在 `x1` 处的内径，单位 mm。
- `type`
  bore 形状类型字符串。
  当前建议值：
  - `linear`
  - `exponential`
  - `circle`
  - `bessel`
  说明：
  - 最稳妥先用 `linear`
  - OpenWind 底层还支持 `spline`，但当前 owbatch 的 `param` 只有单列，不适合直接表达多参数 spline
- `param`
  某些 `type` 需要的附加参数。
  建议：
  - `linear`：留空
  - `exponential`：留空
  - `circle`：填圆弧参数的单个数值
  - `bessel`：填 Bessel 形状参数 `alpha`

示例：

```csv
segment,x0,x1,d0,d1,type,param
1,0,120,14,14,linear,
2,120,420,14,20,linear,
```

### `template/holes_template.csv`

列说明：
- `label`
  孔或阀的唯一名字。
  作用：
  - 在 `fingering_template.csv` 中按这个名字写指法
  - 在 `cases.csv` 中可用 `hole_<label>_<field>` 覆盖
  建议：
  - 用短且稳定的名字，例如 `h1`, `h2`, `thumb`, `vent`
  - 避免空格和 `#`
- `position`
  孔中心或阀接出点在主管上的轴向位置，单位 mm。
- `length`
  孔 chimney 长度，或 valve 偏路管长度，单位 mm。
- `diameter`
  孔或 valve 管道内径，单位 mm。
- `type`
  side component 的管型字符串。
  当前建议值：
  - `linear`
  说明：
  - 当前最稳妥只填 `linear`
- `group`
  你自己定义的分组标签。
  当前内置只识别一个特殊值：
  - `upper`
  作用：
  - 若 `cases.csv` 使用 `upper_holes_shift`，只有 `group=upper` 的孔会被整体平移
  其它字符串目前只作为备注，不参与计算逻辑
- `variety`
  side component 类型。
  可选值：
  - `hole`
  - `valve`
  说明：
  - 留空时当前工具会按 `hole` 处理
  - 如果某一行填 `valve`，则该行必须再提供 `reconnection`
- `reconnection`
  仅对 `variety=valve` 有意义，表示偏路管重新接回主管的位置，单位 mm。
  普通孔可留空。

示例：

```csv
label,position,length,diameter,type,group,variety,reconnection
h1,180,10,4.0,linear,upper,,
h2,240,10,4.5,linear,upper,,
```

### `template/fingering_template.csv`

列说明：
- `label`
  第 1 列必须是 `label`。
  每一行对应一个 hole / valve 名，必须和 `holes_template.csv` 里的 `label` 一致。
- 其余各列
  每一列列名都是一个 note 或 fingering 名，例如：
  - `G4`
  - `A4`
  - `all_open`
  - `fork_G4`

重要约定：
- `cases.csv` 里的 `note` 必须和这里的列名一致
- 当前建议 note 名只用简单 ASCII 名称
- 不建议直接用带空格或 `#` 的名字；若一定要用，OpenWind 会做 label 清洗，容易造成 case 里的 `note` 对不上

单元格可选值：
- `o` 或 `open`
  表示开孔 / 抬起
- `x` 或 `closed`
  表示闭孔 / 按下
- `c`
  等价于 `closed`
- `0.5` 或 `.5`
  半开状态

建议：
- 第一版先只用 `o` / `x`

示例：

```csv
label,G4,A4
h1,x,o
h2,o,x
```

### `cases.csv`

固定列说明：
- `case_id`
  用例唯一标识。
  作用：
  - 出现在汇总输出行里
  - 用于生成 `impedances/<case_id>.csv`
  建议：
  - 只用字母、数字、下划线、减号
- `note`
  本 case 使用的 fingering 名。
  必须和 `fingering_template.csv` 的某个列名一致。
- `f_start`
  扫频起点，单位 Hz。
- `f_stop`
  扫频终点，单位 Hz。
- `f_step`
  频率步长，单位 Hz。
- `temperature_c`
  温度，单位摄氏度。
- `losses`
  热黏性损耗模型。
  当前可填：
  - 布尔型：`true`, `false`, `yes`, `no`, `on`, `off`, `1`, `0`
  - OpenWind 字符串：`bessel`, `wl`, `keefe`, `diffrepr`, `diffrepr+`
  建议：
  - 第一轮排错先用 `false`
  - 想更接近真实可再试 `bessel`
- `compute_method`
  频域求解方法。
  可选值：
  - `TMM`
  - `FEM`
  - `hybrid`
  - `modal`
  建议：
  - 第一轮先用 `TMM`
- `radiation_category`
  辐射边界模型。
  常用值：
  - `unflanged`
  - `infinite_flanged`
  - `closed`
  - `perfectly_open`
  建议：
  - 第一轮先用 `unflanged`
- `spherical_waves`
  是否启用球面波修正。
  当前可填：
  - 布尔型：`true`, `false`, `yes`, `no`, `on`, `off`, `1`, `0`
  - OpenWind 特殊字符串：`spherical_area_corr`
  建议：
  - 第一轮先用 `false`
- `flute_type_instrument`
  是否按 flute-like player 计算。
  当前可填：
  - 布尔型：`true`, `false`, `yes`, `no`, `on`, `off`, `1`, `0`
  当前 owbatch 行为：
  - `true`：若未显式指定 `player_preset`，自动映射到 `Player("FLUTE")`
  - `false`：若未显式指定 `player_preset`，自动映射到 `Player("UNITARY_FLOW")`
  说明：
  - 这是为了对照官方 demo 的 “Flute-type instrument” 开关加入的验证版选项
- `player_preset`
  显式指定 OpenWind 的 `Player(...)` 预设名。
  常用值：
  - `UNITARY_FLOW`
  - `FLUTE`
  - `SOPRANO_RECORDER`
  建议：
  - 需要复核 flute-like 假设时，优先直接写 `FLUTE`
  - 若同时填写 `flute_type_instrument`，两者必须逻辑一致
  说明：
  - `FLUTE` / `SOPRANO_RECORDER` 不只是名字不同，它们会带入 OpenWind 内置的 flute/window 激励参数
  - 其中 `FLUTE` 预设还自带 embouchure/window 的 `radiation_category`
- `source_location`
  OpenWind 的声源位置标签。
  常用值：
  - `entrance`
  - 某个 hole 的 `label`
  说明：
  - 留空时使用 OpenWind 默认值，通常是 `entrance`
  - 若填某个 hole label，该标签必须存在于 `holes_template.csv`
- `bore_all_diameter_offset`
  对所有 bore 段的 `d0` / `d1` 统一加一个偏移量，单位 mm。
- `all_hole_diameter_scale`
  对所有孔的 `diameter` 统一乘一个缩放系数。
- `upper_holes_shift`
  对 `group=upper` 的孔统一加一个位置偏移，单位 mm。

按需新增的覆盖列：
- `bore_<segment>_<field>`
  例如：
  - `bore_2_d1`
  - `bore_3_type`
  当前 `<field>` 可用：
  - `x0`, `x1`, `d0`, `d1`, `type`, `param`
- `hole_<index>_<field>`
  用 1-based 序号引用孔，例如：
  - `hole_1_position`
  - `hole_2_diameter`
- `hole_<label>_<field>`
  用孔名引用孔，例如：
  - `hole_h1_position`
  - `hole_thumb_diameter`
  当前 `<field>` 可用：
  - `label`, `position`, `length`, `diameter`, `type`, `variety`, `reconnection`, `group`

建议最小起步行：

```csv
case_id,note,f_start,f_stop,f_step,temperature_c,losses,compute_method,radiation_category,spherical_waves,flute_type_instrument
base,G4,100,3000,5,25,false,TMM,unflanged,false,true
```

## 当前流程

## 响应图语义

当前 owbatch 的频域可视化遵循与 OpenWind demo 对齐的语义，但在实现上暂时固定 `Zc0 = 1`。

因此：
- 阻抗模式：
  - 上图画 `|Z|`
  - 下图画 `angle(Z)`
- 导纳模式：
  - 上图画 `|Y| = |1 / Z|`
  - 下图画 `angle(Y) = angle(1 / Z)`

这套逻辑不是只存在于画图层，而是由共享的响应派生层统一提供，后续 `features.csv` / `analysis.csv` 也会基于同一套语义。

当前 `impedance.csv` 还会带出一些和语义选择相关的元数据列，便于后续自动分析：
- `player_preset`
- `is_flute_like`
- `default_response_mode`
- `primary_feature_family`

填完之后可先跑：

```bash
PYTHONPATH=src /Users/chenweichu/dev/miniconda3/envs/openwind-cli/bin/python -m owbatch.cli inspect \
  --template-dir examples/real_data/template \
  --cases examples/real_data/cases.csv
```

确认展开结果无误后再跑：

```bash
PYTHONPATH=src /Users/chenweichu/dev/miniconda3/envs/openwind-cli/bin/python -m owbatch.cli run \
  --template-dir examples/real_data/template \
  --cases examples/real_data/cases.csv \
  --out-dir examples/real_data/out
```

当前会得到：
- `examples/real_data/out/impedance.csv`
- `examples/real_data/out/impedances/<case_id>.csv`
- `examples/real_data/out/features.csv`
  当前默认写每个 case 主特征族前 `3` 个峰值频率与 Q-factor
- `examples/real_data/out/analysis.csv`
  当前默认按这 `3` 个主峰汇总最近音高、音分偏差、相对 `f1` 最近整数倍的倍频偏差，以及 `q1` / `q2` / `q3`

## 简单绘图

可以直接把 `out/impedance.csv` 画成每个 case 一条线的双图响应。

按自动语义响应绘图：

```bash
PYTHONPATH=src /Users/chenweichu/dev/miniconda3/envs/openwind-cli/bin/python -m visulization.plot_impedance \
  --input examples/real_data/out/impedance.csv \
  --output examples/real_data/out/auto_response.png
```

默认 `--mode auto`：
- flute-like preset 会优先画 admittance 语义
- 非 flute-like preset 会优先画 impedance 语义

显式画阻抗语义响应：

```bash
PYTHONPATH=src /Users/chenweichu/dev/miniconda3/envs/openwind-cli/bin/python -m visulization.plot_impedance \
  --input examples/real_data/out/impedance.csv \
  --mode impedance \
  --output examples/real_data/out/impedance_response.png
```

画导纳语义响应：

```bash
PYTHONPATH=src /Users/chenweichu/dev/miniconda3/envs/openwind-cli/bin/python -m visulization.plot_impedance \
  --input examples/real_data/out/impedance.csv \
  --mode admittance \
  --angle-unit deg \
  --output examples/real_data/out/admittance_response.png
```

也可以把分析表画成 case 对应的倍频偏差折线图：

```bash
PYTHONPATH=src /Users/chenweichu/dev/miniconda3/envs/openwind-cli/bin/python -m visulization.plot_analysis \
  --input examples/real_data/out/analysis.csv \
  --output examples/real_data/out/analysis_deviation.png
```

这个图会自动查找非空的 `deltaN_cents` 列：
- 如果当前分析表是 `f1/f2/f3`，则画 `delta2_cents`、`delta3_cents`
- 如果以后扩展到 `f4`，则会额外画 `delta4_cents`

如果你想在窗口里用鼠标查看某个点的精确数值，可以用交互式查看工具：

```bash
PYTHONPATH=src /Users/chenweichu/dev/miniconda3/envs/openwind-cli/bin/python -m visulization.view_analysis \
  --input examples/real_data/out/analysis.csv
```

打开窗口后，把鼠标悬停到折线点上，会显示：
- `case`
- `note`
- `deltaN_cents`
- 对应峰值频率 `fN`
- 对应比值 `hN`
- 最近整数倍
