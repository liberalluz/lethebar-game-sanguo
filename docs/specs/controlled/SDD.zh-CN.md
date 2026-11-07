<!-- translation-of: SDD.md -->

# 软件设计说明书 — `sanguo`

这个包是怎么拼起来的，以及每一块为什么在那个位置。需求按 SRS 的 ID 引用；本文件不重述需求。

## 1. 形态

一次发布是一个 zip：

```text
sanguo.zip
├── manifest.json
├── data/
│   ├── nodes.json
│   ├── actions.json
│   ├── state.json
│   ├── rules.json
│   ├── phases.json
│   ├── factions.json
│   └── i18n/en.json
└── assets/
    ├── scene.png
    └── theme.wav
```

引擎把包安置到 `app/builtin/<id>.zip`，从那里读取。运行时不需要 zip 之外的任何东西：没有字体、没有共享文件、没有脚本。

## 2. manifest

`manifest.json` 就是接口。本包设置的字段，以及每个字段为什么存在：

| 字段 | 值 | 为什么 |
|---|---|---|
| `id` | `sanguo` | 存档键是 `save:<id>:<slot>`；改名会让存档变孤儿（REQ-001） |
| `version` | `1.0.0` | 包自己的版本，与引擎版本无关 |
| `specVersion` | `2.0.0` | 本文件所遵循的 manifest 格式版本 |
| `kind` | `bundle` | 整个世界在一个包里，不分散到多个层 |
| `requires` | `[]` | 不需要先装别的包 |
| `engine` | `>=4.7.0 <5.0.0` | 内容所面向的引擎范围（REQ-018） |
| `name` / `names` | `三国` / `Three Kingdoms` | 按语言给展示名；`id` 永不改 |
| `defaultLocale` / `locales` | `zh-CN` / `["en"]` | 中文是源，英文是覆盖层（REQ-013） |
| `protocol` | `turn_based@1` | 一回合做一件事 |
| `capabilities` | 七项 | 引擎必须提供什么（REQ-017） |
| `mechanics` | 五项 | 菜单列出的子集 |
| `entry` | `n1` | 新局打开的节点（REQ-009） |
| `saveSchema` | `1` | 存档载荷的形状（REQ-014） |
| `assets` | 两条 | 路径加槽位，引擎据此绑定而不用猜（REQ-015） |
| `clock` | `{"per": "turn"}` | 世界按回合计时，不按秒 |
| `collection` | `three-kingdoms` | 菜单先分世界，再分包（REQ-012） |
| `content` | 视角、密度、登场、弧光 | 叙事面是声明出来的，不是推断的（REQ-010） |
| `meta` | 受众、时长、一句话 | 商店页与菜单条目所需（REQ-011） |

`kind` 取 `bundle` 而非 `layer`，因为本包拥有一个完整世界：它自带状态、阶段与入口。层要做的相反——说明它改的是哪个包的什么，这也是后续卡牌包将采取的形式。

## 3. 数据文件

| 文件 | 内容 | 被读来做什么 |
|---|---|---|
| `nodes.json` | 开场节点 `n1`：文本、素材、空的选项 | 一局的第一屏 |
| `actions.json` | 五个行动：id、名称、提示、代价、效果 | 一回合能花在什么上 |
| `state.json` | 四项资源：`init`、`min`、`max`，可选 `labels` | 资源栏与其上下限 |
| `rules.json` | 三条由声望驱动的规则，带 `set` 与 `relations` | 玩家不操作时仍在变的东西 |
| `phases.json` | `turns`、`ranks`、`fail` | 局的长短、段位表、结局 |
| `factions.json` | 三个实体及其关系，加上 `ally` / `hostile` 阈值 | 三方如何互相看待 |
| `i18n/en.json` | 按节点 id 的文本覆盖，加一层扁平的 `strings` 映射 | 每一句英文（REQ-013） |

按「谁来读」拆分，不按主题拆：引擎先要回合数，再要节点文本；而译者只需要那层扁平的 `strings`。

## 4. 作为数据的回合

包不实现回合循环，只声明一回合可以包含什么。

1. 一局从 `n1` 打开，四项资源取各自的 `init` 值。
2. 玩家选一个行动；先扣 `costs`，再生 `effects`。
3. `rules.json` 里的规则对着新状态求值。
4. 时钟推进；从第 12 回合起，粮草规则每回合加 1。
5. `phases.json` 决定段位是否变化、是否触到失败条件。

顺序值得写下来，因为两个文件会互相影响：一个耗粮的行动可以把粮草压到 0，而失败判定读的是行动之后的值，不是之前。

## 5. 本地化

中文是数据文件里的源文本，英文是 `data/i18n/en.json` 里的覆盖层：

- 节点文本按节点 id 建键（`n1`）；
- 界面字符串是扁平键：`action.<id>`、`rank.<turn>`、`resource.standing.<value>`、`failure.<index>`。

缺失的键回落为中文源文，而不是空串，所以译了一半的包在缺口处读起来是中文，不会露出空洞。这也是为什么 REQ-013 只要求覆盖、不要求机制：机制本来就容得下缺口。

## 6. 素材

两个文件，都在 manifest 里声明，引擎按槽位绑定：

| 路径 | 类型 | 槽位 | 用途 |
|---|---|---|---|
| `assets/scene.png` | texture | `scene` | 入口画面的背景 |
| `assets/theme.wav` | audio | `audio` | 与画面一同播放的主题曲 |

场景在 `nodes.json` 里也列了一次，因为入口节点要说明它显示哪些素材。manifest 里的那条让它们成为包的一部分，节点里的那条让它们在这一刻可见。

## 7. 构建与发布

- `infra/tool/release/pack.py build packs/sanguo` 会排序条目、钉住时间戳、把 `manifest.json` 放在最前，所以两次构建字节相同（REQ-019）。
- `pack.py hash` 写出 `sanguo-1.0.0.json`，含 `id`、`version`、`bytes`、`sha256`、`specVersion`、`engine`。
- 标签是 `pack/sanguo/v1.0.0`；发布带 zip 与描述符。发布之后不再移动标签。

## 8. 已知限制

这些是 1.0.0 的真实状态，记在这里而不是悄悄修掉：

- `factions.json` 里的势力名与 `content.arc` 里的弧光段名只有中文，未被 `data/i18n/en.json` 覆盖。SRS 把它们声明为叙事面（REQ-010），但尚未要求英文对应。
- `meta.minutes` 已声明，但菜单还不读它。
- `meta.audience` 由引擎校验，但没有任何地方据此筛选。
- 不能在游戏运行中安装包；zip 由安置 `app/builtin/` 的工具放置。

## 9. 为什么不

- **不做层。** 后续计划的卡牌包是层，因为它改的是一个已经存在的世界；本包本身就是那个世界。
- **不含代码。** 需要代码的地方就是引擎改动；包保持为数据（REQ-016）。
- **不带字体。** 引擎提供字体；把字体塞进包既增大体积，又白白背上许可义务。
- **不写第二份变更日志。** `changelog.d/` 的碎片在发布时被消费，另有 `CHANGELOG.md` 只会互相漂移。
