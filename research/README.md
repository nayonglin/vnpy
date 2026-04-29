# 并行研究记录规范

本目录用于替代“所有研究都追加到根目录 `memory.md` / `back_log.md`”的单流水账模式。

## 核心原则

1. 根目录 `memory.md` 和 `back_log.md` 作为历史总账与重要合入摘要保留，不再作为多条研究线的日常写入目标。
2. 每条研究线拥有独立目录：`research/lines/<line_id>/`。
3. 日常研究只写本线目录，避免不同 worktree / agent 同时修改同一个大文件。
4. 每次阶段性研究写一个独立 stage 文件，而不是追加同一个长文件。
5. 合入时由协调者读取各线 stage 文件，更新 `research/registry.md`，必要时再把重要里程碑摘要追加到根目录总账。

## 推荐目录结构

```text
research/
  README.md
  registry.md
  merge_log.md
  templates/
    stage_record.md
  lines/
    <line_id>/
      LINE.md
      stages/
        20260429_1731_stage321_slow_rhythm_stability.md
```

## 写入规则

- 新阶段必须写入：`research/lines/<line_id>/stages/<timestamp>_stage<stage>_<slug>.md`
- 同一条线如果只有一个工作区在推进，可以同步更新该线的 `LINE.md`。
- 如果同一条线也被多个工作区并行推进，只写唯一 stage 文件，暂不改 `LINE.md`，由合入者统一整理。
- 不同研究线不得修改彼此目录。
- 只有合入/复盘时才更新 `research/registry.md` 和根目录总账。

## stage 文件命名

```text
YYYYMMDD_HHMM_stageNNN_short_slug.md
```

示例：

```text
20260429_1731_stage321_slow_rhythm_stability.md
```

## 合入流程

1. 确认每条线的 stage 文件都包含参数、结果、过拟合反思、继续价值判断。
2. 把同一研究线的 stage 文件整理到该线 `LINE.md`。
3. 更新 `research/registry.md` 的状态、最新阶段、下一步。
4. 只有重要突破、正式候选、路线废弃、跨线合并这四类事件，才追加根目录 `memory.md` / `back_log.md`。

## 当前活跃研究线

详见 `research/registry.md`。
