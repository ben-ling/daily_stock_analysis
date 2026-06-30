# AGENTS.md

本文件用于约束本仓库的默认开发流程，目标是减少重复沟通、减少返工，并让改动和当前项目结构保持一致。

如果本文件与仓库中的脚本、工作流、代码现状不一致，以实际可执行内容为准，并在相关改动中顺手修正文档，避免规则继续漂移。

## 1. 项目架构概览（Architecture Overview）

### 1.1 项目定位（Project Overview）

股票智能分析系统，覆盖 A 股、港股、美股、日股（`.T`）、韩股（`.KS` / `.KQ`）和 ETF。主流程：**抓取数据 -> 技术分析 / 新闻检索 -> LLM 分析 -> 生成报告 -> 多渠道通知推送**。同一后端同时支撑 CLI 调度、FastAPI 服务、Web 工作台与 Electron 桌面端。

### 1.2 关键入口与模块职责

- `main.py`：CLI 主入口（一次性分析、`--schedule` 调度、`--serve` / `--serve-only` API 服务）。先执行 `setup_env()`，再按 flag 编排。
- `server.py`：FastAPI 服务入口，复用 `api.app.create_app()`，供 `uvicorn` 直接加载。
- `api/`：FastAPI 应用。`api/app.py` 是工厂（CORS、auth 中间件、SPA 静态托管、`/api/v1` 挂载）；`api/v1/router.py` 聚合 endpoint（`auth/agent/analysis/history/stocks/backtest/system/usage/portfolio/alerts/decision-signals/alphasift/intelligence/health`）；`api/v1/schemas/` 是 Pydantic 契约层。
- `src/core/`：主流程编排（`pipeline.py` 管理「数据获取 -> 分析 -> 通知」并发与异常隔离）、调度、回测引擎、大盘复盘、交易历、市场策略。
- `src/services/`：业务服务层（分析、历史、持仓、告警、决策信号、运行诊断、运行时调度、股票索引等），是 API 与 repository 之间的语义层。
- `src/repositories/`：数据访问层（MySQL，`src/storage.py` 提供 `get_db()`）。
- `src/schemas/`：领域数据结构与报告 schema。
- `src/agent/`：多 Agent 编排（`orchestrator.py` 模式：`quick/standard/full/specialist`，链路 Technical → Intel → Risk → Decision；`executor.py` 为等价实现，经 `factory.py` 选择；`tools/` 为 LLM 工具注册表；`strategies/`、`skills/` 为策略与技能路由）。
- `src/llm/`：生成后端抽象（`litellm_backend`、`local_cli_backend`、`hermes`、`backend_registry` 解析 `litellm`/`codex_cli`/`auto`，`usage` 计量）。
- `src/notification*.py` + `src/notification_sender/`：通知汇总与多渠道发送（企业微信、飞书、Telegram、Discord、Slack、邮件、Pushover、ntfy、gotify、pushplus、serverchan3、Astrbot、自定义 webhook）。
- `data_provider/`：多数据源策略层（`DataFetcherManager` 自动 fallback）。优先级见 `data_provider/__init__.py`：Tushare（配 token 时最高）→ Efinance → AkShare → Pytdx → Baostock → YFinance → Longbridge；另有 Tencent、Finnhub、AlphaVantage、TickFlow、台湾三大法人等专用 fetcher。
- `bot/`：机器人接入（`platforms/` 支持钉钉、Discord、飞书 stream；`commands/` 为命令路由）。
- `apps/dsa-web/`：Vite + React 19 + TS + Tailwind v4 + Zustand + React Router 前端，`src/api/` 为后端 API 客户端。
- `apps/dsa-desktop/`：Electron 桌面端（`main.js`/`preload.js`，复用 Web 构建产物，打包内嵌 `dist/backend/stock_analysis`）。
- `scripts/`：本地与 CI 脚本（`ci_gate.sh`、`test.sh`、`check_ai_assets.py`、stock index 生成、桌面端打包）。
- `.github/workflows/`：CI、发布、每日任务。
- `strategies/`：YAML 策略定义（15 种内置策略）。
- `templates/`：Jinja2 报告模板（`report_markdown.j2`、`report_brief.j2`、`report_wechat.j2`）。
- `tests/`：pytest 测试套件。

