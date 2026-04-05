# 桌面端控制台 UI 重做实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将桌面端界面重做为全中文的控制台式工作台，重构信息层级、视觉系统和主要交互语义，同时保持现有接口与行为不变。

**Architecture:** 保留现有 React 组件边界，以 `App.tsx` 重组页面骨架，用各面板组件分别承接中文语义和控制台布局，再用 `index.css` 建立新的设计 token、分层卡片体系和桌面优先响应式规则。当前工作区已存在未提交的桌面端改动，执行前必须先阅读目标文件差异并在实现中合并，不能直接覆盖。

**Tech Stack:** React 18、TypeScript、Vite、Vitest、Testing Library、纯 CSS

---

### Task 1: 重建页面骨架与中文指挥栏

**Files:**
- Modify: `apps/desktop/src/App.tsx`
- Modify: `apps/desktop/src/App.test.tsx`
- Modify: `apps/desktop/src/index.css`

**Step 1: 写失败测试**

在 `apps/desktop/src/App.test.tsx` 新增或改写断言，要求首页出现以下中文结构：

```tsx
expect(screen.getByRole("button", { name: "唤醒" })).toBeInTheDocument();
expect(screen.getByRole("button", { name: "休眠" })).toBeInTheDocument();
expect(screen.getByText("指挥台")).toBeInTheDocument();
expect(screen.getByText("对话控制台")).toBeInTheDocument();
expect(screen.getByText("目标看板")).toBeInTheDocument();
```

**Step 2: 运行测试并确认失败**

Run: `npm test -- --run src/App.test.tsx`
Expected: FAIL，因为当前页面仍使用英文按钮和未更新的结构标题。

**Step 3: 写最小实现**

在 `apps/desktop/src/App.tsx` 中重组页面骨架，形成：

```tsx
<main className="console-shell">
  <section className="command-deck">
    <header className="command-deck__headline">
      <p className="section-kicker">数字人控制台</p>
      <h1>指挥台</h1>
    </header>
    <div className="command-deck__actions">
      <button type="button">唤醒</button>
      <button type="button">休眠</button>
    </div>
  </section>
  <section className="workspace-grid">...</section>
  <section className="mission-board">...</section>
</main>
```

同时在 `apps/desktop/src/index.css` 中补上 `console-shell`、`command-deck`、`workspace-grid`、`mission-board` 的最小布局样式，先保证结构成立。

**Step 4: 运行测试并确认通过**

Run: `npm test -- --run src/App.test.tsx`
Expected: PASS，首页测试使用全中文结构通过。

**Step 5: 提交**

```bash
git add apps/desktop/src/App.tsx apps/desktop/src/App.test.tsx apps/desktop/src/index.css
git commit -m "feat: 重构桌面端控制台骨架"
```

### Task 2: 重做对话控制台

**Files:**
- Modify: `apps/desktop/src/components/ChatPanel.tsx`
- Create: `apps/desktop/src/components/ChatPanel.test.tsx`
- Modify: `apps/desktop/src/index.css`

**Step 1: 写失败测试**

新建 `apps/desktop/src/components/ChatPanel.test.tsx`，覆盖中文标题、发送状态、消息身份标签：

```tsx
render(
  <ChatPanel
    draft="你好"
    isSending={false}
    messages={[
      { id: "1", role: "user", content: "你好" },
      { id: "2", role: "assistant", content: "我在。" },
    ]}
    onDraftChange={vi.fn()}
    onSend={vi.fn()}
  />,
);

expect(screen.getByText("对话控制台")).toBeInTheDocument();
expect(screen.getByText("你")).toBeInTheDocument();
expect(screen.getByText("小晏")).toBeInTheDocument();
expect(screen.getByRole("button", { name: "发送" })).toBeInTheDocument();
```

**Step 2: 运行测试并确认失败**

Run: `npm test -- --run src/components/ChatPanel.test.tsx`
Expected: FAIL，因为当前组件标题、按钮和消息前缀仍为旧文案。

**Step 3: 写最小实现**

在 `apps/desktop/src/components/ChatPanel.tsx` 中将结构调整为：

```tsx
<section className="panel panel--console">
  <div className="panel__header">
    <div>
      <p className="panel__eyebrow">实时交互</p>
      <h2 className="panel__title">对话控制台</h2>
    </div>
    <span className="mini-badge">{isSending ? "正在回复" : "在线中"}</span>
  </div>
  <div className="chat-thread">...</div>
  <div className="chat-composer">...</div>
</section>
```

消息气泡内使用独立标签显示 `你` / `小晏`，发送按钮统一为 `发送`，输入占位文案和发送状态全部改中文。同步更新 `apps/desktop/src/index.css` 的对话区样式。

