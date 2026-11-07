<!-- translation-of: CONTRIBUTING.md -->

# 贡献指南

[English](CONTRIBUTING.md) · 简体中文

## 开始之前

- 读 `AGENTS.md`。
- 读 `docs/specs/git-conventions.md` §2–§4。
- AI 参与过这次改动，读 `CONTRIBUTING.ai.md`。
- 一个改动 = 一个批次 = 一个 PR。

## 流程

```text
分支 -> 提交 -> PR -> 评审 -> 合并
```

- 不要直接推 `main`。
- 分支保持短生命周期。
- 填写 PR 模板，不留占位符。
- 合并前必需检查必须通过。

## PR 的范围

- 一个 PR 就是一个批次：一个变了的行为，以及它是怎么被验证的。不是一天的工作，也不是一个提交。
- 归入当前 PR：措辞、错字、注释、模板同步、把文档挪到它该在的位置——同一个主题，在描述里的 `Also changed` 下列出。
- 另开 PR：跨主题的改动（工具 / 文档 / 包内容），以及任何改门禁、改策略、改验收判据的东西。
- 检验：标题里需要出现「和」字，就拆。
- 上限：diff 超过约 400 行，或碰了三个不相关的区域，说明批次切大了——拆批次，不只是拆 PR。

## 评审

- 作者不能自审。作者是 AI 时，由人签字。
- 评审 diff、测试和证据。
- 豁免要记录，不能只口头同意。

## 合并

- 用 `gh pr merge --squash` 合并，不要直接推 `main`。
- 多笔提交的 squash 合并要传 `--subject` 与 `--body-file`；正文由 `pr_merge.py` 生成，不要手打。规则与已经留在历史里的两种错法见 `docs/specs/git-conventions.md` §4。
- 合并之后跑 `pr_merge.py --verify-only`；它读什么、为什么别的检查覆盖不到，也见 §4。
