# owbatch

`owbatch` 是一个面向 OpenWind 的纯命令行批处理工具骨架，目标是把 OpenWind 当作频域求解内核，用 CSV 驱动模板、参数扫描、特征提取和结果导出。

当前仓库处于第一阶段：
- 已初始化 Python 项目骨架
- 已提供最小 CLI 框架
- 已写入输入 schema 草案
- 已实现模板加载与 case 展开
- 已打通最小 OpenWind 频域调用
- 已提供 fixture 和 smoke test

## 当前范围

第一版目标：
- 频域批处理
- 单机命令行
- CSV 输入输出
- 基于“模板 + case 覆盖”的工作流
- 导出阻抗/导纳原始数据与共振特征

暂不包含：
- Web / GUI
- 数据库
- 时域分析
- 自动优化器 UI

## 安装

开发安装：

```bash
python -m pip install -e ".[dev]"
```

安装后可用命令：

```bash
owbatch --help
owbatch inspect --help
owbatch run --help
```

## CLI 草案

### `owbatch inspect`

用途：
- 检查模板目录和 `cases.csv` 的输入约定
- 打印本次批处理请求的摘要
- 后续将用于查看展开后的几何和求解参数

当前状态：
- 已能加载模板和 `cases.csv`
- 已能打印展开后的 bore / holes / fingering / solver 参数
- 当前输出格式为 JSON，便于排查 case 覆盖结果

示例：

```bash
owbatch inspect --template-dir ./templates/xiao_a --cases ./cases.csv
```

### `owbatch run`

用途：
- 批量执行 case
- 后续输出 `impedance.csv`、`features.csv`、`analysis.csv`

当前状态：
- 已能执行最小频域批处理
- 已输出 `impedance.csv`
- 已为每个 case 额外输出一个阻抗列表文件到 `impedances/`
- 已输出 `features.csv`，当前默认提取每个 case 主特征族的前 `3` 个峰值频率和 Q-factor
- 已输出 `analysis.csv`，当前默认基于前 `3` 个主峰汇总音高、倍频偏差与 Q-factor

示例：

```bash
owbatch run \
  --template-dir ./templates/xiao_a \
  --cases ./cases.csv \
  --out-dir ./out
```

## 输入 Schema 草案

### 模板目录

模板目录最少需要：
- `bore_template.csv`

可选文件：
- `holes_template.csv`
- `fingering_template.csv`

说明：
- `holes_template.csv` 对无音孔乐器可以省略，或保留为只有表头的空表
- `fingering_template.csv` 对无音孔且不使用 `note` 指法切换的情况可以省略，或保留为只有 `label` 表头的空表
- 如果 `holes_template.csv` 和 `fingering_template.csv` 文件存在但没有数据行，也会按无孔乐器处理
- 这种无孔情形下，即使 `cases.csv` 里的 `note` 不为空，也不会阻止计算；该 `note` 会保留在输出中，但不会参与 OpenWind 指法切换

当前最小 schema：

`bore_template.csv`
- 必需列：`x0`, `x1`, `d0`, `d1`, `type`
- 可选列：`segment`, `param`
- 当前约定使用几何单位 `mm`
- 当前约定使用直径列 `d0` / `d1`，运行时以 `unit="mm"` 和 `diameter=True` 传给 OpenWind

`holes_template.csv`
- 必需列：`label`, `position`, `length`, `diameter`
- 可选列：`type`, `group`, `variety`, `reconnection`
- 文件可为空表；对无音孔乐器也可以直接省略

`fingering_template.csv`
- 第一列必须是 `label`
- 其余列名视为 note 名
- 单元格使用 OpenWind 兼容的 `o` / `x`
- 文件可为空表；若模板存在 hole 数据行且 `cases.csv` 里使用了 `note`，则仍需要相应的指法列名
  例外：
  - 如果模板整体没有任何 hole 数据行，则即使 `note` 不为空，也按无孔乐器处理，不要求存在对应指法列

### `cases.csv`

一行一个 case，只填写变化参数和求解参数。当前先确定字段分组，不在这一阶段绑定到具体解析逻辑。

保留字段：
- `case_id`
- `skip`
- `note`
- `f_start`
- `f_stop`
- `f_step`
- `temperature_c`
- `losses`
- `compute_method`
- `radiation_category`
- `spherical_waves`
- `flute_type_instrument`
- `player_preset`
- `source_location`

派生/批量变换字段草案：
- `bore_all_diameter_offset`
- `all_hole_diameter_scale`
- `upper_holes_shift`

逐项覆盖字段示例：
- `hole_5_position`
- `hole_5_diameter`
- `bore_2_d1`

