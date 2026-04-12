import { useState } from "react";
import { MarkdownMessage } from "../MarkdownMessage";
import type {
  OrchestratorMessage,
  OrchestratorMessageBlock,
  OrchestratorSession,
  OrchestratorTask,
  OrchestratorVerification,
} from "../../lib/api";

type OrchestratorMessageRendererProps = {
  message: OrchestratorMessage;
  session: OrchestratorSession;
  onApprovePlan: (sessionId: string) => Promise<void>;
  onRejectPlan: (sessionId: string) => Promise<void>;
  onResumeSession: (sessionId: string) => Promise<void>;
  onCancelSession: (sessionId: string) => Promise<void>;
  onActivateSession: (sessionId: string) => Promise<void>;
  onSendQuickMessage: (message: string) => Promise<void> | void;
};

export function OrchestratorMessageRenderer({
  message,
  session,
  onApprovePlan,
  onRejectPlan,
  onResumeSession,
  onCancelSession,
  onActivateSession,
  onSendQuickMessage,
}: OrchestratorMessageRendererProps) {
  const markdownBlocks = message.blocks.filter((block) => block.type === "markdown");
  const cardBlocks = message.blocks.filter((block) => block.type !== "markdown");
  const text = markdownBlocks.map((block) => block.text ?? "").join("\n\n").trim();

  return (
    <article
      className={`chat-message chat-message--${message.role} ${message.role === "system" ? "orchestrator-chat-message--system" : ""}`}
    >
      <div className="chat-message__bubble orchestrator-chat-message__bubble">
        {text ? (
          message.role === "user" ? (
            <p className="chat-message__content">{text}</p>
          ) : (
            <div className="chat-message__markdown">
              <MarkdownMessage content={message.state === "streaming" ? `${text}▍` : text} />
            </div>
          )
        ) : null}

        {cardBlocks.map((block, index) => (
          <OrchestratorBlockCard
            key={`${message.message_id}-${block.type}-${index}`}
            block={block}
            session={session}
            onApprovePlan={onApprovePlan}
            onRejectPlan={onRejectPlan}
            onResumeSession={onResumeSession}
            onCancelSession={onCancelSession}
            onActivateSession={onActivateSession}
            onSendQuickMessage={onSendQuickMessage}
          />
        ))}
      </div>
    </article>
  );
}

type OrchestratorBlockCardProps = {
  block: OrchestratorMessageBlock;
  session: OrchestratorSession;
  onApprovePlan: (sessionId: string) => Promise<void>;
  onRejectPlan: (sessionId: string) => Promise<void>;
  onResumeSession: (sessionId: string) => Promise<void>;
  onCancelSession: (sessionId: string) => Promise<void>;
  onActivateSession: (sessionId: string) => Promise<void>;
  onSendQuickMessage: (message: string) => Promise<void> | void;
};

