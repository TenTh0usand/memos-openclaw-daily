你现在在 `E:\workspace\github\memos-openclaw-daily` 这个工作区执行每日总结任务。

严格按下面顺序执行：

1. 运行：

```powershell
python -m memos_daily_report prepare
```

2. 读取 `runs/latest_status.json`。

3. 根据 `status` 分流：

- 如果是 `waiting_retry`：
  - 说明今天还没有可总结的 memo。
  - 如果 `reminder_error` 非空，在最终回复里顺带说清楚提醒发送失败的原因。
  - 执行：

```powershell
Start-Sleep -Seconds 2700
```

  - 然后再次执行：

```powershell
python -m memos_daily_report prepare
```

  - 再读取一次 `runs/latest_status.json`。
  - 如果第二次仍然是 `waiting_retry`，立即停止，不要写回 Memos，最终只回复“今天还没有 Memos 记录，已发送提醒并完成一次自动重试”。

- 如果是 `ready` 或 `forced_ready`：
  - 继续下面步骤。

4. 读取 `context_path` 指向的 `daily_context.md`。

5. 如果 `daily_context.md` 里列出了图片绝对路径，逐个查看这些图片，把视觉信息纳入总结。

6. 生成一份中文 Markdown 日报，要求：

- 标题格式：`# YYYY-MM-DD 日报`
- 总长度控制在 300-700 字
- 必须包含以下小节：
  - `## 今日概览`
  - `## 时间线`
  - `## 吃了什么 / 生活片段`
  - `## 工作 / 学习 / 部署`
  - `## 想法与情绪`
  - `## 明日建议`
- 不要编造没有出现在 memo 或图片里的细节
- 如果某一块信息不足，明确写“今天这部分记录较少”
- 末尾追加标签：`#daily-report #ai-summary`

7. 把日报保存到 `run_dir` 下的 `report.md`。

8. 然后执行：

```powershell
python -m memos_daily_report publish --content-file <run_dir>\report.md
```

9. 最终回复只保留两部分：

- 这次日报的 2-3 句简短摘要
- 写回成功后的 memo name