### 1.3 运行时数据流

1. `pipeline.py` 用 `ThreadPoolExecutor` 并发处理多只股票，单股失败不阻断整体。
2. 每只股票：`DataFetcherManager` 按优先级取行情/K线/资金流/筹码 → `StockTrendAnalyzer` 算技术指标 → `SearchService` 取新闻 → `GeminiAnalyzer`（实际为通用 LLM 分析器，经 `src/llm/` 后端）生成决策报告 → `extract_and_persist_from_analysis_result` 抽取决策信号 → `NotificationService` 按路由分发。
3. Agent 模式（`src/agent/`）提供多轮追问与策略问股，经 `orchestrator.py` 串联子 agent。
4. API 模式由 `RuntimeSchedulerService` 在 FastAPI lifespan 内托管调度，与 CLI `--schedule` 互斥（通过 `CLI_SCHEDULER_OWNER_ENV` 协调归属）。

## 2. 构建与常用命令（Build & Commands）

### 运行应用

```bash
python main.py
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### 后端验证

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh                 # 全量：syntax + flake8 关键项 + 确定性检查 + 离线测试
./scripts/ci_gate.sh syntax          # 仅语法
./scripts/ci_gate.sh flake8          # 仅 flake8
./scripts/ci_gate.sh deterministic   # code + yfinance 识别检查
./scripts/ci_gate.sh offline-tests   # pytest -m "not network"
python -m pytest -m "not network"
python -m py_compile <changed_python_files>
./scripts/test.sh <scenario>         # 见 scripts/test.sh：market/a-stock/etf/hk-stock/us-stock/mixed/single/dry-run/full/quick/code/yfinance/syntax/flake8/all
```

### Web / Desktop

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
npm run test            # vitest run
npm run test:smoke      # playwright e2e