function OrchestratorBlockCard(props: OrchestratorBlockCardProps) {
  const { block } = props;

  if (block.type === "plan_card" && block.plan) {
    return <PlanCard plan={block.plan} />;
  }
  if (block.type === "approval_card") {
    return <ApprovalCard {...props} />;
  }
  if (block.type === "task_card" && block.task) {
    return <TaskCard task={block.task} session={props.session} onResumeSession={props.onResumeSession} onSendQuickMessage={props.onSendQuickMessage} />;
  }
  if (block.type === "verification_card" && block.verification) {
    return <VerificationCard verification={block.verification} session={props.session} onResumeSession={props.onResumeSession} onSendQuickMessage={props.onSendQuickMessage} />;
  }
  if (block.type === "summary_card") {
    return (
      <section className="orchestrator-inline-card">
        <div className="orchestrator-inline-card__label">最终摘要</div>
        <p>{block.summary || "暂无摘要"}</p>
      </section>
    );
  }
  if (block.type === "directive_card") {
    return (
      <section className="orchestrator-inline-card">
        <div className="orchestrator-inline-card__label">边界更新</div>
        <p>{block.summary || "已更新主控边界。"}</p>
      </section>
    );
  }
  if (block.type === "next_action_card") {
    return <NextActionCard block={block} onSendQuickMessage={props.onSendQuickMessage} />;
  }
  if (block.type === "stall_followup_card") {
    return <StallFollowupCard block={block} onSendQuickMessage={props.onSendQuickMessage} />;
  }
  if (block.type === "session_status_card") {
    const statusSession = block.session ?? props.session;
    const primaryAction =
      statusSession.status === "failed" || statusSession.status === "cancelled"
        ? (
          <AsyncActionButton
            className="chat-page__action-btn"
            label={statusSession.coordination?.failure_category === "verification_failure" ? "重跑验收阶段" : "恢复推进"}
            pendingLabel="处理中..."
            onAction={() => props.onResumeSession(statusSession.session_id)}
          />
        )
        : statusSession.coordination?.preempted_by_session_id
          ? (
            <AsyncActionButton
              className="chat-page__action-btn"
              label="查看抢占会话"
              pendingLabel="切换中..."
              onAction={() =>
                props.onActivateSession(statusSession.coordination?.preempted_by_session_id || statusSession.session_id)
              }
            />
          )
          : statusSession.status === "pending_plan_approval"
            ? (
              <AsyncActionButton
                className="chat-page__action-btn"
                label="解释这份计划"
                pendingLabel="发送中..."
                onAction={() => props.onSendQuickMessage("先解释一下这份计划为什么这么拆")}
              />
            )
            : null;

    return (
      <section className="orchestrator-inline-card">
        <div className="orchestrator-inline-card__label">会话状态</div>
        <div className="orchestrator-inline-card__pills">
          <span className={`orchestrator-pill orchestrator-pill--${statusSession.status}`}>{renderSessionStatus(statusSession.status)}</span>
          {statusSession.coordination?.queue_position ? (
            <span className="orchestrator-pill">队列 #{statusSession.coordination.queue_position}</span>
          ) : null}
        </div>
        <p>{block.summary || statusSession.coordination?.waiting_reason || "主控会话正在等待下一步。"}</p>
        {primaryAction ? <div className="orchestrator-inline-card__actions">{primaryAction}</div> : null}
      </section>
    );
  }

  return null;
}

function AsyncActionButton({
  className,
  label,
  pendingLabel = "处理中...",
  onAction,
}: {
  className: string;
  label: string;
  pendingLabel?: string;
  onAction: () => Promise<void> | void;
}) {
  const [pending, setPending] = useState(false);

  async function handleClick() {
    if (pending) {
      return;
    }

    setPending(true);
    try {
      await Promise.resolve(onAction());
    } finally {
      setPending(false);
    }
  }

  return (
    <button className={className} type="button" disabled={pending} onClick={() => void handleClick()}>
      {pending ? pendingLabel : label}
    </button>
  );
}

