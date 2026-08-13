# GitHub Actions 部署

SparkFlow 已内置 GitHub Actions 工作流和 Web 控制中心。推荐先在控制中心完成配置、账号、Cookie 与定时计划预检，再把生成结果写入 GitHub Environment `user-data`。

> Web 控制中心是纯静态页面。它可以生成配置并读取公开的 GitHub Actions 运行状态，但不会在浏览器中保存 Cookie，也不会要求你把 GitHub Token 放进网页。

## 1. Fork 并启用 Actions

1. Fork 本仓库到自己的 GitHub 账号。
2. 打开 Fork 后仓库的 `Actions` 页面。
3. 如果 GitHub 提示 Fork 的工作流尚未启用，先手动启用 Workflows。

首次部署完成后，建议手动运行一次 `DouYin Spark Flow Schedule Run`，确认 Cookie、好友匹配与页面结构都正常。

## 2. 打开 Web 控制中心

控制中心源码位于 `docs/`，可通过 GitHub Pages 部署。

控制中心包含：

- **运行态**：读取当前公开仓库真实的 GitHub Actions Workflow / Run 状态；没有运行记录时会明确显示空状态，不使用模拟数据。
- **基础配置**：生成与 `utils/config.py` 一致的环境变量。
- **账号任务**：生成 `TASKS` 与每个账号对应的 `COOKIES_<UNIQUE_ID>` Secret 键名。
- **定时计划**：生成与 `.github/workflows/schedule.yml` 对应的 `cron` + `timezone` 片段。
- **部署输出**：集中展示 Environment Variables 和需要创建的 Secrets。

Cookie 内容只保留在当前页面内存中。保存本地草稿时不会写入 Cookie。

## 3. 创建 `user-data` Environment

进入自己的 SparkFlow 仓库：

`Settings` → `Environments` → `New environment`

环境名称填写：

```text
user-data
```

项目的生产工作流通过 `environment: user-data` 读取这里配置的 Variables 和 Secrets。

## 4. 配置 Environment Variables

在控制中心完成基础配置和账号任务后，进入“部署输出”页面。

把 **Environment Variables** 中的键和值写入：

`Settings` → `Environments` → `user-data` → `Environment variables`

当前 Python 代码实际读取的变量包括：

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

其中 `TASKS` 是 JSON 数组，每个账号包含：

```json
{
  "username": "账号标识",
  "unique_id": "唯一标识",
  "targets": ["好友1", "好友2"]
}
```

## 5. 配置 Environment Secrets

每个账号都需要一个独立 Cookie Secret，键名规则为：

```text
COOKIES_<UNIQUE_ID大写>
```

例如 `unique_id` 为 `zion0929`：

```text
COOKIES_ZION0929
```

进入：

`Settings` → `Environments` → `user-data` → `Environment secrets`

把 Cookie-Editor 导出的 JSON 数组作为 Secret 值粘贴进去。

控制中心会检查 Cookie 是否是非空 JSON 数组，并检查常见 Playwright Cookie 字段和 `douyin.com` 域名，但最终登录有效性仍需要通过一次真实 Actions 运行确认。

## 6. 修改执行时间

生产工作流位于：

```text
.github/workflows/schedule.yml
```

当前工作流支持 GitHub Actions 的 `timezone` 配置，因此可以直接使用本地时间。例如每天北京时间 09:07：

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "7 9 * * *"
      timezone: "Asia/Shanghai"
```

控制中心“定时计划”页面可以生成对应片段，但纯静态页面不会假装已经写回仓库。复制片段后仍需提交 `.github/workflows/schedule.yml` 才会真正生效。

## 7. 手动运行验证

进入仓库的 `Actions` 页面，选择：

```text
DouYin Spark Flow Schedule Run
```

点击 `Run workflow`。

建议重点检查：

1. `Validate SparkFlow configuration` 是否通过。
2. `Run DouYin Spark Flow` 是否成功。
3. Actions Summary 中的配置和运行状态。
4. 失败时下载 `run-logs-*` Artifact 查看 `logs/` 和 `run-status.json`。

如果控制中心显示“API 返回 0 个工作流”或“暂无运行记录”，通常表示这个 Fork 的 Actions 还没有启用或还没有完成过一次运行。启用并手动运行后，再刷新控制中心即可看到真实状态。

## 8. 安全说明

- 不要把 Cookie 提交到 Git 仓库。
- 不要把 Cookie 放进普通 Environment Variables，应使用 Environment Secrets。
- 控制中心不批量导出 Cookie 值，只显示需要创建的 Secret 键名和本地格式检查结果。
- 不要在静态页面中填写 GitHub PAT。涉及触发工作流、修改 Secrets 等写操作，直接通过 GitHub 官方页面完成。

Cookie 获取和好友匹配方式见：[SparkFlow 控制中心与账号配置说明](配置生成器使用.md)。
