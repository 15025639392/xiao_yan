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
  if (block.type === "session_status_card") {
    const statusSession = block.session ?? props.session;
    return (
      <section className="orchestrator-inline-card">
        <div className="orchestrator-inline-card__label">会话状态</div>
        <div className="orchestrator-inline-card__pills">
          <span className={`orchestrator-pill orchestrator-pill--${statusSession.status}`}>{renderSessionStatus(statusSession.status)}</span>
          <span className="orchestrator-pill">{statusSession.project_name}</span>
          {statusSession.coordination?.queue_position ? (
            <span className="orchestrator-pill">队列 #{statusSession.coordination.queue_position}</span>
          ) : null}
        </div>
        <p>{block.summary || statusSession.coordination?.waiting_reason || "主控会话正在等待下一步。"}</p>
        <div className="orchestrator-inline-card__actions">
          {statusSession.status === "failed" || statusSession.status === "cancelled" ? (
            <AsyncActionButton
              className="chat-page__action-btn"
              label={statusSession.coordination?.failure_category === "verification_failure" ? "重跑验收阶段" : "恢复推进"}
              pendingLabel="处理中..."
              onAction={() => props.onResumeSession(statusSession.session_id)}
            />
          ) : null}
          {statusSession.status === "pending_plan_approval" ? (
            <AsyncActionButton
              className="chat-page__action-btn"
              label="解释这份计划"
              pendingLabel="发送中..."
              onAction={() => props.onSendQuickMessage("先解释一下这份计划为什么这么拆")}
            />
          ) : null}
          {statusSession.coordination?.preempted_by_session_id ? (
            <AsyncActionButton
              className="chat-page__action-btn"
              label="查看抢占会话"
              pendingLabel="切换中..."
              onAction={() =>
                props.onActivateSession(statusSession.coordination?.preempted_by_session_id || statusSession.session_id)
              }
            />
          ) : null}
        </div>
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
  return (
    <section className="orchestrator-inline-card">
      <div className="orchestrator-inline-card__label">执行计划</div>
      <strong>{plan.objective}</strong>
      <div className="orchestrator-inline-card__section">
        <span>Definition of done</span>
        <ul>
          {plan.definition_of_done.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
      <div className="orchestrator-inline-card__section">
        <span>任务拆解</span>
        <ol>
          {plan.tasks.map((task) => (
            <li key={task.task_id}>
              {task.kind.toUpperCase()} · {task.title}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function ApprovalCard({
  session,
  onApprovePlan,
  onRejectPlan,
  onSendQuickMessage,
}: OrchestratorBlockCardProps) {
  const pending = session.status === "pending_plan_approval";
  return (
    <section className="orchestrator-inline-card">
      <div className="orchestrator-inline-card__label">待审批</div>
      <p>{pending ? "当前计划等待你批准后开工。" : "当前没有待审批事项。"}</p>
      {pending ? (
        <div className="orchestrator-inline-card__actions">
          <AsyncActionButton
            className="btn btn--primary btn--sm"
            label="批准并开工"
            pendingLabel="批准中..."
            onAction={() => onApprovePlan(session.session_id)}
          />
          <AsyncActionButton
            className="btn btn--secondary btn--sm"
            label="拒绝计划"
            pendingLabel="拒绝中..."
            onAction={() => onRejectPlan(session.session_id)}
          />
          <AsyncActionButton
            className="chat-page__action-btn"
            label="先解释计划"
            pendingLabel="发送中..."
            onAction={() => onSendQuickMessage("先解释一下这份计划为什么这么拆")}
          />
        </div>
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
  return (
    <section className="orchestrator-inline-card">
      <div className="orchestrator-inline-card__label">任务状态</div>
      <div className="orchestrator-inline-card__pills">
        <span className={`orchestrator-pill orchestrator-pill--${task.status}`}>{renderTaskStatus(task.status)}</span>
        <span className="orchestrator-pill">{task.kind.toUpperCase()}</span>
      </div>
      <strong>{task.title}</strong>
      <p>{task.result_summary || task.error || "等待进一步推进。"}</p>
      {task.scope_paths.length > 0 ? <p>Scope: {task.scope_paths.join(" · ")}</p> : null}
      {task.acceptance_commands.length > 0 ? <p>验收: {task.acceptance_commands.join(" | ")}</p> : null}
      {task.delegate_run_id ? <code className="orchestrator-task__runid">run: {task.delegate_run_id.slice(0, 12)}</code> : null}
      <div className="orchestrator-inline-card__actions">
        {task.status === "failed" ? (
          <>
            <AsyncActionButton
              className="chat-page__action-btn"
              label={session.coordination?.failure_category === "verification_failure" ? "重跑验收阶段" : "重派失败环节"}
              pendingLabel="处理中..."
              onAction={() => onResumeSession(session.session_id)}
            />
            <AsyncActionButton
              className="chat-page__action-btn"
              label="解释失败原因"
              pendingLabel="发送中..."
              onAction={() => onSendQuickMessage(`解释一下任务「${task.title}」为什么失败，以及下一步建议`)}
            />
          </>
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
      {verification.commands.length > 0 ? (
        <ul className="orchestrator-command-list">
          {verification.commands.map((command) => (
            <li key={command}>
              <code>{command}</code>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="orchestrator-inline-card__actions">
        {!verification.passed ? (
          <>
            <AsyncActionButton
              className="chat-page__action-btn"
              label="重跑验收阶段"
              pendingLabel="处理中..."
              onAction={() => onResumeSession(session.session_id)}
            />
            <AsyncActionButton
              className="chat-page__action-btn"
              label="解释验收失败"
              pendingLabel="发送中..."
              onAction={() => onSendQuickMessage("解释一下这次统一验收为什么失败，以及最小修复路径")}
            />
          </>
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