function PlanCard({ plan }: { plan: NonNullable<OrchestratorMessageBlock["plan"]> }) {
  const [showDetails, setShowDetails] = useState(false);
  const primaryDefinition = plan.definition_of_done[0] ?? null;
  const hiddenDefinitionCount = Math.max(0, plan.definition_of_done.length - (primaryDefinition ? 1 : 0));
  const hasExpandableDetails = hiddenDefinitionCount > 0 || plan.tasks.length > 0 || plan.constraints.length > 0;

  return (
    <section className="orchestrator-inline-card">
      <div className="orchestrator-inline-card__label">执行计划</div>
      <strong>{plan.objective}</strong>
      {primaryDefinition ? <p>关键验收: {primaryDefinition}</p> : null}
      <div className="orchestrator-inline-card__pills">
        <span className="orchestrator-pill">任务 {plan.tasks.length}</span>
        {plan.constraints.length > 0 ? <span className="orchestrator-pill">约束 {plan.constraints.length}</span> : null}
      </div>
      {hasExpandableDetails ? (
        <button
          className="chat-page__action-btn orchestrator-inline-card__toggle"
          type="button"
          onClick={() => setShowDetails((current) => !current)}
        >
          {showDetails ? "收起完整计划" : "查看完整计划"}
        </button>
      ) : null}
      {showDetails ? (
        <>
          {plan.constraints.length > 0 ? (
            <div className="orchestrator-inline-card__details">
              <span>约束条件</span>
              <ul>
                {plan.constraints.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {plan.definition_of_done.length > 0 ? (
            <div className="orchestrator-inline-card__details">
              <span>Definition of done</span>
              <ul>
                {plan.definition_of_done.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {plan.tasks.length > 0 ? (
            <div className="orchestrator-inline-card__details">
              <span>任务拆解</span>
              <ol>
                {plan.tasks.map((task) => (
                  <li key={task.task_id}>
                    {task.kind.toUpperCase()} · {task.title}
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function ApprovalCard({
  session,
  onApprovePlan,
  onRejectPlan,
}: OrchestratorBlockCardProps) {
  const pending = session.status === "pending_plan_approval";
  const [showMoreActions, setShowMoreActions] = useState(false);

  const moreActionId = `approval-more-${session.session_id}`;

  return (
    <section className="orchestrator-inline-card">
      <div className="orchestrator-inline-card__label">待审批</div>
      <p>{pending ? "当前计划等待你批准后开工。" : "当前没有待审批事项。"}</p>
      {pending ? (
        <>
          <div className="orchestrator-inline-card__actions">
            <AsyncActionButton
              className="btn btn--primary btn--sm"
              label="批准并开工"
              pendingLabel="批准中..."
              onAction={() => onApprovePlan(session.session_id)}
            />
            <button
              type="button"
              className="chat-page__action-btn orchestrator-inline-card__toggle"
              aria-expanded={showMoreActions}
              aria-controls={moreActionId}
              onClick={() => setShowMoreActions((current) => !current)}
            >
              {showMoreActions ? "收起更多操作" : "更多操作"}
            </button>
          </div>
          {showMoreActions ? (
            <div id={moreActionId} className="orchestrator-inline-card__details">
              <AsyncActionButton
                className="btn btn--secondary btn--sm"
                label="拒绝计划"
                pendingLabel="拒绝中..."
                onAction={() => onRejectPlan(session.session_id)}
              />
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function TaskCard({
  task,
  session,
  onResumeSession,
  onSendQuickMessage,
}: {
  task: OrchestratorTask;
  session: OrchestratorSession;
  onResumeSession: (sessionId: string) => Promise<void>;
  onSendQuickMessage: (message: string) => Promise<void> | void;
}) {
  const [showDetails, setShowDetails] = useState(false);
  const engineerLabel = resolveEngineerLabel(task);
  const detailRows: string[] = [];
  if (engineerLabel) {
    detailRows.push(`执行人: ${engineerLabel}`);
  }
  if (task.delegate_run_id) {
    detailRows.push(`run: ${task.delegate_run_id.slice(0, 12)}`);
  }
  if (task.scope_paths.length > 0) {
    detailRows.push(`Scope: ${task.scope_paths.join(" · ")}`);
  }
  if (task.acceptance_commands.length > 0) {
    detailRows.push(`验收: ${task.acceptance_commands.join(" | ")}`);
  }
  const hasDetails = detailRows.length > 0;

  return (
    <section className="orchestrator-inline-card">
      <div className="orchestrator-inline-card__label">任务状态</div>
      <div className="orchestrator-inline-card__pills">
        <span className={`orchestrator-pill orchestrator-pill--${task.status}`}>{renderTaskStatus(task.status)}</span>
        <span className="orchestrator-pill">{task.kind.toUpperCase()}</span>
      </div>
      <strong>{task.title}</strong>
      <p>{task.result_summary || task.error || "等待进一步推进。"}</p>
      {hasDetails ? (
        <>
          <button
            className="chat-page__action-btn orchestrator-inline-card__toggle"
            type="button"
            onClick={() => setShowDetails((current) => !current)}
          >
            {showDetails ? "收起详情" : "查看详情"}
          </button>
          {showDetails ? (
            <ul className="orchestrator-inline-card__details">
              {detailRows.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
      <div className="orchestrator-inline-card__actions">
        {task.status === "failed" ? (
          <AsyncActionButton
            className="chat-page__action-btn"
            label={session.coordination?.failure_category === "verification_failure" ? "重跑验收阶段" : "重派失败环节"}
            pendingLabel="处理中..."
            onAction={() => onResumeSession(session.session_id)}
          />
        ) : null}
        {task.status === "running" ? (
          <AsyncActionButton
            className="chat-page__action-btn"
            label="查看当前推进"
            pendingLabel="发送中..."
            onAction={() => onSendQuickMessage(`解释一下任务「${task.title}」现在推进到哪一步`)}
          />
        ) : null}
        {(task.status === "pending" || task.status === "queued") ? (
          <AsyncActionButton
            className="chat-page__action-btn"
            label="推进这个任务"
            pendingLabel="发送中..."
            onAction={() => onSendQuickMessage(`继续推进任务「${task.title}」，并告诉我你准备怎么做`)}
          />
        ) : null}
      </div>
    </section>
  );
}

function VerificationCard({
  verification,
  session,
  onResumeSession,
  onSendQuickMessage,
}: {
  verification: OrchestratorVerification;
  session: OrchestratorSession;
  onResumeSession: (sessionId: string) => Promise<void>;
  onSendQuickMessage: (message: string) => Promise<void> | void;
}) {
  return (
    <section className="orchestrator-inline-card">
      <div className="orchestrator-inline-card__label">统一验收</div>
      <div className="orchestrator-inline-card__pills">
        <span className={`orchestrator-pill ${verification.passed ? "orchestrator-pill--succeeded" : "orchestrator-pill--failed"}`}>
          {verification.passed ? "PASSED" : "FAILED"}
        </span>
      </div>
      <p>{verification.summary || "暂无验收摘要"}</p>
      {verification.commands.length > 0 ? <VerificationDetails commands={verification.commands} /> : null}
      <div className="orchestrator-inline-card__actions">
        {!verification.passed ? (
          <AsyncActionButton
            className="chat-page__action-btn"
            label="重跑验收阶段"
            pendingLabel="处理中..."
            onAction={() => onResumeSession(session.session_id)}
          />
        ) : (
          <AsyncActionButton
            className="chat-page__action-btn"
            label="总结交付结果"
            pendingLabel="发送中..."
            onAction={() => onSendQuickMessage("总结一下这次主控交付的关键改动和验收结果")}
          />
        )}
      </div>
    </section>
  );
}

function NextActionCard({
  block,
  onSendQuickMessage,
}: {
  block: OrchestratorMessageBlock;
  onSendQuickMessage: (message: string) => Promise<void> | void;
}) {
  const suggestionItems = Array.isArray(block.details?.suggestions)
    ? block.details.suggestions
      .map((item) => {
        if (item == null || typeof item !== "object") {
          return null;
        }
        const candidate = item as Record<string, unknown>;
        const command = typeof candidate.command === "string" ? candidate.command.trim() : "";
        if (!command) {
          return null;
        }
        const priority = candidate.priority === "recommended" ? "recommended" : "alternative";
        const reason = typeof candidate.reason === "string" ? candidate.reason.trim() : "";
        const confidenceValue = typeof candidate.confidence === "number" ? candidate.confidence : null;
        const confidence =
          confidenceValue == null
            ? null
            : Math.min(1, Math.max(0, confidenceValue));
        return {
          command,
          priority,
          reason,
          confidence,
        };
      })
      .filter((item): item is { command: string; priority: "recommended" | "alternative"; reason: string; confidence: number | null } => item !== null)
    : [];
  const queueLine = typeof block.details?.queue_line === "string" ? block.details.queue_line : "";
  const nextAction = typeof block.details?.next_action === "string" ? block.details.next_action : "";
  const suggestedCommand = typeof block.details?.suggested_command === "string" ? block.details.suggested_command : "";
  const suggestedCommands = Array.isArray(block.details?.suggested_commands)
    ? block.details.suggested_commands.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
  const commandOptions = suggestionItems.length > 0
    ? suggestionItems
    : (
      suggestedCommands.length > 0
        ? suggestedCommands.map((command, index) => ({
          command,
          priority: index === 0 ? "recommended" : "alternative",
          reason: "",
          confidence: null,
        }))
        : (suggestedCommand
            ? [{ command: suggestedCommand, priority: "recommended", reason: "", confidence: null }]
            : [])
    );

  const primaryOption = commandOptions.find((item) => item.priority === "recommended") ?? commandOptions[0] ?? null;
  const summaryLine = block.summary || nextAction || queueLine || "主控已生成下一步建议。";

  return (
    <section className="orchestrator-inline-card orchestrator-next-action-card">
      <div className="orchestrator-inline-card__label">下一步建议</div>
      <p>{summaryLine}</p>
      {primaryOption ? (
        <div className="orchestrator-next-action-card__group">
          <code className="orchestrator-task__runid">{primaryOption.command}</code>
          <AsyncActionButton
            className="chat-page__action-btn"
            label={`执行建议`}
            pendingLabel="发送中..."
            onAction={() => onSendQuickMessage(primaryOption.command)}
          />
        </div>
      ) : null}
    </section>
  );
}

function StallFollowupCard({
  block,
  onSendQuickMessage,
}: {
  block: OrchestratorMessageBlock;
  onSendQuickMessage: (message: string) => Promise<void> | void;
}) {
  const managerSummary = typeof block.details?.manager_summary === "string"
    ? block.details.manager_summary
    : (block.summary || "主控检测到任务卡点，已发起追问。");
  const engineerPrompt = typeof block.details?.engineer_prompt === "string" ? block.details.engineer_prompt : "";
  const hasLevelDetail = typeof block.details?.level === "string";
  const level = typeof block.details?.level === "string" ? block.details.level : "soft_ping";
  const elapsedMinutes = typeof block.details?.elapsed_minutes === "number" ? block.details.elapsed_minutes : null;
  const suggestions = Array.isArray(block.details?.suggestions)
    ? block.details.suggestions.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
  const followupCommand = typeof block.details?.followup_command === "string" ? block.details.followup_command.trim() : "";
  const [showDetails, setShowDetails] = useState(false);
  const hasDetails = hasLevelDetail || elapsedMinutes != null || engineerPrompt || suggestions.length > 0;

  return (
    <section className="orchestrator-inline-card orchestrator-stall-followup-card">
      <div className="orchestrator-inline-card__label">主控介入追问</div>
      <p>{managerSummary}</p>
      {followupCommand ? (
        <div className="orchestrator-inline-card__actions">
          <AsyncActionButton
            className="chat-page__action-btn"
            label="立即追问工程师"
            pendingLabel="发送中..."
            onAction={() => onSendQuickMessage(followupCommand)}
          />
        </div>
      ) : null}
      {hasDetails ? (
        <>
          <button
            className="chat-page__action-btn orchestrator-inline-card__toggle"
            type="button"
            onClick={() => setShowDetails((current) => !current)}
          >
            {showDetails ? "收起介入细节" : "查看介入细节"}
          </button>
          {showDetails ? (
            <div className="orchestrator-inline-card__details">
              {hasLevelDetail ? <p>介入级别: {renderStallLevel(level)}</p> : null}
              {elapsedMinutes != null ? <p>已运行时长: 约 {Math.max(1, Math.floor(elapsedMinutes / 60))} 小时</p> : null}
              {engineerPrompt ? <p>追问话术: {engineerPrompt}</p> : null}
              {suggestions.length > 0 ? (
                <ul>
                  {suggestions.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function VerificationDetails({ commands }: { commands: string[] }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        className="chat-page__action-btn orchestrator-inline-card__toggle"
        type="button"
        onClick={() => setOpen((current) => !current)}
      >
        {open ? "收起验收命令" : "查看验收命令"}
      </button>
      {open ? (
        <ul className="orchestrator-command-list">
          {commands.map((command) => (
            <li key={command}>
              <code>{command}</code>
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}

function renderSessionStatus(status: OrchestratorSession["status"]): string {
  if (status === "pending_plan_approval") return "待审批";
  if (status === "dispatching") return "待派发";
  if (status === "running") return "运行中";
  if (status === "verifying") return "验收中";
  if (status === "completed") return "已完成";
  if (status === "failed") return "失败";
  if (status === "cancelled") return "已取消";
  if (status === "planning") return "规划中";
  return "草稿";
}

function renderTaskStatus(status: OrchestratorTask["status"]): string {
  if (status === "pending") return "待执行";
  if (status === "queued") return "排队中";
  if (status === "running") return "运行中";
  if (status === "succeeded") return "已完成";
  if (status === "failed") return "失败";
  return "已取消";
}

function resolveEngineerLabel(task: OrchestratorTask): string | null {
  if (typeof task.engineer_label === "string" && task.engineer_label.trim().length > 0) {
    return task.engineer_label.trim();
  }
  if (typeof task.engineer_id === "number" && task.engineer_id > 0) {
    return `工程师${task.engineer_id}号(codex)`;
  }
  return null;
}

function renderStallLevel(level: string): string {
  if (level === "hard_intervention") return "硬介入";
  if (level === "manual_followup") return "手动追问";
  return "软追问";
}