**Step 4: 运行测试并确认通过**

Run: `npm test -- --run src/components/ChatPanel.test.tsx`
Expected: PASS，对话控制台的中文结构和按钮行为通过。

**Step 5: 提交**

```bash
git add apps/desktop/src/components/ChatPanel.tsx apps/desktop/src/components/ChatPanel.test.tsx apps/desktop/src/index.css
git commit -m "feat: 重做桌面端对话控制台"
```

### Task 3: 重做状态侧栏三张卡片

**Files:**
- Modify: `apps/desktop/src/components/StatusPanel.tsx`
- Modify: `apps/desktop/src/components/StatusPanel.test.tsx`
- Modify: `apps/desktop/src/components/WorldPanel.tsx`
- Modify: `apps/desktop/src/components/WorldPanel.test.tsx`
- Modify: `apps/desktop/src/components/AutobioPanel.tsx`
- Modify: `apps/desktop/src/components/AutobioPanel.test.tsx`
- Modify: `apps/desktop/src/index.css`

**Step 1: 写失败测试**

把现有三个面板测试改为中文语义断言，例如：

```tsx
expect(screen.getByText("当前状态")).toBeInTheDocument();
expect(screen.getByText("当前阶段")).toBeInTheDocument();
expect(screen.getByText("内在世界")).toBeInTheDocument();
expect(screen.getByText("自我叙事")).toBeInTheDocument();
expect(screen.getByText("当前专注目标")).toBeInTheDocument();
```

同时将世界状态和自我叙事的空状态改成中文断言。

**Step 2: 运行测试并确认失败**

Run: `npm test -- --run src/components/StatusPanel.test.tsx src/components/WorldPanel.test.tsx src/components/AutobioPanel.test.tsx`
Expected: FAIL，因为当前三个组件仍存在英文标题、英文字段标签和旧布局。

**Step 3: 写最小实现**

分别修改三个组件：

`apps/desktop/src/components/StatusPanel.tsx`

```tsx
<section className="panel panel--rail panel--status">
  <div className="panel__header">
    <div>
      <p className="panel__eyebrow">系统读数</p>
      <h2 className="panel__title">当前状态</h2>
    </div>
  </div>
  <dl className="metric-list">...</dl>
</section>
```

`apps/desktop/src/components/WorldPanel.tsx`

```tsx
<section className="panel panel--rail">
  <h2 className="panel__title">内在世界</h2>
  <dl className="world-metrics">...</dl>
</section>
```

`apps/desktop/src/components/AutobioPanel.tsx`

```tsx
<section className="panel panel--rail">
  <h2 className="panel__title">自我叙事</h2>
  {uniqueEntries.length === 0 ? <p>还没有形成自我叙事。</p> : ...}
</section>
```

把字段标签全部转换为中文语义，例如把英文阶段标签改成 `当前阶段`、把 `Focus Goal` 改成 `当前专注目标`、把 `Latest Event` 改成 `最近事件`，并在 `apps/desktop/src/index.css` 中补上侧栏卡片、指标列表、计划块和自我编程块样式。

**Step 4: 运行测试并确认通过**

Run: `npm test -- --run src/components/StatusPanel.test.tsx src/components/WorldPanel.test.tsx src/components/AutobioPanel.test.tsx`
Expected: PASS，侧栏三张卡片都完成中文化和新层级布局。

**Step 5: 提交**

```bash
git add apps/desktop/src/components/StatusPanel.tsx apps/desktop/src/components/StatusPanel.test.tsx apps/desktop/src/components/WorldPanel.tsx apps/desktop/src/components/WorldPanel.test.tsx apps/desktop/src/components/AutobioPanel.tsx apps/desktop/src/components/AutobioPanel.test.tsx apps/desktop/src/index.css
git commit -m "feat: 重做桌面端状态侧栏"
```

### Task 4: 重做目标看板

**Files:**
- Modify: `apps/desktop/src/components/GoalsPanel.tsx`
- Modify: `apps/desktop/src/components/GoalsPanel.test.tsx`
- Modify: `apps/desktop/src/index.css`

**Step 1: 写失败测试**

将 `apps/desktop/src/components/GoalsPanel.test.tsx` 改成中文语义断言，并补上看板分组断言：

```tsx
expect(screen.getByText("目标看板")).toBeInTheDocument();
expect(screen.getByText("目标链")).toBeInTheDocument();
expect(screen.getByText("独立目标")).toBeInTheDocument();
expect(screen.getByRole("button", { name: "暂停" })).toBeInTheDocument();
expect(screen.getByRole("button", { name: "完成" })).toBeInTheDocument();
```

