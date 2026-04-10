# Memos + Python + OpenClaw 日报方案

这个目录给你一套最小可用骨架：

- `Memos` 继续负责手机端快速记录文字、图片、随想；
- `Python` 负责调用 Memos API，按天收集 memo 和附件，整理成 OpenClaw 好消费的上下文包；
- `OpenClaw` 负责每天定时执行、看图、总结，并可把日报再写回 Memos；
- `SMTP` 负责在“今天还没有任何 memo”时提醒你去记录。

我刻意没有把“总结”硬编码进 Python，因为你的目标就是让 OpenClaw 来做每日回顾。这样职责更清楚，也更方便你以后切模型、改提示词、加周报。

## 目录结构

```text
memos-openclaw-daily/
├─ .env.example
├─ pyproject.toml
├─ README.md
├─ openclaw/
│  └─ DAILY_REPORT_PROMPT.md
└─ src/
   └─ memos_daily_report/
      ├─ __init__.py
      ├─ __main__.py
      ├─ cli.py
      ├─ config.py
      ├─ memos_client.py
      ├─ notifications.py
      ├─ workflow.py
      └─ models.py
```

## 这套方案怎么跑

### 1. 安装

```powershell
cd E:\workspace\github\memos-openclaw-daily
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
```

然后把 `.env` 里这些值填好：

- `MEMOS_BASE_URL`: 你的 Memos 地址，比如 `https://memo.example.com`
- `MEMOS_TOKEN`: Memos 设置页里创建的 Access Token
- `MEMOS_TIMEZONE`: 你的日报时区，默认 `Asia/Shanghai`
- `SMTP_TO`: 你的 `smtp-telegram` 收件地址
- `SMTP_HOST` / `SMTP_PORT`: 你的 SMTP 网关参数

`.env.example` 里放的是占位示例：

- `SMTP_HOST=smtp-relay.example.com`
- `SMTP_PORT=2525`
- `SMTP_USERNAME=` 留空
- `SMTP_PASSWORD=` 留空
- `SMTP_USE_SSL=false`
- `SMTP_USE_STARTTLS=false`

### 2. 先测试“收集当天内容”

```powershell
python -m memos_daily_report collect
```

成功后会生成：

```text
runs/
├─ latest.txt
├─ latest_status.json
└─ 2026-04-10/
   ├─ daily_context.md
   ├─ memos.json
   ├─ workflow_state.json
   └─ media/
```

其中：

- `daily_context.md` 是给 OpenClaw 看的主输入
- `memos.json` 是结构化原始数据
- `media/` 里是下载下来的图片附件
- `latest.txt` 里写的是本次运行目录的绝对路径
- `latest_status.json` 里写的是当前是否适合生成日报

### 3. 测试“准备日报工作流”

```powershell
python -m memos_daily_report prepare
```

这个命令会：

1. 收集当天 memo 和图片
2. 如果今天已有内容，则标记为 `ready`
3. 如果今天还没有内容，则尝试发一条 SMTP 提醒，并标记为 `waiting_retry`
4. 同一天默认只提醒一次，避免重复打扰

你会看到三种典型状态：

- `ready`: 今天已有 memo，可以继续生成日报
- `waiting_retry`: 今天还没记录，已经提醒或等待重试
- `forced_ready`: 今天没有 memo，但你手动要求强制继续

### 4. 用 OpenClaw 生成日报

把 [`openclaw/DAILY_REPORT_PROMPT.md`](E:/workspace/github/memos-openclaw-daily/openclaw/DAILY_REPORT_PROMPT.md) 的内容作为 cron job 的 `--message`。

PowerShell 例子：

```powershell
openclaw cron add `
  --name "Memos Daily Report" `
  --cron "30 22 * * *" `
  --tz "Asia/Shanghai" `
  --session isolated `
  --announce `
  --channel telegram `
  --to "<你的 Telegram chat id 或 -100...:topic:...>" `
  --message (Get-Content .\openclaw\DAILY_REPORT_PROMPT.md -Raw)
```

这条 job 的思路是：

1. 运行 `python -m memos_daily_report prepare`
2. 如果今天没记录，则先发 SMTP 提醒
3. 等待 45 分钟后自动重试一次
4. 第二次还是空，就停止，不写回空日报
5. 如果有 memo，就读取 `daily_context.md` 和图片
6. 生成中文日报
7. 把日报保存成 `report.md`
8. 运行 `python -m memos_daily_report publish --content-file ...` 写回 Memos

注意：

- 如果你写的是 `--no-deliver`，OpenClaw 不会往 Telegram 发任何通知。
- 想发到 Telegram，必须用 `--announce --channel telegram --to "..."`。

## Python CLI

### `collect`

按天从 Memos 拉取 memo，下载附件，并输出 OpenClaw 上下文包。

