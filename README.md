# DouYin Spark Flow

![cover](docs/images/cover.png)

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)
![Playwright](https://img.shields.io/badge/Playwright-%E2%9C%94-green?logo=playwright)
![chrome-headless-shell](https://img.shields.io/badge/chrome--headless--shell-%E2%9C%94-brightgreen?logo=googlechrome)

> `dev` 分支迁移到 `https://www.douyin.com/chat`，加载更稳定并支持更多好友匹配方式。该分支仍处于测试阶段。

## 项目介绍

DouYin Spark Flow 是一套面向个人使用场景的抖音火花自动续火脚本，通过 Python + Playwright 执行消息任务，并可由 GitHub Actions 定时运行。

本仓库同时提供 **SparkFlow Web 控制中心**。控制中心与 Python 环境变量和 GitHub Actions 工作流直接对应，用于配置生成、账号任务管理、Cookie JSON 本地检查、定时计划生成和真实 Actions 状态查看。

### 主要能力

- [x] GitHub Actions 定时运行与手动触发
- [x] Web 控制中心，支持桌面端和移动端
- [x] 读取公开仓库真实 GitHub Actions Workflow / Run 状态
- [x] 运行前账号、Cookie、目标好友、定时计划四项预检
- [x] 多账号与多目标任务
- [x] 按昵称或抖音号匹配目标好友
- [x] Environment Variables / Secrets 键名生成
- [x] `cron` + `timezone` 定时计划生成
- [x] 每日一言消息模板
- [x] 源码部署到自有服务器

主任务使用 Playwright 和 `chrome-headless-shell` 自动访问抖音相关页面并执行消息任务。Web 控制中心只负责配置和状态展示，不在浏览器中执行抖音自动化。

## Web 控制中心

控制中心源码位于：

```text
docs/
```

可通过 GitHub Pages 部署，也可以直接作为静态站点托管。

控制中心遵循以下安全边界：

- Cookie 只在当前页面内存中用于格式检查。
- 保存草稿时不会持久化 Cookie。
- 不要求在静态页面中填写 GitHub PAT。
- 修改 Secrets、触发 Workflow 等写操作通过 GitHub 官方页面完成。
- 没有真实 Workflow / Run 时显示空状态，不使用演示数据补位。

详细说明见：[SparkFlow Web 控制中心](docs/配置生成器使用.md)。

## 使用方法

**准备：** GitHub 账号、浏览器，以及运行 SparkFlow 所需的账号配置。

1. 打开 [SparkFlow Web 控制中心说明](docs/配置生成器使用.md)，完成基础配置和账号任务。
2. 按 [GitHub Actions 部署说明](docs/Action部署说明.md) 创建 `user-data` Environment，并写入 Variables / Secrets。
3. 在 GitHub Actions 中手动运行一次，确认真实执行结果。
4. 验证通过后再依赖定时计划运行。

源码部署用户可参考：[源代码部署说明](docs/源代码部署说明.md)。

## 上游项目与贡献者

本仓库来源于 DouYinSparkFlow 项目。上游贡献者信息：

[![contributors](https://contrib.rocks/image?repo=2061360308/DouYinSparkFlow)](https://github.com/2061360308/DouYinSparkFlow/graphs/contributors)

上游讨论区：

[DouYinSparkFlow Discussions](https://github.com/2061360308/DouYinSparkFlow/discussions)

## Star 趋势

[![Star History Chart](https://api.star-history.com/svg?repos=2061360308/DouYinSparkFlow&type=Date)](https://www.star-history.com/#2061360308/DouYinSparkFlow&Date)

## 免责声明

1. 本项目为开源学习用途，仅用于技术研究和个人自用，严禁用于商业用途、恶意刷量或违反抖音平台规则的行为。
2. 使用本脚本产生的一切风险，包括账号限流、封禁、处罚等，由使用者自行承担。
3. 本项目使用公开页面和浏览器自动化能力，使用者需遵守相关平台协议和法律法规。
4. 请合理控制运行频率，避免给平台造成额外压力，建议仅用于个人少量好友的火花维系。
5. 使用本项目即表示已经阅读并接受上述说明。

## 开源协议

本项目基于 MIT 协议开源，详见 [LICENSE](LICENSE)。
