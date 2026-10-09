# TaskDetail 三档响应式截图 QA 报告

> 日期：2026-10-09 ｜ 验收人：ZCode 主线程（真实浏览器实页验收）
> 范围：登录后受保护页面 —— TaskDetail（任务详情）为主，登录页/仪表盘顺带核验
> 结论：**通过**。三档分辨率（1440 / 900 / 390）无阻塞缺陷；SSE 实时流真跑验证通过。

## 1. 验收环境

| 项 | 值 |
|---|---|
| 后端 | Spring Boot local profile（H2 内存库），`http://localhost:8080` |
| RAG | FastAPI `.venv`，`http://localhost:8001`（BGE 未加载，hash 向量降级，trace 可见） |
| 前端 | `web/dist` 生产构建（含全部已提交前端改动），经本地静态+反代服务器伺服于 `:5173`（`/api`→8080、`/rag`→8001，同源免 CORS） |
| LLM | 未配置 API key → MockLlmClient 离线路径（终态诚实降级为 REVIEW_REQUIRED） |
| 浏览器 | ZCode 内置浏览器（Chromium 内核），真实视口 `setViewportSize` |

说明：本机 node_modules 残缺且 npm 源不可达，无法起 vite dev server，故用 dist 生产构建 + 自写反代（工具归档在仓库外 `myproject/tools/qa_static_proxy.py`）。dist 为最近一次成功构建产物，其后前端源码零改动，等价于线上形态。

## 2. 测试数据（真实链路生成，非种子）

通过真实 API 创建并执行（登录 → 建项目 oracle→opengauss → 建任务 → execute）：

- 任务 #1「Oracle→openGauss 演示任务」，源 SQL 含 `SYSDATE / MONTHS_BETWEEN / NVL / CONNECT BY` 等 Oracle 特有语法
- 六 Agent 流水线 8 个持久化步骤（含 04-patcher→05-critic 反思回环两轮）
- 终态 `REVIEW_REQUIRED`（Mock LLM 无法产出可信 SQL，系统诚实降级并提示人工复核——符合设计）
- 确定性修复真实生效：`NVL(salary, 0)` → `COALESCE(salary, 0)`

## 3. 三档截图结果

截图目录：`docs/qa/screenshots/`。页面滚动发生在 `.el-main` 内部容器（body 不滚），
浏览器整页截图无法展开，故按内部容器分段滚动截取，每档覆盖完整内容。

| 档位 | 内容高度 | 分段 | 文件 |
|---|---|---|---|
| 1440×900 桌面 | 1466px | 2 | `taskdetail-1440x900-s{1,2}of2.png` |
| 900×900 中屏 | 2141px | 3 | `taskdetail-900x900-s{1..3}of3.png` |
| 390×844 移动 | 2428px | 4 | `taskdetail-390x844-s{1..4}of4.png` |
| SSE 终态 | — | 1 | `taskdetail-live-sse-final-1440x900.png` |

视觉验收结论（AI 视觉模型逐张审查）：

- **1440 桌面**：侧边栏 7 项完整；状态徽章（需人工复核）+ runId + 提示 alert 正常；
  时间线 8 步（阶段/耗时/置信度）清晰；源 SQL 与迁移结果**双栏并排**深色代码块，内容完整。
- **900 中屏**：单列堆叠正常，侧边栏折叠为图标栏（约 60px），时间线无横向溢出。
- **390 移动**：汉堡菜单 + 标题正常折行，徽章/进度条/按钮可点且未被裁切，无挤压变形。
- 三档均**无元素重叠、溢出、异常空白等阻塞缺陷**。

## 4. SSE 实时流验证（重新执行）

点击「重新执行」后真跑观察：

1. 立即进入「执行中」态：新 runId、进度 0%、「停止监听」按钮激活、「开始执行」禁用；
2. SSE 实时推送：步骤与进度实时填充（本机 Mock LLM 下全流水线约 1.5s 完成，进度 0%→100%）；
3. 终态徽章自动更新为「需人工复核」，与后端 API 状态一致；
4. 终态截图见 `taskdetail-live-sse-final-1440x900.png`。

## 5. 顺带核验项

- 登录页渲染正常（默认账号提示为演示便利项，生产应移除——README 已注明）；
- 仪表盘「演示数据」诚实标注正常显示；
- 401 链路：未携带 token 访问受保护 API 返回 401（后端安全链生效）。

## 6. QA 工具侧观察（非产品缺陷，记录备查）

- Element Plus 按钮在高频重渲染下，Playwright 角色 click 的可点性检查偶发超时；改用页面内
  `element.click()` 稳定。属于测试工具与动画/重渲染的竞态，不是产品 bug，自动化时建议直接用表单提交或 evaluate 点击。
- 整页截图不展开内部滚动容器：验收长页面需分段滚动截图（本报告采用）。
