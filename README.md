# DouYin SparkFlow

![cover](docs/images/cover.png)

> SparkFlow 现在采用 **单一 `main` 分支 + 单一运行入口 + 单一生产工作流**。Web 控制中心、定时任务、手动 smoke、正式发送和文档都以 `main` 为唯一事实来源。

DouYin SparkFlow 是一套面向个人使用场景的抖音火花自动续火工具，使用 Python + Playwright 自动访问 `https://www.douyin.com/chat`，并可通过 GitHub Actions 定时运行。

## 当前架构

```text
main.py                    # 统一 CLI：send / smoke / validate
core/
  runtime.py               # 运行模式、状态记录、统一调度
  tasks.py                 # 抖音 Web Chat 自动化核心
  browser.py               # Playwright 浏览器生命周期
  msg_builder.py           # 消息构建
utils/
  config.py                # 配置解析、Cookie 标准化、账号任务校验
  validate_config.py       # Actions/本地共用配置校验入口
  export_github_env.py     # GitHub Environment 导出
  logger.py                # 日志
  hitokoto.py              # 每日一言
.github/workflows/
  schedule.yml             # 唯一 SparkFlow 运行工作流
  ci.yml                   # 编译与单元测试
  branch-policy.yml        # 保证仓库仅保留 main
```

详细设计见 [架构说明](docs/架构说明.md)。

## 主要能力

- GitHub Actions 定时执行与手动执行。
- `send` / `smoke` 两种模式共用完全相同的配置和自动化核心。
- 正式发送前自动执行非发送 smoke 预检。
- 多账号、多目标好友。
- 按昵称或抖音号（`short_id`）匹配目标好友。
- Cookie-Editor JSON 标准化与运行前严格校验。
- Web 控制中心生成 Variables / Secrets / cron 配置并展示真实 Actions 状态。
- `run-status.json` + `logs/` 统一诊断产物。
- push 到 `main` 自动执行 Python 编译和单元测试。
- 仓库分支策略自动删除所有非 `main` 分支。

## 统一运行入口

本地或 Actions 都只调用 `main.py`：

```bash
python main.py --validate
python main.py --mode smoke
python main.py --mode send
```

兼容旧环境变量 `SPARKFLOW_SMOKE_TEST=1`；新配置推荐使用 `SPARKFLOW_MODE=smoke|send` 或直接使用 `--mode`。

## GitHub Actions

唯一生产工作流是：

```text
.github/workflows/schedule.yml
```

手动运行 `SparkFlow` 时可选择：

- `smoke`：验证 Cookie、登录态、Web Chat 和目标匹配，不发送消息。
- `send`：先运行 smoke 预检，成功后才正式发送。

定时触发固定执行 `smoke -> send`，两阶段使用同一份 `user-data` Environment 配置。

旧的 `api` / `dev` 分支工作流已经移除。`branch-policy.yml` 会清理已有非 `main` 分支，并在以后创建额外分支时再次执行清理。

## 配置

建议先使用 `docs/` 中的 SparkFlow Web 控制中心生成配置，再写入 GitHub Environment `user-data`。

Environment Variables：

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

每个账号还需要一个 Environment Secret：

```text
COOKIES_<UNIQUE_ID>
```

Cookie 必须从已经登录的 `https://www.douyin.com/chat` 页面导出。

完整步骤见 [GitHub Actions 部署说明](docs/Action部署说明.md) 和 [Web 控制中心说明](docs/配置生成器使用.md)。

## 测试

第一方代码不依赖浏览器即可完成基础回归测试：

```bash
python -m compileall -q main.py core utils tests
python -m unittest discover -s tests -v
```

真实页面兼容性由 `smoke` 模式验证，因为抖音页面结构和登录风控无法用纯单元测试完整模拟。

## 安全边界

- Cookie 只应保存为 GitHub Environment Secrets，不要提交到仓库。
- Web 控制中心不会持久化 Cookie，也不需要 GitHub PAT。
- `smoke` 模式不会发送消息，适合在 Cookie 更新或页面结构变化后先验证。
- 建议只用于个人少量好友，并遵守抖音平台规则和当地法律法规。

## 上游项目

本仓库来源于 DouYinSparkFlow 项目：

[![contributors](https://contrib.rocks/image?repo=2061360308/DouYinSparkFlow)](https://github.com/2061360308/DouYinSparkFlow/graphs/contributors)

## License

MIT，详见 [LICENSE](LICENSE)。
