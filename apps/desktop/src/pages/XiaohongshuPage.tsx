import { useState } from "react";

import {
  autofillXiaohongshuPublishDraft,
  publishXiaohongshuViaMcp,
  autofillXiaohongshuTextImageCards,
  captureXiaohongshuCreatorHome,
  captureXiaohongshuLeadSignals,
  previewXiaohongshuCreatorHome,
  type XiaohongshuPublishAutofillResponse,
  type XiaohongshuCreatorPreviewItem,
  type XiaohongshuLeadCaptureResponse,
  type XiaohongshuPublishViaMcpResponse,
  type XiaohongshuTextImageAutofillResponse,
} from "../lib/api";
import { Button, Panel } from "../components/ui";
import {
  buildPublishDraft,
  buildPublishChecklist,
  buildLeadCaptureTemplate,
  buildLeadFollowUpPacket,
  buildImageCardDraft,
  extractCreatorHomeSnapshot,
  parseImagePaths,
  parseActivities,
  parseTopics,
  type XiaohongshuImageCardDraft,
  type XiaohongshuLeadCaptureTemplate,
  type XiaohongshuLeadFollowUpPacket,
  type XiaohongshuPublishChecklist,
  type XiaohongshuPublishDraft,
} from "./xiaohongshuPageHelpers";
import { buildLeadReplyPlan, type XiaohongshuLeadReplyPlan } from "./xiaohongshuLeadReplyHelpers";
import { XiaohongshuDraftCard } from "./XiaohongshuDraftCard";
import { XiaohongshuOpportunityPanel } from "./XiaohongshuOpportunityPanel";

type XiaohongshuPageProps = {
  assistantName: string;
};

const DEFAULT_ACCOUNT_NAME = "小红薯66661C17";
const DEFAULT_TOPICS = [
  "#高颜值巧克力 | 30万人参与 | 14.4亿次浏览",
  "#早餐吃什么 | 288.7万人参与 | 105.3亿次浏览",
  "#面条的花式做法 | 30.3万人参与 | 29.8亿次浏览",
].join("\n");
const DEFAULT_ACTIVITIES = [
  "RED新生代创作大赛 | 03-30 至 05-10 | 官方活动, 奖励多多",
  "我的时尚缪斯 | 04-19 至 05-31 | 官方活动, 奖励多多",
  "春天见面会 | 04-18 至 04-30 | 官方活动, 奖励多多",
].join("\n");
const DEFAULT_MESSAGE =
  "请围绕冷启动起号和后续成交经营，生成适合人工确认后发布的小红书笔记草稿。";
const DEFAULT_RAW_SNAPSHOT = [
  "创作话题",
  "#高颜值巧克力",
  "30万人参与，14.4亿次浏览",
  "#早餐吃什么",
  "288.7万人参与，105.3亿次浏览",
  "#面条的花式做法",
  "30.3万人参与，29.8亿次浏览",
  "热门活动",
  "官方活动, 奖励多多",
  "RED新生代创作大赛 03-30 至 05-10",
  "我的时尚缪斯 04-19 至 05-31",
  "春天见面会 04-18 至 04-30",
].join("\n");

