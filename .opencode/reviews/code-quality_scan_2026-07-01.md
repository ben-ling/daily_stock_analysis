# 前端代码质量扫描

**建议优先修复 P0 项，其余可迭代优化**

| 范围 | apps/dsa-web/src | 扫描时间 | 2026-07-01 |
|------|------------------|---------|------------|

## Issues

| Sev | File | Issue | Fix |
|-----|------|-------|-----|
| 🔴 | `StockScreeningPage.tsx:392-431` | 硬编码 `red-500`/`blue-500`/`amber-500` 等，无主题变量 | 替换为 `var(--color-*)` 或主题类 |
| 🔴 | `PortfolioPage.tsx:1408-1519` | 7+ 原生 `<input>` 无 `aria-label`，3+ 原生 `<button>` 未用 `Button` | 接入共享 `Input`/`Button` 组件 |
| 🔴 | `DecisionSignalsPage.tsx:631,689` | 原生 `<button className="btn-primary">` | 替换为 `<Button variant="primary">` |
| 🔴 | `ChatPage.tsx:1095` | `quickQuestions.map((q, i)` 用 `key={i}` | 用 `q.label` 或 `q.skill` 作为 key |
| 🔴 | `ChatPage.tsx:1184` | `.split('\n').map((line, i)` 用 `key={i}` | 用 `msg.id + '-' + i` |
| 🔴 | 6 处 `map((_, index)` 用 `key={index}` | ChatPage/SettingsPage/TokenUsagePage/JsonViewer/SettingsLoading 列表 key 不稳定 | 使用稳定唯一标识 |
| 🔴 | `LoginPage.tsx:99-163` | orb 和图标使用 `emerald-*` 固定色 | 通过 `useTheme()` 动态计算 |
| 🔴 | `NotFoundPage.tsx:19` | 内联 `style={{ backgroundImage: 'linear-gradient(...)' }}` | 提取为 Tailwind 渐变类 |
| 🟡 | `TokenUsagePage.tsx:2` | 导入 `Clock3` 但未使用 | 移除无用导入 |
| 🟡 | `SettingsPage.tsx:553` | `useEffect` 缺少 `status` 依赖 | 补充依赖项 |
| 🟡 | `ChatPage.tsx` / `StockScreeningPage.tsx` | 消息渲染区/选股区无独立 ErrorBoundary | 添加 ErrorBoundary 包裹 |
| 🟡 | `ScoreGauge.tsx:239` | `style={{ color: isDark ? colors.color : colors.lightEndColor }}` | 改用 CSS 变量 |
| 🟢 | `StockBarItem.tsx:56` | `style={{ boxShadow: '0 0 10px rgba(...)' }}` | 改用 `shadow-*` 类 |
| 🟢 | `PortfolioPage.tsx` 多处 `rounded-xl border settings-border bg-card/90 p-1` | 重复卡片样式模式 | 提取公用 CSS 类 |
| 🟢 | `ChatPage.tsx` | 4+ 内联 SVG 图标，>100 行 | 提取为 lucide-react 图标 |

## Notes
- TypeScript 严格模式执行良好，**无显式 `any` 类型** 👍
- ESLint 仅 1 个 warning（`SettingsPage.tsx:553`），无 error
- 上次 UI 优化已覆盖 8 个文件（P0/P1/P2 共 11 项），构建通过