约定：
- `skip` 放在 `case_id` 与 `note` 之间；值为 `y` 时跳过该 case，不参与展开和计算；值为 `n` 或空值时正常计算
- case 行中的非空字段覆盖模板默认值
- 未识别字段先保留为原始覆盖项，后续由 case 展开层解释
- 当前已支持的逐项覆盖：
  - `bore_<segment>_<field>`，例如 `bore_2_d1`
  - `hole_<index>_<field>` 或 `hole_<label>_<field>`，例如 `hole_1_position`
- 当前已支持的派生字段：
  - `bore_all_diameter_offset`
  - `all_hole_diameter_scale`
  - `upper_holes_shift`，要求 `holes_template.csv` 中存在 `group=upper`
- 当前已支持的 player/source 字段：
  - `flute_type_instrument`：`true` 时默认映射到 `Player("FLUTE")`，`false` 时默认映射到 `Player("UNITARY_FLOW")`
  - `player_preset`：可显式指定 OpenWind `Player(...)` 预设，例如 `UNITARY_FLOW`、`FLUTE`、`SOPRANO_RECORDER`
  - `source_location`：传给 OpenWind `source_location`，默认通常为 `entrance`

## 计划输出

后续将生成三类 CSV：
- `impedance.csv`
- `features.csv`
- `analysis.csv`

当前状态：
- `impedance.csv` 已实现
- `impedance.csv` 当前除复阻抗与派生响应列外，还包含语义元数据：
  - `player_preset`
  - `is_flute_like`
  - `default_response_mode`
  - `primary_feature_family`
- `impedances/<case_id>.csv` 已实现，当前格式为三列：
  - `frequency_hz`
  - `abs_y`
  - `angle_y_rad`
  文件使用空格分隔，并允许科学计数法，风格接近 OpenWind 原始导出
- `features.csv` 已实现，当前默认输出每个 case 主特征族的前 `3` 个峰：
  - 非 flute-like case：默认提取 `z_resonance`
  - flute-like case：默认提取 `y_resonance`
  - 当前每行至少包含：
    - `kind`
    - `index`
    - `frequency_hz`
    - `q_factor`
    - `amplitude`
- `analysis.csv` 已实现，当前每个 case / note 一行，默认汇总前 `3` 个主峰：
  - `feature_family`
  - `f1` / `f2` / `f3`
  - `pitch1` / `pitch2` / `pitch3`
  - `pitch1_cents` / `pitch2_cents` / `pitch3_cents`
  - `h2` / `h3`
  - `delta2_cents` / `delta3_cents`
    这里的 `deltaN_cents` 表示“第 N 个峰相对 `f1` 的最近整数倍”的音分偏差，不是固定相对 `N*f1`
  - `q1` / `q2` / `q3`
  - `a1` / `a2` / `a3`

## 响应语义

当前项目已经显式引入一层共享的响应语义派生逻辑，位于 `src/owbatch/response.py`。

输入真源仍然是复阻抗采样：
- `frequency_hz`
- `re_z`
- `im_z`

在当前研究阶段统一取 `Zc0 = 1`，因此语义约定为：
- 阻抗模式：
  - 上图/主模值：`|Z|`
  - 下图/相位：`angle(Z)`
- 导纳模式：
  - 上图/主模值：`|Y| = |1 / Z|`
  - 下图/相位：`angle(Y) = angle(1 / Z)`

这层逻辑会被：
- `runner.py` 复用，用于构建 `impedance.csv`
- `visulization/plot_impedance.py` 复用，用于画 OpenWind 语义一致的响应图
- 未来的 `extractors.py` / `analysis.csv` 复用，用于 resonance / antiresonance、Q-factor、f1/f2/f3 等

当前也约定了一个面向后续特征提取的默认语义：
- 非 flute-like player：默认主特征族为 `z_resonance`
- flute-like player，例如 `FLUTE` / `SOPRANO_RECORDER`：默认主特征族为 `y_resonance`

## 可视化

仓库当前包含一个简单绘图工具，可对 `out/impedance.csv` 按 `case_id` 画响应双图：

```bash
owbatch-plot-impedance --input ./out/impedance.csv --output ./out/impedance_response.png
```

默认 `--mode auto`：
- flute-like case，例如 `FLUTE` / `SOPRANO_RECORDER`：自动按导纳语义绘制
- 非 flute-like case：自动按阻抗语义绘制
- 若同一张图里混入两种默认语义，`auto` 会报错并要求显式指定 `--mode`

显式按阻抗语义绘制双图：

