<!-- translation-of: STD.md -->
# 软件测试设计

[English](STD.md) · 中文

一个用例一行。表格是给机器读的部分——`check_verification.py` 读它，覆盖只从
第二列统计。表格之后的小节说人怎么重跑。

## 用例

| 用例 | 覆盖 | 判据 |
| --- | --- | --- |
| `TC-IDN-001` | REQ-001, REQ-014 | `packs/sanguo/manifest.json` 里 `id: sanguo`、`kind: bundle`、`entry: n1`、`protocol: turn_based@1`、`saveSchema: 1` |
| `TC-RUN-001` | REQ-002 | `data/phases.json` 声明 24 回合，第 1 回合状态行显示 24 |
| `TC-RUN-002` | REQ-003 | 五个段位边界在第 1、6、11、16、21 回合 |
| `TC-RUN-003` | REQ-005 | `data/rules.json` 在粮草、兵员或声望归零时结束，金帛归零不结束 |
| `TC-RES-001` | REQ-004 | `data/state.json` 初值 40 / 30 / 12 / 1，上下界 0–100、0–100、0–60、0–4 |
| `TC-RES-002` | REQ-006 | `data/actions.json` 五个行动，各有代价与效果，代价先于效果结算 |
| `TC-RES-003` | REQ-007 | `data/rules.json` 三条声望规则：第 12 回合起每回合 +1 粮；声望 ≥2 时 cao→shao −5；声望 ≥3 时 liu→cao +5 |
| `TC-RES-004` | REQ-008 | `data/factions.json` 初值 shao→cao −20、cao→shao −20、liu→cao 30，盟友 60、敌对 −60 |
| `TC-NAR-001` | REQ-009 | `data/nodes.json` 从 `n1` 开始，第 1 回合显示该节点文字与选项 |
| `TC-NAR-002` | REQ-010 | 清单的 `content` 块声明视角、密度、登场与弧光 |
| `TC-NAR-003` | REQ-011 | 清单的 `meta` 有中英 pitch、`audience: adults`、`minutes: 30` |
| `TC-NAR-004` | REQ-012 | 清单的 `collection` 是 `three-kingdoms`，货架把它列在该世界下 |
| `TC-NAR-005` | REQ-013 | 玩家能看到的中文都有 `data/i18n/en.json` 的英文键，语言检查无缺失 |
| `TC-PKG-001` | REQ-015 | 清单声明两个素材，槽位 `scene` 与 `audio`，两个文件都在归档里 |
| `TC-PKG-002` | REQ-016 | `check_pack.py` 接受该归档：无代码，根上只有清单，目录只有 `data/`、`assets/`、`i18n/` |
| `TC-PKG-003` | REQ-017 | `capabilities` 里每个 id 都是引擎已提供的 |
| `TC-PKG-004` | REQ-018 | 声明的 `engine` 区间包含安装用例所用的引擎 |
| `TC-PKG-005` | REQ-019 | 同一棵树构建两次字节相同——sha256 与描述符里的字节数一致 |
| `TC-INS-001` | REQ-001, REQ-017, REQ-018 | 人把 `sanguo.zip` 装进引擎，包出现在「三国」下 |
| `TC-PLY-001` | REQ-002, REQ-003, REQ-005 | 人玩九回合：第 6 回合段位推进，无资源归零，未提前结束 |
| `TC-LAY-001` | REQ-016 | 内容层归档通过 `check_pack.py`，声明 `kind: layer`、`layer: content`、`target: sanguo` |
| `TC-LAY-002` | REQ-016 | mod 层归档通过 `check_pack.py`，声明 `kind: layer`、`layer: mod`、`target: sanguo`，未勾选时不改变任何东西 |
| `TC-REL-001` | REQ-019 | 发布资产重新下载后 sha256 与字节数等于描述符 |

## 每个用例怎么重跑

机械用例都从仓库根、在批次的基提交上跑这三条：

```text
python infra/tool/release/pack.py build packs/<id> --out dist
python infra/checks/check_pack.py dist/<id>.zip
python infra/tool/release/pack.py hash dist/<id>.zip
```

- **身份、进程、资源、叙事**：读判据点名的 JSON，比字段。断言的是数据，不涉及引擎。
- **封套**：`check_pack.py` 打印 `the envelope holds`，或点名是哪个条目破了规则。
- **可复现**：构建到两个输出目录，比两个 `sha256`；工具写入固定时间戳并按序排条目，任何差异都是真差异。
- **安装与试玩**：人从发布页下载资产，用引擎自己的界面安装，发截图。两张截图结案：装好后的包列表，以及数字确实变过的一回合。
- **层用例**：先对层自己的归档做同一次封套检查，然后勾选与不勾选各玩一次。
- **发布**：从发布页下载资产，与发布里描述符的 sha256 比对。

## 证据

命令用例把输出留在 `.batch/<id>/evidence/<name>.log`；人工用例把截图放在出口
记录旁边。出口记录引用它跑过的用例 id；没有跑就写 `none` 并说明原因。
