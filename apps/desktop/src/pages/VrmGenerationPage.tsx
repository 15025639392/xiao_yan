import { useEffect, useState } from "react";

import {
  cancelVrmGenerationJob,
  createVrmGenerationJob,
  fetchVrmGenerationJob,
  listVrmGenerationJobs,
  type VrmGenerationJob,
} from "../lib/apiVrmGeneration";
import { loadAvatarPreviewModel } from "../components/avatar/avatarPreviewModel";

type VrmGenerationPageProps = {
  assistantName: string;
  pollIntervalMs?: number;
};

const DEFAULT_PROMPT = "小晏，温柔，浅棕短发，蓝眼睛，白色居家裙";
const FINAL_STATUSES = new Set(["completed", "failed", "cancelled"]);

export function VrmGenerationPage({ assistantName, pollIntervalMs = 1200 }: VrmGenerationPageProps) {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [job, setJob] = useState<VrmGenerationJob | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewMessage, setPreviewMessage] = useState<string | null>(null);
  const [recentJobs, setRecentJobs] = useState<VrmGenerationJob[]>([]);
  const [recentError, setRecentError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    void listVrmGenerationJobs({ limit: 5 })
      .then((payload) => {
        if (isMounted) {
          setRecentJobs(payload.items);
          setRecentError(null);
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          setRecentError(err instanceof Error ? err.message : "最近任务读取失败");
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!job || FINAL_STATUSES.has(job.status)) return;

    const timer = window.setInterval(() => {
      void fetchVrmGenerationJob(job.job_id)
        .then((nextJob) => {
          setJob(nextJob);
          if (FINAL_STATUSES.has(nextJob.status)) {
            window.clearInterval(timer);
          }
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "任务状态获取失败");
          window.clearInterval(timer);
        });
    }, pollIntervalMs);

    return () => window.clearInterval(timer);
  }, [job, pollIntervalMs]);

  async function handleSubmit() {
    const nextPrompt = prompt.trim();
    if (!nextPrompt) {
      setError("请先描述想生成的形象。");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      const created = await createVrmGenerationJob({ prompt: nextPrompt });
      setJob(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建 VRM 生成任务失败");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCancel() {
    if (!job || FINAL_STATUSES.has(job.status)) return;
    setError(null);
    try {
      setJob(await cancelVrmGenerationJob(job.job_id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "取消任务失败");
    }
  }

  async function handleLoadPreview() {
    const outputPath = job?.artifacts.output_vrm_path;
    if (!outputPath) return;
    setError(null);
    setPreviewMessage(null);
    try {
      await loadAvatarPreviewModel(outputPath);
      setPreviewMessage("已加载到预览窗口，未替换正式形象。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载预览模型失败");
    }
  }

  return (
    <section className="vrm-generation-page" aria-labelledby="vrm-generation-title">
      <header className="vrm-generation-page__header">
        <p className="vrm-generation-page__eyebrow">VRM 形象草稿</p>
        <h1 id="vrm-generation-title">为{assistantName}生成外显模型</h1>
        <p className="vrm-generation-page__description">
          通过对话描述生成可审计的 VRM 草稿。当前产物默认是草稿版本，不会自动替换正式形象。
        </p>
      </header>

      <div className="vrm-generation-page__grid">
        <form
          className="vrm-generation-card"
          onSubmit={(event) => {
            event.preventDefault();
            void handleSubmit();
          }}
        >
          <label className="vrm-generation-field" htmlFor="vrm-generation-prompt">
            <span>形象描述</span>
            <textarea
              id="vrm-generation-prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              rows={6}
              placeholder="例如：小晏，浅棕短发，蓝眼睛，白色居家裙"
            />
          </label>
          <p className="vrm-generation-page__hint">
            建议描述发型、眼睛、服装和气质；复杂建模会在后续资产库阶段逐步增强。
          </p>
          <div className="vrm-generation-page__actions">
            <button className="vrm-generation-primary" type="submit" disabled={isSubmitting}>
              {isSubmitting ? "创建中..." : "生成 VRM 草稿"}
            </button>
            <button
              className="vrm-generation-secondary"
              type="button"
              disabled={!job || FINAL_STATUSES.has(job.status)}
              onClick={() => void handleCancel()}
            >
              取消任务
            </button>
          </div>
        </form>

        <aside className="vrm-generation-card" aria-label="生成状态">
          <h2>生成状态</h2>
          {job ? <JobSummary job={job} onLoadPreview={() => void handleLoadPreview()} /> : <p className="vrm-generation-page__empty">尚未创建任务。</p>}
          {previewMessage ? <p className="vrm-generation-page__success">{previewMessage}</p> : null}
          {error ? <p className="vrm-generation-page__error">{error}</p> : null}
        </aside>
      </div>
      <section className="vrm-generation-card vrm-generation-page__recent" aria-labelledby="vrm-generation-recent-title">
        <h2 id="vrm-generation-recent-title">最近生成</h2>
        <RecentJobs jobs={recentJobs} />
        {recentError ? <p className="vrm-generation-page__hint">最近任务暂时不可用：{recentError}</p> : null}
      </section>
    </section>
  );
}

function RecentJobs({ jobs }: { jobs: VrmGenerationJob[] }) {
  if (jobs.length === 0) {
    return <p className="vrm-generation-page__empty">还没有可恢复的生成记录。</p>;
  }

  return (
    <ul className="vrm-generation-recent-list">
      {jobs.map((recentJob) => (
        <li key={recentJob.job_id}>
          <div>
            <strong>{recentJob.prompt}</strong>
            <span>{recentJob.status}</span>
          </div>
          {recentJob.artifacts.output_vrm_path ? <p>{recentJob.artifacts.output_vrm_path}</p> : null}
        </li>
      ))}
    </ul>
  );
}

function JobSummary({ job, onLoadPreview }: { job: VrmGenerationJob; onLoadPreview: () => void }) {
  return (
    <dl className="vrm-generation-job">
      <div>
        <dt>状态</dt>
        <dd>{job.status}</dd>
      </div>
      <div>
        <dt>任务 ID</dt>
        <dd>{job.job_id}</dd>
      </div>
      {job.artifacts.output_vrm_path ? (
        <div>
          <dt>VRM 产物</dt>
          <dd>{job.artifacts.output_vrm_path}</dd>
        </div>
      ) : null}
      {job.artifacts.spec_path ? (
        <div>
          <dt>规格文件</dt>
          <dd>{job.artifacts.spec_path}</dd>
        </div>
      ) : null}
      {job.error_message ? (
        <div>
          <dt>错误</dt>
          <dd>{job.error_message}</dd>
        </div>
      ) : null}
      {job.status === "completed" && job.artifacts.output_vrm_path ? (
        <div>
          <dt>预览</dt>
          <dd>
            <button className="vrm-generation-secondary" type="button" onClick={onLoadPreview}>
              加载为当前预览模型
            </button>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}