export function XiaohongshuPage({ assistantName }: XiaohongshuPageProps) {
  const [accountName, setAccountName] = useState(DEFAULT_ACCOUNT_NAME);
  const [topicsText, setTopicsText] = useState(DEFAULT_TOPICS);
  const [activitiesText, setActivitiesText] = useState(DEFAULT_ACTIVITIES);
  const [rawSnapshotText, setRawSnapshotText] = useState(DEFAULT_RAW_SNAPSHOT);
  const [message, setMessage] = useState(DEFAULT_MESSAGE);
  const [loading, setLoading] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [autofillingIndex, setAutofillingIndex] = useState<number | null>(null);
  const [publishViaMcpIndex, setPublishViaMcpIndex] = useState<number | null>(null);
  const [textImageIndex, setTextImageIndex] = useState<number | null>(null);
  const [leadCaptureIndex, setLeadCaptureIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<XiaohongshuCreatorPreviewItem[]>([]);
  const [publishDrafts, setPublishDrafts] = useState<Record<number, XiaohongshuPublishDraft>>({});
  const [imageDrafts, setImageDrafts] = useState<Record<number, XiaohongshuImageCardDraft>>({});
  const [publishChecklists, setPublishChecklists] = useState<Record<number, XiaohongshuPublishChecklist>>({});
  const [followUpPackets, setFollowUpPackets] = useState<Record<number, XiaohongshuLeadFollowUpPacket>>({});
  const [leadCaptureTemplates, setLeadCaptureTemplates] = useState<Record<number, XiaohongshuLeadCaptureTemplate>>({});
  const [leadCaptureResults, setLeadCaptureResults] = useState<Record<number, XiaohongshuLeadCaptureResponse>>({});
  const [leadReplyPlans, setLeadReplyPlans] = useState<Record<number, XiaohongshuLeadReplyPlan>>({});
  const [autofillResults, setAutofillResults] = useState<Record<number, XiaohongshuPublishAutofillResponse>>({});
  const [publishViaMcpResults, setPublishViaMcpResults] = useState<Record<number, XiaohongshuPublishViaMcpResponse>>({});
  const [textImageResults, setTextImageResults] = useState<Record<number, XiaohongshuTextImageAutofillResponse>>({});
  const [imagePathInputs, setImagePathInputs] = useState<Record<number, string>>({});

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    try {
      const topics = parseTopics(topicsText);
      const activities = parseActivities(activitiesText);
      const nextResults = await previewXiaohongshuCreatorHome({
        account_name: accountName.trim() || undefined,
        topics,
        activities,
        message: message.trim() || undefined,
      });
      setResults(nextResults);
      setPublishDrafts({});
      setImageDrafts({});
      setPublishChecklists({});
      setFollowUpPackets({});
      setLeadCaptureTemplates({});
      setLeadCaptureResults({});
      setLeadReplyPlans({});
      setAutofillResults({});
      setPublishViaMcpResults({});
      setTextImageResults({});
      setImagePathInputs({});
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成小红书经营草稿失败");
    } finally {
      setLoading(false);
    }
  }

  function handleExtractFromRawSnapshot() {
    const extracted = extractCreatorHomeSnapshot(rawSnapshotText);
    if (extracted.topics.length > 0) {
      setTopicsText(
        extracted.topics
          .map((item) => [item.topic, item.participation_count, item.view_count].filter(Boolean).join(" | "))
          .join("\n"),
      );
    }
    if (extracted.activities.length > 0) {
      setActivitiesText(
        extracted.activities
          .map((item) => [item.title, item.date_range, item.incentive_hint].filter(Boolean).join(" | "))
          .join("\n"),
      );
    }
  }

  async function handleCaptureFromChrome() {
    setCapturing(true);
    setError(null);
    try {
      const captured = await captureXiaohongshuCreatorHome();
      setRawSnapshotText(captured.raw_text);
      setAccountName(captured.account_name?.trim() || DEFAULT_ACCOUNT_NAME);
      setTopicsText(
        captured.topics
          .map((item) => [item.topic, item.participation_count, item.view_count].filter(Boolean).join(" | "))
          .join("\n"),
      );
      setActivitiesText(
        captured.activities
          .map((item) => [item.title, item.date_range, item.incentive_hint].filter(Boolean).join(" | "))
          .join("\n"),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "自动读取当前创作首页失败");
    } finally {
      setCapturing(false);
    }
  }

  function ensureDraft(index: number, item: XiaohongshuCreatorPreviewItem): XiaohongshuPublishDraft {
    const existing = publishDrafts[index];
    if (existing) {
      return existing;
    }
    const nextDraft = buildPublishDraft(item);
    setPublishDrafts((current) => ({ ...current, [index]: nextDraft }));
    ensurePublishChecklist(index, item);
    ensureFollowUpPacket(index, item);
    ensureLeadCaptureTemplate(index, item);
    return nextDraft;
  }

  async function handleAutofill(index: number, item: XiaohongshuCreatorPreviewItem) {
    const draft = ensureDraft(index, item);
    setAutofillingIndex(index);
    setError(null);
    try {
      const result = await autofillXiaohongshuPublishDraft({
        title: draft.title,
        body: draft.body,
      });
      setAutofillResults((current) => ({ ...current, [index]: result }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "打开小红书发布页失败");
    } finally {
      setAutofillingIndex(null);
    }
  }

  function ensureImageDraft(index: number, item: XiaohongshuCreatorPreviewItem): XiaohongshuImageCardDraft {
    const existing = imageDrafts[index];
    if (existing) {
      return existing;
    }
    const nextDraft = buildImageCardDraft(item);
    setImageDrafts((current) => ({ ...current, [index]: nextDraft }));
    return nextDraft;
  }

  function ensurePublishChecklist(index: number, item: XiaohongshuCreatorPreviewItem): XiaohongshuPublishChecklist {
    const existing = publishChecklists[index];
    if (existing) {
      return existing;
    }
    const nextChecklist = buildPublishChecklist(item);
    setPublishChecklists((current) => ({ ...current, [index]: nextChecklist }));
    return nextChecklist;
  }

  function ensureFollowUpPacket(index: number, item: XiaohongshuCreatorPreviewItem): XiaohongshuLeadFollowUpPacket {
    const existing = followUpPackets[index];
    if (existing) {
      return existing;
    }
    const nextPacket = buildLeadFollowUpPacket(item);
    setFollowUpPackets((current) => ({ ...current, [index]: nextPacket }));
    return nextPacket;
  }

  function ensureLeadCaptureTemplate(index: number, item: XiaohongshuCreatorPreviewItem): XiaohongshuLeadCaptureTemplate {
    const existing = leadCaptureTemplates[index];
    if (existing) {
      return existing;
    }
    const nextTemplate = buildLeadCaptureTemplate(item);
    setLeadCaptureTemplates((current) => ({ ...current, [index]: nextTemplate }));
    return nextTemplate;
  }

  async function handleTextImageAutofill(index: number, item: XiaohongshuCreatorPreviewItem) {
    const imageDraft = ensureImageDraft(index, item);
    ensurePublishChecklist(index, item);
    ensureFollowUpPacket(index, item);
    ensureLeadCaptureTemplate(index, item);
    setTextImageIndex(index);
    setError(null);
    try {
      const result = await autofillXiaohongshuTextImageCards({
        cards: imageDraft.cards,
        trigger_generate: true,
      });
      setTextImageResults((current) => ({ ...current, [index]: result }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "填入小红书图卡失败");
    } finally {
      setTextImageIndex(null);
    }
  }

  async function handlePublishViaMcp(index: number, item: XiaohongshuCreatorPreviewItem) {
    const draft = ensureDraft(index, item);
    setPublishViaMcpIndex(index);
    setError(null);
    try {
      const result = await publishXiaohongshuViaMcp({
        title: draft.title,
        body: draft.body,
        image_paths: parseImagePaths(imagePathInputs[index] || ""),
      });
      setPublishViaMcpResults((current) => ({ ...current, [index]: result }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "通过 MCP 发布图文失败");
    } finally {
      setPublishViaMcpIndex(null);
    }
  }

  async function handleLeadCapture(index: number, item: XiaohongshuCreatorPreviewItem) {
    const draft = ensureDraft(index, item);
    setLeadCaptureIndex(index);
    setError(null);
    try {
      const result = await captureXiaohongshuLeadSignals({
        title_hint: draft.title,
      });
      setLeadCaptureResults((current) => ({ ...current, [index]: result }));
      const nextReplyPlan = buildLeadReplyPlan(item, result);
      setLeadReplyPlans((current) => ({ ...current, [index]: nextReplyPlan }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "自动提取当前小红书页面线索失败");
    } finally {
      setLeadCaptureIndex(null);
    }
  }

  return (
    <div className="xhs-page">
      <header className="xhs-page__header">
        <div>
          <h2 className="xhs-page__title">小红书经营</h2>
          <p className="xhs-page__subtitle">
            用创作首页里的真实话题和活动，快速生成第一批可发的小红书草稿。现在是 {assistantName} 帮你跑冷启动内容闭环。
          </p>
        </div>
        <Button type="button" onClick={() => void handleGenerate()} disabled={loading}>
          {loading ? "生成中..." : "生成草稿候选"}
        </Button>
      </header>

      {error ? <div className="xhs-page__error">生成失败：{error}</div> : null}

      <section className="xhs-page__grid">
        <XiaohongshuOpportunityPanel
          rawSnapshotText={rawSnapshotText}
          accountName={accountName}
          topicsText={topicsText}
          activitiesText={activitiesText}
          message={message}
          capturing={capturing}
          loading={loading}
          onRawSnapshotChange={setRawSnapshotText}
          onAccountNameChange={setAccountName}
          onTopicsChange={setTopicsText}
          onActivitiesChange={setActivitiesText}
          onMessageChange={setMessage}
          onCapture={() => void handleCaptureFromChrome()}
          onExtract={handleExtractFromRawSnapshot}
        />

        <Panel
          icon="📝"
          title="草稿候选"
          subtitle="这里显示后端返回的可发候选，先挑最顺手的一条。"
          className="xhs-page__panel"
        >
          {results.length === 0 ? (
            <div className="xhs-empty">
              <strong>还没有草稿结果</strong>
              <p>先点一次“生成草稿候选”，就能把创作首页机会转成内容建议。</p>
            </div>
          ) : (
            <div className="xhs-results">
              {results.map((item, index) => {
                const draft = publishDrafts[index];
                const imageDraft = imageDrafts[index];
                const publishChecklist = publishChecklists[index];
                const followUpPacket = followUpPackets[index];
                const leadCaptureTemplate = leadCaptureTemplates[index];
                const leadCaptureResult = leadCaptureResults[index];
                const leadReplyPlan = leadReplyPlans[index];
                return (
                  <XiaohongshuDraftCard
                    key={`${item.platform_result.event.text.slice(0, 20)}-${index}`}
                    item={item}
                    index={index}
                    draft={draft}
                    imageDraft={imageDraft}
                    publishChecklist={publishChecklist}
                    followUpPacket={followUpPacket}
                    leadCaptureTemplate={leadCaptureTemplate}
                    leadCaptureResult={leadCaptureResult}
                    leadReplyPlan={leadReplyPlan}
                    autofillResult={autofillResults[index]}
                    publishViaMcpResult={publishViaMcpResults[index]}
                    textImageResult={textImageResults[index]}
                    autofilling={autofillingIndex === index}
                    publishViaMcpPending={publishViaMcpIndex === index}
                    textImageFilling={textImageIndex === index}
                    leadCapturing={leadCaptureIndex === index}
                    imagePathsText={imagePathInputs[index] || ""}
                    onExpand={() => ensureDraft(index, item)}
                    onAutofill={() => void handleAutofill(index, item)}
                    onImagePathsChange={(value) =>
                      setImagePathInputs((current) => ({
                        ...current,
                        [index]: value,
                      }))
                    }
                    onPublishViaMcp={() => void handlePublishViaMcp(index, item)}
                    onTextImageAutofill={() => void handleTextImageAutofill(index, item)}
                    onLeadCapture={() => void handleLeadCapture(index, item)}
                  />
                );
              })}
            </div>
          )}
        </Panel>
      </section>
    </div>
  );
}
