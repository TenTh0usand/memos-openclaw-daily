# 在 NAS 上接入 OpenClaw + Telegram

这份项目当前是“脚本 + Prompt”，不是已经安装进 OpenClaw 的 skill。

也就是说：

- 现在这套逻辑还没有自动存在于你 NAS 上那台 OpenClaw 里；
- 我刚才做的测试是在本地电脑目录里直接运行 Python 脚本；
- 如果要让 NAS 上的 OpenClaw 真正接管，就需要把这个项目放到 NAS，并让 OpenClaw cron 指向它。

## 先说结论

最稳的上线方式是：

1. 把整个 `memos-openclaw-daily` 目录复制到 NAS
2. 确保 OpenClaw 的 Linux / Docker 环境里已经有 `python3` 和 `python3-venv`
3. 把 `.env` 配成 NAS 内网能访问 Memos 的地址
4. 用包装脚本自动创建 Linux 虚拟环境并安装 Python 包
5. 先手动测试 `prepare`
6. 确认 OpenClaw 的 Telegram channel 已配对
7. 用 `openclaw cron add --announce --channel telegram --to ...` 建每日任务

## 这是 skill 还是脚本？

当前是脚本，不是 skill。

更准确地说：

- `src/memos_daily_report/*.py` 是真正干活的执行逻辑
- `openclaw/DAILY_REPORT_PROMPT.md` 是给 OpenClaw 的执行说明

为什么我建议先保持“脚本 + prompt”：

- 读取 Memos API、下载图片、写回 memo，这些更适合脚本做
- OpenClaw 负责看图、总结、定时和 Telegram 投递
- skill 更像“操作说明书”，不适合承载稳定的数据处理流水线

后面当然也可以再包装成 OpenClaw skill，但那是锦上添花，不是必须。

## Memos 地址怎么填

如果 `Memos` 和 `OpenClaw` 在 NAS 同一台机器上，优先顺序通常是：

1. `http://127.0.0.1:5230`
2. `http://<docker-service-name>:5230`
3. `http://<nas-lan-ip>:5230`

推荐：

- 如果 OpenClaw 和 Memos 都是宿主机进程，优先 `127.0.0.1`
- 如果它们都在同一个 Docker 网络里，优先服务名，比如 `http://memos:5230`
- 局域网地址也能用，但通常不如 loopback 或容器内服务名直接

## 在 NAS 上部署

下面以 Linux / NAS shell 为例。

### 1. 复制项目到 NAS

你可以放到任意目录，例如：

```bash
mkdir -p /volume1/dev
cd /volume1/dev
```

然后把当前项目目录复制过去。

### 2. 准备 Python 运行时

如果你是 Docker 部署的 OpenClaw，先确认容器里有：

- `python3`
- `python3-venv`

没有的话，不建议在运行中的容器里临时乱装。更稳的是直接扩展镜像。

仓库里给了一个最小示例：

- [`../docker/openclaw-python/Dockerfile.example`](../docker/openclaw-python/Dockerfile.example)
- [`../docker/openclaw-python/compose.snippet.yml`](../docker/openclaw-python/compose.snippet.yml)

### 3. 安装项目依赖

```bash
cd /volume1/dev/memos-openclaw-daily
cp .env.example .env
bash ./scripts/run_memos_daily.sh prepare --no-send-empty-reminder
```

第一次运行时，脚本会自动：

- 创建 `.venv-linux/`
- 安装 `pip` 依赖
- 执行 `memos_daily_report prepare`

### 4. 配 `.env`

最少要改这些：

```env
MEMOS_BASE_URL=http://127.0.0.1:5230
MEMOS_TOKEN=你的 PAT
MEMOS_TIMEZONE=Asia/Shanghai

SMTP_HOST=smtp-relay.example.com
SMTP_PORT=2525
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_SSL=false
SMTP_USE_STARTTLS=false
SMTP_FROM=memos-bot@example.local
SMTP_TO=telegram@example.local
```

如果你的 OpenClaw 在 Docker 容器里，而 Memos 不在同一个网络，`127.0.0.1` 可能会指向容器自己而不是 NAS 宿主机。这时改成：

- `http://memos:5230`，如果同网络有服务名
- 或 NAS 宿主机地址，例如 `http://<nas-lan-ip>:5230`

### 5. 手动测试脚本

```bash
bash ./scripts/run_memos_daily.sh prepare
bash ./scripts/run_memos_daily.sh collect
```

如果 `runs/latest_status.json` 里是 `ready`，说明 Memos 读取没问题。

### 6. 测试 OpenClaw Telegram 通道

先确认 OpenClaw 的 Telegram 已配对。

文档里明确支持：

- `openclaw message send --channel telegram --target 123456789 --message "hi"`

你可以先在 NAS 上跑一条最简单的测试消息。

### 7. 添加每日任务

```bash
cd /volume1/dev/memos-openclaw-daily
openclaw cron add \
  --name "Memos Daily Report" \
  --cron "30 22 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --announce \
  --channel telegram \
  --to "<你的 Telegram chat id 或 -100...:topic:...>" \
  --message "$(cat /volume1/dev/memos-openclaw-daily/openclaw/DAILY_REPORT_PROMPT.md)"
```

重点：

- 不能写 `--no-deliver`
- 要显式写 `--announce --channel telegram --to ...`

## 为什么你刚才没收到 Telegram

有两个原因：

1. 我刚才真正执行的是你本地电脑里的脚本，不是 NAS 上的 OpenClaw
2. README 之前的旧命令用了 `--no-deliver`，即使 OpenClaw 跑了，也不会发 Telegram

## 现在真正的状态

现在这套东西的状态是：

- 代码已经能读 Memos、下图片、出日报、写回 Memos
- 也已经验证过 SMTP 提醒链路
- 但 NAS 上的 OpenClaw 还没有“安装这套能力”

准确说，它还没有“掌握这个技巧”，因为脚本还没部署到 NAS 上的 OpenClaw 工作目录，也还没创建实际 cron 任务。

另外，如果容器里没有 `python3`，单纯“复制源码目录”也不够；源码可以直接拷，但运行时还是要有 Linux 侧 Python。

## 你下一步最省事的做法

推荐你这样做：

1. 把这个目录原样复制到 NAS
2. 在 NAS 上把 `.env` 改成 `MEMOS_BASE_URL=http://127.0.0.1:5230`
3. 先执行一次 `bash ./scripts/run_memos_daily.sh prepare`
4. 再执行一次 `openclaw message send --channel telegram --target ... --message "test"`
5. 最后再加 cron

这样排错最简单。
