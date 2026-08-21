# GitHub Actions 部署

SparkFlow 现在只使用 `main`。业务执行只有一个工作流：`.github/workflows/schedule.yml`，手动 smoke、正式发送和定时任务全部走同一条链路。

## 1. Fork 并启用 Actions

1. Fork 仓库。
2. 打开 Fork 的 `Actions` 页面并启用 Workflows。
3. 确认默认分支为 `main`。

仓库自带 `Main Branch Policy`。它会删除非 `main` 分支，因此不要再创建 `api`、`dev` 或功能分支来承载不同运行能力。

## 2. 创建 `user-data` Environment

进入：

```text
Settings -> Environments -> New environment
```

创建：

```text
user-data
```

SparkFlow 工作流只从这个 Environment 读取运行配置。

## 3. Environment Variables

写入以下变量：

```text
PROXY_ADDRESS
MESSAGE_TEMPLATE
HITOKOTO_TYPES
MATCH_MODE
BROWSER_TIMEOUT
FRIEND_LIST_WAIT_TIME
TASK_RETRY_TIMES
LOG_LEVEL
TASKS
```

`TASKS` 示例：

```json
[
  {
    "username": "主账号",
    "unique_id": "123456789",
    "targets": ["好友A", "好友B"]
  }
]
```

运行开始后会先执行严格配置校验。无效 JSON、重复 `unique_id`、空目标列表、非法 `MATCH_MODE`、非正数超时/重试值都会在浏览器启动前直接失败。

## 4. Environment Secrets

每个账号需要：

```text
COOKIES_<UNIQUE_ID大写>
```

例如：

```text
COOKIES_123456789
```

Cookie 必须在已登录的 `https://www.douyin.com/chat` 页面导出。推荐使用 Cookie-Editor 的 JSON 数组格式。

不要把 Cookie 放进仓库文件、Issue、普通 Variables 或网页源码。

## 5. 先运行 smoke

打开 `Actions -> SparkFlow -> Run workflow`：

```text
Branch: main
mode: smoke
```

smoke 会验证：

- 配置和 Cookie JSON。
- Playwright 浏览器运行时。
- 抖音 Web Chat 登录态。
- 聊天页面结构。
- 至少一个目标好友的匹配。

它不会发送消息。

## 6. 正式发送

再次运行：

```text
Branch: main
mode: send
```

`send` 不会直接发送。工作流会先自动执行一次 smoke 预检；只有预检成功后才运行正式发送。

定时任务同样固定执行：

```text
validate -> smoke -> send
```

## 7. 修改定时计划

只修改：

```text
.github/workflows/schedule.yml
```

默认示例：

```yaml
schedule:
  - cron: "7 9 * * *"
    timezone: "Asia/Shanghai"
```

Web 控制中心可以生成 `cron + timezone` 片段，但静态页面不会直接修改仓库。

## 8. 诊断

每次运行都会生成：

```text
run-status.json
logs/
```

Actions 结束后会上传 `sparkflow-<run id>-<attempt>` Artifact，并在 Summary 中记录配置、smoke 和 send 的结果。

如果 smoke 失败，不要继续反复正式发送。优先检查：

1. `COOKIES_*` 是否从 `www.douyin.com/chat` 重新导出。
2. 浏览器中该账号是否仍能直接打开聊天列表。
3. `MATCH_MODE` 与 `TARGETS` 是否一致。
4. Artifact 中的日志和可选失败截图。

## 9. CI 与单分支策略

`SparkFlow CI` 会在 `main` 每次更新时执行 Python 编译和单元测试。

`Main Branch Policy` 会删除所有非 `main` 分支并在删除后复查。这样不会再出现某个工作流继续 checkout 一个已经不存在或能力落后的测试分支。