```bash
owbatch-plot-impedance \
  --input ./out/impedance.csv \
  --mode impedance \
  --output ./out/impedance_response.png
```

若要按导纳语义对齐 OpenWind demo 的 admittance 视图，可使用：

```bash
owbatch-plot-impedance \
  --input ./out/impedance.csv \
  --mode admittance \
  --angle-unit deg \
  --output ./out/admittance_response.png
```

此时绘制：
- 上图：`|Y|`
- 下图：`angle(Y)`

也可以把 `analysis.csv` 画成每个 case 一条横坐标、每个倍频偏差一条折线：

```bash
owbatch-plot-analysis \
  --input ./out/analysis.csv \
  --output ./out/analysis_deviation.png
```

当前行为：
- 横轴：`case_id`
- 纵轴：偏差音分 `deltaN_cents`
- 若分析表只有 `f1/f2/f3`，则自动画 `delta2_cents`、`delta3_cents`
- 若分析表有 `f4`，则会继续自动画 `delta4_cents`

如果你需要在窗口里用鼠标查看某个点的精确值，可以用交互式查看工具：

```bash
owbatch-view-analysis \
  --input ./out/analysis.csv
```

当前行为：
- 打开 Matplotlib 交互窗口，不保存图片
- 鼠标悬停到点上时，会显示 `case`、`note`、`deltaN_cents`、对应的 `fN`、`hN` 和最近整数倍

如果你希望把目录选择、重算和四张研究图整合到一个桌面工具里，可以使用 dashboard：

```bash
owbatch-dashboard
```

或启动时直接预载一个源数据目录：

```bash
owbatch-dashboard --directory ./examples/real_data
```

这个目录应包含：
- `template/`
- `cases.csv`

当前 dashboard 包含：
- 目录选择控件和当前路径显示
- `刷新` 按钮
- `保存图表` 按钮；当前四张图正常显示时，可将当前布局整体保存为一张 PNG 到所选源数据目录下，文件名为时间戳
- 左侧 `case_id` 选择列表；只有选中的 case 会被绘制
- 左侧 `全选` 按钮；若当前未全选则一键全选，若当前已全选则一键全不选
- 四张嵌入式图表：
  - Admittance modulus
  - Admittance angle
  - Pitch frequency
  - Harmonic deviation

状态逻辑：
- 未选择目录时，图表区显示 `请选择包含源数据的目录`
- 目录结构不满足要求时，图表区显示 `源数据不满足要求`
- 选择有效目录后会自动开始计算，无需再点一次刷新
- 计算过程中，状态栏会实时显示 `正在计算…… m/n 条 case`
- 任意 case 选择状态变化都会立即重绘四张图

其中右上角的 `Pitch frequency` 图：
- 横轴：`case`
- 纵轴：峰值频率 `fN`
- 线条数量取决于 `analysis.csv` 中有值的 `fN` 列数量
- 悬停标签会显示 `pitch`、`pitch_cents`、`q`

## 目录职责

代码目录：

- `src/owbatch/cli.py`
  命令行入口，负责参数解析与命令分发。
- `src/owbatch/models.py`
  输入输出 schema 草案，放数据模型与请求对象。
- `src/owbatch/config.py`
  放模板文件名、保留列、输出文件名等常量。
- `src/owbatch/template_loader.py`
  下一阶段负责读取模板 CSV 并形成内存对象。
- `src/owbatch/case_expander.py`
  下一阶段负责把 `cases.csv` 覆盖展开为完整几何与求解请求。
- `src/owbatch/response.py`
统一的响应语义层，负责从 `re_z` / `im_z` 派生 `|Z|`、`angle(Z)`、`|Y|`、`angle(Y)`，供可视化和后续特征提取复用。
- `src/owbatch/runner.py`
  下一阶段负责组织批处理执行、调用 OpenWind、串联导出。
- `src/owbatch/extractors.py`
  当前负责从频域曲线提取主特征族峰值、频率与 Q-factor。
- `src/owbatch/analysis.py`
  当前负责把峰值表汇总成每个 case / note 一行的分析表，包括音高、音分偏差、倍频偏差和 Q-factor。
- `src/owbatch/writers.py`
  下一阶段负责把结果写回 CSV。

测试目录：

- `tests/test_smoke.py`
  最小冒烟测试，确保 CLI 可导入、可显示帮助、可接受基础参数。
- `tests/fixtures/`
  后续放模板和 case 的最小样例数据。

## 下一步

下一阶段将实现：
1. 扩展到更多特征族，例如 `z_antiresonance` / `y_antiresonance`
2. 将峰值数量暴露为 CLI 参数
3. 更完整的输入校验与错误提示
