<!-- translation-of: README.md -->

# lethebar-game-sanguo

[English](README.md) · 简体中文

> Lethebar 的三国世界：它的故事、它的数值、它的画。
> 玩它的规则留在引擎里，这个仓只装「这个世界是什么」。

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Pack](https://img.shields.io/badge/pack-sanguo-c0392b.svg)](packs/sanguo/manifest.json)
[![Engine](https://img.shields.io/badge/engine-%3E%3D4.7.0%20%3C5.0.0-478cbf.svg)](https://github.com/liberalluz/lethebar)

## 包

<!-- pack-badges:begin -->
![packs](https://img.shields.io/badge/packs-3-6f42c1)
![spec](https://img.shields.io/badge/spec-2.0.0-007ec6)
![engine](https://img.shields.io/badge/engine-%3E%3D4.7.0%20%3C5.0.0-478cbf)

| Kind | Pack | Version | Spec | Engine |
| --- | --- | --- | --- | --- |
| `bundle` | `sanguo` | `1.1.0` | `2.0.0` | `>=4.7.0 <5.0.0` |
| `layer:content` | `sanguo-content` | `1.0.0` | `2.0.0` | `>=4.7.0 <5.0.0` |
| `layer:mod` | `sanguo-hard` | `1.1.0` | `2.0.0` | `>=4.7.0 <5.0.0` |
<!-- pack-badges:end -->

## 状态

**`pack/sanguo/v1.1.0` 已发布。** 一局 24 回合，从初平元年的起兵讲到五级段位的尽头；三个资源决定它会不会提前结束——粮草、士卒、声望，任意一项归零就结束。

已知限制，全部在引擎侧、本仓不修：势力名与弧光段名是写死的中文，不随界面语言变；包里声明的时长会被收下，但菜单还不显示；受众会被校验，但没有任何东西按它筛选；图和声被画进一条带子和一个立绘栏，且只收 PNG、JPEG、WAV。

## 它是什么

- **这是一个世界，不是引擎。** `data/` 说发生什么，`assets/` 说看起来什么样、听起来什么样，`manifest.json` 说这两样怎么打包。回合怎么推进、段位怎么算、失败怎么判，都是引擎 `app/core` 的事；哪个世界需要改这些，它要的是一次引擎改动，不是一次包改动。
- **一个包，一个 id。** `sanguo` 是包 id，永不改：存档键是 `save:sanguo:<slot>`，改名等于把每个玩家的旧档变成孤儿。
- **是 bundle，不是 layer。** 六层——数值、文本、美术、声、菜单条目、叙事声明——全装在这一个包里。以后那个包（`sanguo-cards`，v0.7.0，还没写）会作为 `layer` 叠在上面；为了那一天，这个包什么都不用挪。
- **数据可以直接 diff。** 每个文件都是普通 JSON 或一张素材。改数值就是一行 diff，评审时不用真跑游戏。

## 安装

发布带两个文件：`sanguo.zip` 与 `sanguo-1.1.0.json`。构建把 zip 摆进引擎的 `app/builtin/`，那是加载器唯一会读包的地方；描述文件是玩家拿来核对 zip 的。摆进去之前先核：

```bash
sha256sum sanguo.zip
```

描述文件在 `sha256` 里带着同一个值，两边互相核对。

游戏内装包不在这次发布的范围里。引擎自带它的包，这个包通过「摆盘」进入一次构建。

## 包里有什么

| 路径 | 内容 |
|---|---|
| `manifest.json` | `id`、`version`、`specVersion`、`engine`、`protocol`、`capabilities`、`entry`、`saveSchema`、`assets`、`meta`、`content` |
| `data/nodes.json` | 一个回合能打开的场景 |
| `data/actions.json` | 玩家能做什么，每个选择花什么 |
| `data/ledger.json` | 四个资源与它们的起始值 |
| `data/rules.json` | 一个选择被允许改什么 |
| `data/phases.json` | 24 回合，五级段位落在第 1 / 6 / 11 / 16 / 21 回合，三个失败条件 |
| `data/relations.json` | 撑起这一局的三家 |
| `data/i18n/en.json` | 每一条可见中文的英文覆盖层 |
| `assets/scene.png` | 场景带 |
| `assets/theme.wav` | 主题音 |

manifest 声明 `protocol: turn_based@1`——一回合做一件事——以及七个 capability（`render.2d@1`、`text@1`、`ledger@1`、`rules@1`、`phases@1`、`menu@1`、`relations@1`）。它不声明任何新能力；需要新能力的包，是在要求引擎先长出来。

## 世界

第三人称、密集、登场三人：魏的曹操、盟主袁绍、骁将吕布。弧光五段——初平元年 · 起兵 / 群雄并起 / 中原逐鹿 / 三分之势 / 天下归心——每跨过一段，正文下面那行字就变。势力名与段名是包内文本，中文，暂不随读者语言变。

## 命令

| 命令 | 做什么 |
|---|---|
| `python infra/tool/merge/pr_merge.py --self-test` | 断言合并工具执行的消息规则 |
| `python infra/checks/check_commit_body.py --ref origin/main` | 按规范 §2 判已合并提交的提交信息 |

目前没有 CI。

## 仓库结构

| 目录 | 职责 |
|---|---|
| `packs/` | 一个包一个目录，目录名必须等于它的 `id`：`packs/sanguo/` |
| `shared/` | 多个包会共用的东西；第二个包需要之前一直是空的 |
| `docs/` | 规格、决策、意图（[docs/README.md](docs/README.md)） |
| `infra/` | 本仓自己的工具，摆法与引擎仓一致：`checks/` 与 `tool/merge/` |

没有 `app/`：引擎的代码不在这里。

## 文档

| 想找 | 去哪 |
|---|---|
| 为什么有这个 | [docs/intent/](docs/intent/) |
| 应该是什么样 | [docs/specs/](docs/specs/) |
| 决定了什么、否掉了什么 | [docs/decisions/](docs/decisions/) |

文档放哪：应该怎样 → `specs/`；定了没定 → `decisions/`；为什么 → `intent/`；怎么操作 → `runbooks/`。

## 参与贡献

- 开 PR 之前读 [CONTRIBUTING.md](CONTRIBUTING.md)。
- AI 参与过内容改动？也读 [CONTRIBUTING.ai.md](CONTRIBUTING.ai.md)：AI 的改动要有人复核并带证据，作者不能自审。
- 数值改动用数字说话比用文字好：把某条目的改前改后贴进 issue。

## 安全

见 [SECURITY.md](SECURITY.md)。对引擎来说包是不可信输入，一次发布的可信度不超过它旁边那份哈希。

## 许可

这个世界以 [Apache License 2.0](LICENSE) 授权：允许商用与再分发，前提是保留版权声明与 [NOTICE](NOTICE)。玩它的引擎另行授权，在它自己的仓里。