```powershell
python -m memos_daily_report collect --date 2026-04-10
python -m memos_daily_report collect --time-field updated_ts
python -m memos_daily_report collect --no-download-attachments
```

参数：

- `--date YYYY-MM-DD`: 默认取 `MEMOS_TIMEZONE` 下的今天
- `--time-field`: `created_ts` 或 `updated_ts`，默认 `created_ts`
- `--output-root`: 输出目录，默认读 `MEMOS_OUTPUT_ROOT`
- `--download-attachments / --no-download-attachments`

### `prepare`

这是给 OpenClaw 用的工作流入口。

```powershell
python -m memos_daily_report prepare
python -m memos_daily_report prepare --force
python -m memos_daily_report prepare --no-send-empty-reminder
```

参数：

- `--force`: 即使 `memoCount` 为 0，也允许后续继续生成一次日报
- `--no-send-empty-reminder`: 今天没记录时不发 SMTP 提醒

生成物：

- `runs/latest_status.json`: OpenClaw 读取的最新状态
- `runs/<日期>/workflow_state.json`: 当天工作流状态，避免重复提醒

### `publish`

把已经生成好的 Markdown 日报写回 Memos。

```powershell
python -m memos_daily_report publish --content-file .\runs\2026-04-10\report.md
```

参数：

- `--content-file`: Markdown 文件路径
- `--content`: 直接传内容
- `--visibility`: `PRIVATE` / `PROTECTED` / `PUBLIC`
- `--tag`: 默认会追加 `.env` 里的 `MEMOS_REPORT_TAG`

### `send-reminder`

如果你想手动发一条提醒：

```powershell
python -m memos_daily_report send-reminder
python -m memos_daily_report send-reminder --subject "记一下今天干了什么" --body "随手发一句话或一张图就行。"
```

## 手动强制生成一次

如果今天没有 memo，但你就是想让 OpenClaw 强制生成一版，你可以先跑：

```powershell
python -m memos_daily_report prepare --force
```

然后再让 OpenClaw 执行日报 prompt。这样状态会变成 `forced_ready`，不会因为空记录直接中止。

## 推荐的日报格式

建议你让 OpenClaw 输出固定结构，后面周报/月报更容易复用：

```markdown
# 2026-04-10 日报

## 今日概览

## 时间线

## 吃了什么 / 生活片段

## 工作 / 学习 / 部署

## 想法与情绪

## 明日建议

#daily-report #ai-summary
```

## 为什么我建议“Python 拉取，OpenClaw 总结”

因为你真正需要的不是一个 “Memos CLI”，而是一条稳定流水线：

- Memos API 负责数据读取和回写
- Python 负责把碎片和图片整理成可消费上下文
- OpenClaw 负责多模态理解、归纳、定时执行
- SMTP 负责今天没写内容时的提醒

这样比直接赌一个社区 MCP server 更稳，尤其是你的重点是“图片也要进日报”，而不是简单 CRUD。

## 后续可以怎么升级

你把这版跑通后，下一步很自然：

- 加 `#food` / `#deploy` / `#thought` / `#todo` 标签，日报质量会明显更稳
- 改成 webhook 增量收集，而不是每天全量扫一次
- 在 OpenClaw 里继续做周报、月报、饮食回顾、部署周报
- 加 Telegram 投递，日报生成后直接推送给你
- 把自动重试等待时长改成你习惯的 20 分钟或 60 分钟

## 排错

### `collect` 能跑通，但 `memoCount` 一直是 0

这通常说明这几个情况之一：

- 这枚 token 对应的账号最近确实没有 memo
- 你网页登录 Memos 用的账号，和生成 token 的账号不是同一个
- 你平时看的内容是别的用户发布的公开 memo，而不是当前 token 所属用户的数据

这时候最简单的验证方式是：

1. 先在 Memos 里手动新建一条测试 memo
2. 再执行一次 `python -m memos_daily_report collect`
3. 看 `runs/<日期>/memos.json` 里的 `memoCount` 是否变成 1

### SMTP 发不出去

这套代码支持你给的“无认证、无 SSL、无 STARTTLS”模式，但还需要一个真正的收件地址：

- `SMTP_TO`: 你的 `smtp-telegram` 地址
- `SMTP_FROM`: 发件人地址，通常给一个本地域名地址即可，比如 `memos-bot@localhost`

如果 `prepare` 结果里的 `reminder_error` 不为空，OpenClaw 会把失败原因带出来，方便继续排。

## 参考

- https://usememos.com/docs/api
- https://usememos.com/docs/api/memoservice/ListMemos
- https://usememos.com/docs/usage/shortcuts
- https://usememos.com/docs/integrations/webhooks
- https://docs.openclaw.ai/cli/cron
- https://docs.openclaw.ai/automation/tasks