cd ../dsa-desktop
npm install
npm run build           # electron-builder（需先构建后端 dist/backend/stock_analysis 与 Web）
npm run test            # node --test tests/*.test.js
```

### Docker

```bash
docker-compose -f ./docker/docker-compose.yml up -d analyzer         # 定时模式
docker-compose -f ./docker/docker-compose.yml up -d server           # FastAPI 模式
```

### PR / CI 证据

```bash
gh pr view <pr_number>
gh pr checks <pr_number>
gh run view <run_id> --log-failed
```

## 3. 代码风格（Code Style）

- Python：`black`（line-length 120，target py310/311/312）+ `isort`（profile=black，line_length=120）。`flake8` max-line-length=120，忽略 `E501,W503,E203,E402`。CI 闸仅强制 `E9,F63,F7,F82`（语法与未定义名）。
- 注释 / docstring / 日志文案以清晰准确为准，不强制英文，但应与文件语境一致。
- 前端：ESLint 9 + `typescript-eslint`，TS 严格模式（`tsc -b`），Tailwind v4，React 19（含 `babel-plugin-react-compiler`）。
- 不写死密钥、账号、路径、模型名、端口或环境差异逻辑；优先复用现有模块、配置入口、脚本和测试，不新增平行实现。

## 4. 测试（Testing）

### 后端 pytest（`setup.cfg [tool:pytest]`）

- 测试发现：`test_*.py` / `test_*`，`addopts = -v --tb=short`。
- 标记：`unit`（快速离线单测）、`integration`（无外部网络的服务级集成）、`network`（需外部网络/三方服务）。离线运行用 `pytest -m "not network"`；`network-smoke` workflow 运行 `pytest -m network`，为非阻断观测项。
- `tests/conftest.py` 包含 asyncio / FastAPI TestClient 兼容补丁；`tests/litestub_stub.py` 提供离线 LLM stub。
- 测试中允许 `assert`（bandit 跳过 `B101`，排除 `tests/`）。

### 前端 / 桌面端

- Web：`vitest run`（jsdom + @testing-library/react），e2e 用 `@playwright/test`（`apps/dsa-web/e2e/`）。
- Desktop：`node --test tests/*.test.js`。

### CI 覆盖原则

| 检查项 | 来源 | 说明 | 是否阻断 |
| --- | --- | --- | --- |
| `ai-governance` | `.github/workflows/ci.yml` | 校验 `AGENTS.md` / `CLAUDE.md` / `.github` 指令 / `.claude/skills` 关系 | 是 |
| `backend-gate` | `.github/workflows/ci.yml` | 执行 `./scripts/ci_gate.sh` | 是 |
| `docker-build` | `.github/workflows/ci.yml` | Docker 构建与关键模块导入 smoke | 是 |
| `web-gate` | `.github/workflows/ci.yml` | 前端改动时执行 `npm run lint` + `npm run build` | 是（触发时） |
| `network-smoke` | `.github/workflows/network-smoke.yml` | `pytest -m network` + `scripts/test.sh quick` | 否，观测项 |
| `pr-review` | `.github/workflows/pr-review.yml` | PR 静态检查 + AI 审查 + 自动标签 | 否，辅助项 |

若 PR 上已有对应 CI 结果，可直接引用 CI 结论；若 CI 未覆盖改动面，或本地与 CI 环境差异较大，需要补充说明本地验证与缺口。

### 按改动面执行

- Python 后端（`main.py`、`src/`、`data_provider/`、`api/`、`bot/`、`tests/`）：优先 `./scripts/ci_gate.sh`；最低 `python -m py_compile <changed>`。若影响 API、任务编排、报告生成、通知发送、数据源 fallback、认证、调度，交付说明要写明覆盖路径。
- Web 前端（`apps/dsa-web/`）：`cd apps/dsa-web && npm ci && npm run lint && npm run build`。涉及 API 联调、路由、状态、Markdown/图表渲染或认证状态时，说明联动面与未覆盖风险。
- 桌面端（`apps/dsa-desktop/`、`scripts/run-desktop.ps1`、`scripts/build-desktop*.ps1`、`scripts/build-*.sh`、`docs/desktop-package.md`）：先构建 Web，再构建桌面端；受平台限制时说明 Web 产物、Electron 构建与 Release 工作流影响。
- API / Schema / 认证联动（`api/**`、`src/schemas/**`、`src/services/**`、`apps/dsa-web/**`、`apps/dsa-desktop/**`）：至少覆盖后端验证 + 受影响客户端构建。涉及登录、Cookie、会话、轮询、字段增删或枚举变化时，必须写出兼容性影响。
- 文档与治理文件（`README.md`、`docs/**`、`AGENTS.md`、`.github/copilot-instructions.md`、`.github/instructions/**`、`.claude/skills/**`）：不强制代码测试；需确认命令、配置项、文件名、工作流名称与实际仓库一致。改 AI 协作治理资产时执行 `python scripts/check_ai_assets.py`。
- 工作流 / 脚本 / Docker（`.github/**`、`scripts/**`、`docker/**`）：运行最接近改动面的本地验证；交付说明影响哪条流水线、发布或部署路径；未执行 Docker / Actions 验证时说明原因与风险。
- 网络或三方依赖相关改动：先跑离线或确定性检查；确认 timeout、retry、fallback、异常文案、降级路径仍成立；未执行在线验证时说明原因。

## 5. 安全（Security）

- 认证（`src/auth.py`）：单开关 `ADMIN_AUTH_ENABLED`，基于文件凭证。密码以 PBKDF2（100k 迭代）+ salt 存储；会话 Cookie 名 `dsa_session`，签名 secret；登录限流 5 次 / 300s 窗口；会话默认 24h。首登设置初始密码，支持 Web 改密与 CLI 重置。
- 中间件：`api/middlewares/auth.py` 在 `ADMIN_AUTH_ENABLED=true` 时对 `/api/v1/*` 强制会话校验（登录、状态、健康检查、OpenAPI 文档除外）。
- CORS：默认仅放行本地 dev 端口；`CORS_ALLOW_ALL=true` 时若未开认证会记录告警，且 `allow_credentials` 自动关闭。
- 静态资源：`/assets/*` 与 SPA 回退均经 `_resolve_asset_path` 路径包含校验，拒绝 `..`、绝对路径、`\x00`、盘符越界。
- 密钥与凭证：仅从 `.env` / 环境变量读取，不入库、不写死；新增配置项须同步 `.env.example`。避免扩大权限、暴露 secret 或无文档化的破坏性自动化。
- 数据源 fallback：单一数据源 / 通知渠道 / 可选集成失败不应拖垮主分析流程，除非需求明确要求 fail-fast。

## 6. 配置（Configuration）

- 配置入口：`src/config.py` 单例 `Config`（dataclass），`setup_env()` 加载 `.env`，`get_config()` 返回单例。`src/core/config_manager.py` / `config_registry.py` 提供动态管理与校验；`SystemConfigService` 暴露给 API 运行时读写。
- 环境文件：`.env`（可用 `ENV_FILE` 覆盖路径）。新增配置项必须同步 `.env.example` 与相关文档，并评估本地运行、Docker、GitHub Actions、API、Web、Desktop 的影响。新配置优先「不配置也可运行，配置后增强能力」，避免叠加开关和互斥模式。
- LLM 后端：`src/llm/backend_registry.py` 支持 `litellm` / `codex_cli` / `auto`（agent 专用）；渠道经 `hermes` 解析，可多模型 / 图片识别 / 本地模型 / 高级路由（见 `docs/LLM_CONFIG_GUIDE.md`）。
- 数据源：优先级由是否配置 `TUSHARE_TOKEN` 动态调整（见 `data_provider/__init__.py`）；超时 / 重试 / 降级策略在 fetcher 内部维护。
- 通知路由：`src/notification_routing.py` 按渠道分发；`notification_noise.py` 控制告警静默 / 严重级别 / 静默时段与时区校验。
- 调度：`src/scheduler.py`（`--schedule`）与 `src/services/runtime_scheduler.py`（API lifespan）经 `CLI_SCHEDULER_OWNER_ENV` 协调归属，避免重复触发。
- 报告语言：`src/report_language.py` 支持多语言（含 `ko`），由 `REPORT_LANGUAGE` 等环境变量驱动。
- Docker：`docker/docker-compose.yml` 以 `env_file: ../.env` 注入；不要把 `../.env` 作为单文件 volume 挂载到 `/app/.env`（会阻断配置保存的原子 `os.replace`）。挂载卷为 `data/logs/reports/strategies`（只读）/`longbridge_tokens`。

## 7. 硬规则

- 遵循现有目录边界：
  - 后端逻辑优先放在 `src/`、`data_provider/`、`api/`、`bot/`
  - Web 前端改动在 `apps/dsa-web/`
  - 桌面端改动在 `apps/dsa-desktop/`
  - 部署与流水线改动在 `scripts/`、`.github/workflows/`、`docker/`
- 未经明确确认，不执行 `git commit`、`git tag`、`git push`。
- commit message 使用英文，不添加 `Co-Authored-By`。
- 不写死密钥、账号、路径、模型名、端口或环境差异逻辑。
- 优先复用现有模块、配置入口、脚本和测试，不新增平行实现。
- 默认稳定性优先于“顺手优化”；非当前任务直接需要的重构、抽象和基础设施迁移一律克制。
- 新增配置项时，必须同步更新 `.env.example` 和相关文档。
- 涉及用户可见能力、CLI/API 行为、部署方式、通知方式、报告结构变化时，必须同步更新相关文档与 `docs/CHANGELOG.md`。
- 修改报告格式、报告渲染效果或 Web UI 界面时，PR 描述必须附受影响报告 / 页面截图；涉及前后差异时优先附前后对比，无法截图时说明原因与替代可视证据。
- Issue / PR 过程截图、审查截图、一次性验收截图和临时可视证据不得作为仓库文件合入；应放在 PR 描述、PR 评论、GitHub 附件、Actions artifact 或外部可访问证据链接中。产品长期文档确需保留的示意图除外，但文件名和文档语义必须脱离具体 issue / PR 编号。
- `docs/CHANGELOG.md` 的 `[Unreleased]` 段使用**扁平格式**：每条独立一行，格式为 `- [类型] 描述`，类型取值：`新功能`/`改进`/`修复`/`文档`/`测试`/`chore`；**禁止在 `[Unreleased]` 内新增 `### 类目标题`**，以减少并发 PR 的 merge 冲突。发版时由 maintainer 汇总整理成带标题的正式格式。
- `README.md` 只用于项目定位、核心能力总览、快速开始、主要入口、赞助/合作等首页级信息；非必要不更新 README，避免持续膨胀。
- 更细的模块行为、页面交互、专题配置、排障说明、字段契约、实现语义和边界条件，优先更新对应 `docs/*.md` 或专题文档，不写入 README。
- 变更中英双语文档之一时，需评估另一份是否需要同步；若未同步，交付说明里要写明原因。
- 注释、docstring、日志文案以清晰准确为准，不强制要求英文，但应与文件语境保持一致。

## 7.1 PR 标题规范（非阻断建议）

- 推荐使用 `<类型>: <修改内容>` 作为 PR 标题，例如 `fix: 修复大盘分析历史记录丢失`，优先类型为 `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci`。
- 标题应描述实际变更内容，建议不添加 `[codex]`、`codex`、`autocode`、`copilot` 或其他工具/agent 来源前缀。
- 该规范仅用于协作可读性与一致性提示，不应单独作为 review process blocker。

## 7.2 贡献质量底线

- 本仓库不接受以堆叠代码量、扩大 diff 面、补丁式响应 review 来替代真实设计收敛的 PR。
- 贡献质量以是否解决明确问题、是否最小化影响面、是否保持现有契约一致、是否覆盖真实风险路径为准；不以新增行数、文件数量、功能宣传或“看起来完整”为准。
- 请不要把本仓库当作低成本试验场、简历展示场或 contribution farming 场所。任何 PR 都必须证明作者理解当前系统契约，并完成基本自审、集成和验证。
- 使用 AI 辅助开发本身不是问题；问题是提交 AI 生成后未经人工语义审查、未验证、未收敛的代码。此类 PR 会按低质量提交处理。
- review 反馈后，不接受只在被指出的位置追加局部 patch。作者必须重新检查同一业务语义涉及的所有入口、配置、测试、文档、workflow 和用户可见路径。
- 如果一个 PR 在多轮 review 后仍持续出现同类契约漂移、重复 fallback、测试绕过真实风险层、PR body 与实际 diff 不一致等问题，维护者可以要求关闭重做，而不是继续逐点 review。

## 8. AI 协作资产治理

- `AGENTS.md` 是仓库内 AI 协作规则的唯一真源。
- `CLAUDE.md` 必须是指向 `AGENTS.md` 的软链接，用于兼容 Claude 生态。
- `.github/copilot-instructions.md` 与 `.github/instructions/*.instructions.md` 是 GitHub Copilot / Coding Agent 的镜像或分层补充；若与本文件冲突，以 `AGENTS.md` 为准。
- 仓库协作 skill 存放在 `.claude/skills/`，分析产物存放在 `.claude/reviews/`；前者可以入库，后者默认视为本地产物。
- 根目录 `SKILL.md` 与 `docs/openclaw-skill-integration.md` 属于产品或外部集成说明，不是仓库协作规则真源。
- 若未来新增 `.agents/skills/` 或其他 agent 专用目录，必须先明确单一真源，再通过脚本或镜像同步；禁止手工长期维护多份同义内容。
- 修改 AI 协作治理资产时，执行：

```bash
python scripts/check_ai_assets.py
```

## 9. 默认工作流

1. 先判断任务类型：`fix / feat / refactor / docs / chore / test / review`
2. 先读现有实现、配置、测试、脚本、工作流和文档，再动手修改。
3. 识别改动边界：后端 / API / Web / Desktop / Workflow / Docs / AI 协作资产。
4. 先判断是否命中高风险区域：配置语义、API / Schema、数据源 fallback、报告结构、认证、调度、发布流程、桌面端启动链路。
5. 只做和当前任务直接相关的最小改动，不顺手夹带无关重构。
6. 如果发现文档、脚本、工作流描述不一致，优先信任实际代码与工作流，再决定是否顺手修正文档。
7. 改完后按下面的验证矩阵执行检查。
8. 最终交付默认要说明：
   - 改了什么
   - 为什么这么改
   - 验证情况
   - 未验证项
   - 风险点
   - 回滚方式

## 10. 稳定性护栏

- 配置与运行入口：
  - 修改 `.env` 语义、默认值、CLI 参数、服务启动方式、调度语义时，要同时评估本地运行、Docker、GitHub Actions、API、Web、Desktop 的影响。
  - 新配置优先做到“不配置也可运行，配置后增强能力”，避免叠加开关和互斥模式。

- 数据源与 fallback：
  - 修改 `data_provider/` 时，要关注数据源优先级、失败降级、字段标准化、缓存与超时策略。
  - 单一数据源失败不应拖垮整个分析流程，除非需求明确要求 fail-fast。

- API / Web / Desktop 兼容：
  - 改 API / Schema / 认证 / 报告载荷时，要同时检查后端、Web、Desktop 的兼容性。
  - 默认优先追加字段、保留旧字段或提供兼容层，避免无提示破坏现有客户端。

- 报告 / Prompt / 通知：
  - 修改报告结构、Prompt、提取器、通知模板、机器人链路时，要检查上游输入与下游消费方是否仍兼容。
  - 单一通知渠道失败不应拖垮整个分析主流程，除非需求明确要求 fail-fast。
  - 修改 `src/services/image_stock_extractor.py` 中 `EXTRACT_PROMPT` 时，要在 PR 描述中附完整最新 prompt。

- 工作流 / 发布 / 打包：
  - 修改自动 tag、Release、Docker 发布、日常分析或桌面端打包流程时，要评估触发条件、产物路径、权限边界和回滚方式。
  - 自动 tag 默认保持 opt-in：只有 commit title 含 `#patch`、`#minor`、`#major` 才触发版本号更新，除非需求明确要求改变发布策略。

## 11. Issue / PR / Skill 工作流

- 仓库内已有以下 skill，可优先复用：
  - `.claude/skills/analyze-issue/SKILL.md`
  - `.claude/skills/analyze-pr/SKILL.md`
  - `.claude/skills/fix-issue/SKILL.md`
- 如果任务明确是 issue 分析、PR 审查、issue 修复，优先按对应 skill 执行，并将产物保存到 `.claude/reviews/`。
- skill 中的命令、模板、验证顺序和交付结构必须与 `AGENTS.md` 保持一致。
- 每次进行 PR 创建 / 更新、PR 审查或 issue 分析前，必须先同步最新代码基线：先检查工作区状态并执行 `git fetch --all --prune`；若工作区干净且当前分支可 fast-forward，则执行 `git pull --ff-only`。如存在本地改动、冲突状态、未跟踪风险文件或无法 fast-forward，不得强行切分支、stash、reset 或覆盖本地状态；PR 审查 / issue 分析可改用已 fetch 的远端 refs/PR head 做分析，并在分析文档中明确记录未更新本地工作树的原因、当前本地 HEAD 与使用的远端基线；PR 创建 / 更新应先说明当前分支与目标基线差异，必要时请求用户确认 rebase、merge 或继续基于当前分支推进。
- skill 默认优先读取 CI / 工作流证据，再决定是否补本地验证。
- 除上述 PR 创建 / 更新、PR 审查 / issue 分析的安全 fast-forward 同步外，skill 不得默认执行 `git pull`、`git push`、`git tag`、`gh pr create` 等会改变远端或当前分支状态的操作；这些操作必须要求用户确认。
- PR 审查默认顺序：
  1. 必要性
  2. 关联性
  3. 标题建议（`<类型>: <修改内容>`，且不含工具/agent 前缀；不作为硬性阻断项）
  4. 描述完整性（对照 `.github/PULL_REQUEST_TEMPLATE.md`）
  5. 验证证据
  6. 实现正确性
  7. 合入判定
- 对 `fix` 类 PR，必须说明：原问题、根因、修复点、回归风险。
- 合入阻断条件：
  - 正确性或安全性问题
  - 阻断型 CI 未通过
  - PR 描述与实际改动内容实质性矛盾
  - 缺少回滚方案
  - 反复出现未收敛的契约漂移、补丁堆叠或验证证据失真

## 11.1 Review 反馈处理与补丁堆叠禁止

当你处理 review 反馈时，禁止只在 reviewer 点名的位置追加局部 patch 后声称“已全部修复”。你必须先重新理解 reviewer 指出的业务契约，再检查同一语义涉及的所有入口、配置、测试、文档、workflow 和用户可见路径。

收到 review 反馈后，必须按以下顺序处理：

1. 逐条列出 reviewer 指出的原问题。
2. 说明根因，不能只描述“改了哪几行”。
3. 找出同一语义影响的所有相关路径，例如 runtime、API/Web、CLI、diagnostics、workflow、docs、tests。
4. 修复完整契约，而不是只修复当前失败测试或当前评论行。
5. 补充能覆盖 reviewer 反例的回归测试、最终入口验证，或明确说明无法验证的原因。
6. 同步更新 PR body，保证 scope、验证结果、兼容性、风险和回滚方案与当前 head 一致。

如果你无法完成上述收敛，不要继续堆叠补丁，不要声称 ready for merge。应主动说明当前 PR 需要拆分、关闭重做，或请求维护者确认新的最小范围。

以下行为会被视为低质量 PR：

- 用 broad fallback、静默降级、`return False/None/[]` 掩盖不清晰的契约。
- 测试 mock 掉真实风险层，只证明局部实现通过。
- CI 通过后声称问题已关闭，但没有覆盖 reviewer 指出的反例。
- PR body 与实际 diff、验证结果或兼容风险不一致。
- review 后继续追加零散 patch，而不是重新收敛完整语义。
- 同一业务语义在 runtime、Web/API、docs、workflow、tests 中表现不一致。

CI 通过只能说明自动检查通过，不能替代人工语义收敛，也不能单独证明 reviewer 指出的反例已经关闭。

## 12. 交付与发布

- 默认交付结构：
  - `改了什么`
  - `为什么这么改`
  - `验证情况`
  - `未验证项`
  - `风险点`
  - `回滚方式`
- 如果是 `docs` 任务，可直接写：`Docs only, tests not run`，但仍需说明是否核对了命令和文件名。
- 自动 tag 默认不触发，只有 commit title 包含 `#patch`、`#minor`、`#major` 才会触发版本号更新。
- 手动打 tag 必须使用 annotated tag。
- 用户可见变更优先通过 PR 合入，并补齐 label 与验证说明。