**Step 2: 运行测试并确认失败**

Run: `npm test -- --run src/components/GoalsPanel.test.tsx`
Expected: FAIL，因为当前组件仍使用英文分组标题和按钮文案。

**Step 3: 写最小实现**

在 `apps/desktop/src/components/GoalsPanel.tsx` 中保留 `groupGoals` 逻辑，但改造成看板式结构：

```tsx
<section className="panel panel--board">
  <div className="panel__header">
    <div>
      <p className="panel__eyebrow">任务推进</p>
      <h2 className="panel__title">目标看板</h2>
    </div>
  </div>
  <section className="goal-group">
    <h3>目标链</h3>
    ...
  </section>
</section>
```

按钮文案改为 `暂停 / 恢复 / 完成 / 放弃`，链路摘要改写为中文可读语句，并在 `apps/desktop/src/index.css` 中增加时间轴、状态条和目标卡分组样式。

**Step 4: 运行测试并确认通过**

Run: `npm test -- --run src/components/GoalsPanel.test.tsx`
Expected: PASS，目标看板的中文结构和操作行为通过。

**Step 5: 提交**

```bash
git add apps/desktop/src/components/GoalsPanel.tsx apps/desktop/src/components/GoalsPanel.test.tsx apps/desktop/src/index.css
git commit -m "feat: 重做桌面端目标看板"
```

### Task 5: 完成控制台视觉系统并做全量验证

**Files:**
- Modify: `apps/desktop/src/index.css`
- Verify: `apps/desktop/src/App.test.tsx`
- Verify: `apps/desktop/src/components/StatusPanel.test.tsx`
- Verify: `apps/desktop/src/components/ChatPanel.test.tsx`
- Verify: `apps/desktop/src/components/GoalsPanel.test.tsx`
- Verify: `apps/desktop/src/components/WorldPanel.test.tsx`
- Verify: `apps/desktop/src/components/AutobioPanel.test.tsx`

**Step 1: 写失败测试**

补充一个整体验证点，确认控制台页面的关键中文区域在同一屏内成立：

```tsx
expect(screen.getByText("指挥台")).toBeInTheDocument();
expect(screen.getByText("对话控制台")).toBeInTheDocument();
expect(screen.getByText("当前状态")).toBeInTheDocument();
expect(screen.getByText("目标看板")).toBeInTheDocument();
```

如果前几步已经覆盖，可将这里视为“先运行全量测试并记录失败项”。

**Step 2: 运行测试并确认失败**

Run: `npm test -- --run src/App.test.tsx src/components/StatusPanel.test.tsx src/components/ChatPanel.test.tsx src/components/GoalsPanel.test.tsx src/components/WorldPanel.test.tsx src/components/AutobioPanel.test.tsx`
Expected: 若样式收尾前仍有文案或结构不一致，应出现 FAIL；否则进入样式收尾和人工检查。

**Step 3: 写最小实现**

在 `apps/desktop/src/index.css` 中完成控制台视觉系统：

```css
:root {
  --bg-canvas: #f4efe8;
  --bg-panel: rgba(255, 252, 247, 0.88);
  --text-strong: #201a17;
  --text-muted: #6d5b52;
  --accent-copper: #8b5e3c;
  --line-soft: rgba(64, 43, 30, 0.12);
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.9fr);
}

@media (max-width: 1024px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}
```

补齐桌面优先布局、侧栏折叠、卡片层级、标签、按钮、消息气泡和目标看板样式，并做一次浏览器人工检查，确认全中文、无横向滚动、主次分明。

**Step 4: 运行测试并确认通过**

Run: `npm test`
Expected: PASS，全部桌面端前端测试通过。

再运行：

Run: `npm run build`
Expected: PASS，Vite 构建成功且无类型错误。

**Step 5: 提交**

```bash
git add apps/desktop/src/index.css apps/desktop/src/App.tsx apps/desktop/src/App.test.tsx apps/desktop/src/components/ChatPanel.tsx apps/desktop/src/components/ChatPanel.test.tsx apps/desktop/src/components/StatusPanel.tsx apps/desktop/src/components/StatusPanel.test.tsx apps/desktop/src/components/WorldPanel.tsx apps/desktop/src/components/WorldPanel.test.tsx apps/desktop/src/components/AutobioPanel.tsx apps/desktop/src/components/AutobioPanel.test.tsx apps/desktop/src/components/GoalsPanel.tsx apps/desktop/src/components/GoalsPanel.test.tsx
git commit -m "feat: 完成桌面端控制台 UI 重做"
```
