import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { previewXiaohongshuCover } from "../lib/api";

import { XiaohongshuPage } from "./XiaohongshuPage";
import {
  buildImageCardDraft,
  buildLeadCaptureTemplate,
  buildLeadFollowUpPacket,
  parseImagePaths,
  buildPublishChecklist,
  buildPublishDraft,
  expandPreviewIntoPublishDraft,
  extractCreatorHomeSnapshot,
} from "./xiaohongshuPageHelpers";
import { XiaohongshuDraftCard } from "./XiaohongshuDraftCard";
import { buildLeadReplyPlan } from "./xiaohongshuLeadReplyHelpers";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    previewXiaohongshuCover: vi.fn().mockResolvedValue({
      title: "测试标题",
      body: "测试正文",
      template_name: "expert_clean",
      available_templates: ["warm_story", "expert_clean", "bold_hook"],
      image_path: "/tmp/xhs-cover-preview.png",
      image_data_url: "data:image/png;base64,preview-default",
    }),
  };
});

test("extractCreatorHomeSnapshot pulls topics and activities from raw creator-home text", () => {
  const result = extractCreatorHomeSnapshot(`
创作话题
#高颜值巧克力
30万人参与，14.4亿次浏览
#早餐吃什么
288.7万人参与，105.3亿次浏览
热门活动
官方活动, 奖励多多
RED新生代创作大赛 03-30 至 05-10
春天见面会 04-18 至 04-30
  `);

  expect(result.topics).toEqual([
    {
      topic: "#高颜值巧克力",
      participation_count: "30万人参与",
      view_count: "14.4亿次浏览",
    },
    {
      topic: "#早餐吃什么",
      participation_count: "288.7万人参与",
      view_count: "105.3亿次浏览",
    },
  ]);
  expect(result.activities).toEqual([
    {
      title: "RED新生代创作大赛",
      date_range: "03-30 至 05-10",
      incentive_hint: "官方活动, 奖励多多",
    },
    {
      title: "春天见面会",
      date_range: "04-18 至 04-30",
      incentive_hint: "官方活动, 奖励多多",
    },
  ]);
});

test("expandPreviewIntoPublishDraft builds a publish-ready draft from preview result", () => {
  const previewItem = {
    output_text: "可以先轻一点接住对方，再给一个低压力的下一步。",
    publish_draft: {
      title: "#高颜值巧克力 不是晒图就行，第一条先这样写",
      opening: "很多人发巧克力内容，问题不是图不够好，而是别人看完不知道你到底想帮她解决什么。",
      body_sections: ["先把人群说清楚。", "再把一个最具体的小技巧讲透。", "最后留一个轻互动口子。"],
      closing_cta: "这条先别写太满，先让人愿意看完并评论。",
      first_comment: "如果你想看我把这条拆成封面和配图版本，可以留言。",
      image_cards: [
        { title: "第一条别只晒图", body: "先说清楚你在帮谁解决什么问题。" },
        { title: "中间页只讲一个动作", body: "别把所有技巧都塞进一条里。" },
        { title: "结尾留一个轻互动", body: "让真正感兴趣的人继续问。" },
      ],
    },
    platform_result: {
      event: {
        event_type: "post",
        text: "这是小红薯66661C17在小红书创作首页看到的创作话题机会。\n推荐话题：#高颜值巧克力",
      },
      actions: [
        {
          action_type: "note_draft_candidate",
          title: "小红书笔记草稿",
          content: "可以先轻一点接住对方，再给一个低压力的下一步。",
        },
      ],
    },
    lead_assessment: {
      is_lead: false,
      intent_level: "low",
      lead_stage: "observe",
      suggested_action: "prepare_note",
      reasons: ["来源于创作首页机会池，优先进入内容生产闭环"],
    },
  };
  const expanded = expandPreviewIntoPublishDraft(previewItem);
  const draft = buildPublishDraft(previewItem);

  expect(expanded).toContain("标题：#高颜值巧克力 不是晒图就行，第一条先这样写");
  expect(expanded).toContain("首评：");
  expect(draft.title).toContain("#高颜值巧克力");
  expect(draft.body).toContain("先把人群说清楚");
});

test("buildImageCardDraft builds three practical image cards from preview result", () => {
  const previewItem = {
    output_text: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
    publish_draft: {
      title: "#早餐吃什么 别上来就堆做法",
      opening: "早餐内容最容易写空，因为大家都在堆食谱，却没先讲清楚适合谁。",
      body_sections: ["先讲一个真实早晨场景。", "再给一个能立刻照着做的动作。", "最后再补一句为什么值得保存。"],
      closing_cta: "这样更像真人经验，不像食谱搬运。",
      first_comment: "想看我继续拆成封面文案，可以留言。",
      image_cards: [
        { title: "#早餐吃什么 别先堆做法", body: "先把人和场景说清楚。" },
        { title: "中间页只讲一个动作", body: "别一页塞五条建议。" },
        { title: "结尾告诉大家为什么值得存", body: "这样才更容易被收藏。" },
      ],
    },
    platform_result: {
      event: {
        event_type: "post",
        text: "这是小红薯66661C17在小红书创作首页看到的创作话题机会。\n推荐话题：#早餐吃什么",
      },
      actions: [
        {
          action_type: "note_draft_candidate",
          title: "小红书笔记草稿",
          content: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
        },
      ],
    },
  };

  const imageDraft = buildImageCardDraft(previewItem);

  expect(imageDraft.cards).toHaveLength(3);
  expect(imageDraft.cards[0]).toContain("#早餐吃什么 别先堆做法");
  expect(imageDraft.cards[1]).toContain("中间页只讲一个动作");
  expect(imageDraft.cards[2]).toContain("为什么值得存");
});

test("buildPublishChecklist builds a publish packet for manual release work", () => {
  const previewItem = {
    output_text: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
    publish_draft: {
      title: "#早餐吃什么 别上来就堆做法",
      opening: "早餐内容最容易写空，因为大家都在堆食谱，却没先讲清楚适合谁。",
      body_sections: ["先讲一个真实早晨场景。", "再给一个能立刻照着做的动作。", "最后再补一句为什么值得保存。"],
      closing_cta: "这样更像真人经验，不像食谱搬运。",
      first_comment: "如果你想看我把这条继续拆成封面文案，可以留言。",
      image_cards: [
        { title: "卡1", body: "内容1" },
        { title: "卡2", body: "内容2" },
        { title: "卡3", body: "内容3" },
      ],
    },
    platform_result: {
      event: {
        event_type: "post",
        text: "这是小红薯66661C17在小红书创作首页看到的创作话题机会。\n推荐话题：#早餐吃什么",
      },
      actions: [
        {
          action_type: "note_draft_candidate",
          title: "小红书笔记草稿",
          content: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
        },
      ],
    },
  };

  const checklist = buildPublishChecklist(previewItem);

  expect(checklist.firstComment).toContain("封面文案");
  expect(checklist.preflightChecks).toHaveLength(5);
  expect(checklist.postPublishActions).toHaveLength(3);
  expect(checklist.publishPacketText).toContain("发布前检查：");
  expect(checklist.publishPacketText).toContain("发布后动作：");
});

test("buildLeadFollowUpPacket builds practical conversion follow-up copy", () => {
  const previewItem = {
    output_text: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
    platform_result: {
      event: {
        event_type: "post",
        text: "这是小红薯66661C17在小红书创作首页看到的创作话题机会。\n推荐话题：#早餐吃什么",
      },
      actions: [
        {
          action_type: "note_draft_candidate",
          title: "小红书笔记草稿",
          content: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
        },
      ],
    },
    lead_assessment: {
      is_lead: true,
      intent_level: "medium",
      lead_stage: "engage",
      suggested_action: "reply_comment",
      follow_up_hint: "先确认对方当前阶段，再决定要不要继续细聊。",
      reasons: ["对方已经表现出明确兴趣"],
    },
  };

  const packet = buildLeadFollowUpPacket(previewItem);

  expect(packet.commentReply).toContain("可以的");
  expect(packet.directMessage).toContain("更具体的 1 版执行步骤");
  expect(packet.wechatBridge).toContain("转到微信人工细聊");
  expect(packet.followUpPacketText).toContain("微信导流：");
});

test("buildLeadCaptureTemplate builds a reusable lead tracking template", () => {
  const previewItem = {
    output_text: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
    platform_result: {
      event: {
        event_type: "post",
        text: "这是小红薯66661C17在小红书创作首页看到的创作话题机会。\n推荐话题：#早餐吃什么",
      },
      actions: [
        {
          action_type: "note_draft_candidate",
          title: "小红书笔记草稿",
          content: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
        },
      ],
    },
  };

  const template = buildLeadCaptureTemplate(previewItem);

  expect(template.signalChecklist).toHaveLength(5);
  expect(template.reviewQuestions).toHaveLength(3);
  expect(template.trackingTemplate).toContain("导到微信人数：");
  expect(template.trackingTemplate).toContain("复盘问题：");
});

test("parseImagePaths keeps non-empty path lines", () => {
  expect(parseImagePaths(" /tmp/a.png \n\n /tmp/b.png ")).toEqual(["/tmp/a.png", "/tmp/b.png"]);
});

test("buildLeadReplyPlan ranks high-intent comments into a practical reply order", () => {
  const previewItem = {
    output_text: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
    platform_result: {
      event: {
        event_type: "post",
        text: "这是小红薯66661C17在小红书创作首页看到的创作话题机会。\n推荐话题：#早餐吃什么",
      },
      actions: [
        {
          action_type: "note_draft_candidate",
          title: "小红书笔记草稿",
          content: "先借平台给的流量入口起步，再用轻量文案去拿真实反馈。",
        },
      ],
    },
  };

  const replyPlan = buildLeadReplyPlan(previewItem, {
    source_url: "https://creator.xiaohongshu.com/new/home",
    note_title: "测试标题",
    raw_text: "raw",
    like_count: "128",
    collect_count: "46",
    comment_count: "12",
    share_count: "3",
    direct_message_signal_count: 1,
    wechat_signal_count: 1,
    purchase_signal_count: 1,
    lead_keywords: ["微信", "报价"],
    matched_comment_lines: ["想加微信细聊预算和报价", "可以私信我一版方案吗？", "这个适合新手怎么开始？"],
    tracking_template: "内容标题：测试标题",
    message: "ok",
  });

  expect(replyPlan.suggestions).toHaveLength(3);
  expect(replyPlan.suggestions[0]?.priorityLabel).toContain("P1");
  expect(replyPlan.suggestions[0]?.recommendedAction).toContain("微信");
  expect(replyPlan.fullText).toContain("高意向评论优先回复：");
  expect(replyPlan.fullText).toContain("建议回复：");
  expect(replyPlan.summary).toContain("3 条");
});

test("draft card switches text-image button label after manual expand is needed", () => {
  render(
    <XiaohongshuDraftCard
      item={{
        output_text: "先借平台给的流量入口起步。",
        platform_result: {
          event: { event_type: "post", text: "推荐话题：#早餐吃什么" },
          actions: [{ action_type: "note_draft_candidate", title: "小红书笔记草稿", content: "先借平台给的流量入口起步。" }],
        },
      }}
      index={0}
      imageDraft={{
        cards: ["封面图卡", "正文图卡1", "正文图卡2"],
        fullText: "图卡 1\n封面图卡\n\n图卡 2\n正文图卡1\n\n图卡 3\n正文图卡2",
      }}
      publishChecklist={{
        firstComment: "评论区回我“模板”。",
        preflightChecks: ["检查 1", "检查 2"],
        postPublishActions: ["动作 1", "动作 2"],
        publishPacketText: "首评：评论区回我“模板”。",
      }}
      followUpPacket={{
        commentReply: "评论回复话术",
        directMessage: "私信承接话术",
        wechatBridge: "微信导流话术",
        followUpPacketText: "承接包内容",
      }}
      leadCaptureTemplate={{
        trackingTemplate: "内容标题：测试标题\n导到微信人数：",
        signalChecklist: ["信号 1"],
        reviewQuestions: ["问题 1"],
      }}
      leadReplyPlan={{
        summary: "当前页已命中 1 条值得优先承接的评论。",
        suggestions: [
          {
            priorityLabel: "优先级 P1：马上承接并尽快导到微信",
            commentLine: "想加微信细聊预算和报价",
            recommendedAction: "先在评论区接住，再马上私信给微信承接话术。",
            replyDraft: "可以，我先在这边接住你。",
          },
        ],
        fullText: "高意向评论优先回复：\n1. 优先级 P1：马上承接并尽快导到微信",
      }}
      textImageResult={{
        status: "needs_manual_expand",
        publish_url: "https://creator.xiaohongshu.com/publish/publish?from=xiao_yan&target=image",
        cards: ["封面", "正文1", "正文2"],
        filled_cards: 1,
        clicked_generate: false,
        message: "已先填入 1/3 张图卡文案。请先在小红书页面点一次“再写一张”，再回到小晏点“继续填正文页”。",
      }}
      publishViaMcpResult={{
        status: "submitted",
        message: "MCP 发布结果：已提交图文发布",
        published_title: "测试标题",
        image_count: 2,
        image_paths: ["/tmp/cover.png", "/tmp/page2.png"],
        post_url: "https://www.xiaohongshu.com/explore/test",
        platform_post_id: "note_123",
      }}
      autofilling={false}
      autoPublishing={false}
      publishViaMcpPending={false}
      textImageFilling={false}
      leadCapturing={false}
      imagePathsText={"/tmp/cover.png\n/tmp/page2.png"}
      onExpand={() => {}}
      onAutofill={() => {}}
      onAutoPublish={() => {}}
      onImagePathsChange={() => {}}
      onPublishViaMcp={() => {}}
      onTextImageAutofill={() => {}}
      onLeadCapture={() => {}}
    />,
  );

  expect(screen.getByRole("button", { name: "从当前页自动提取" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "用 MCP 发布图文" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "我已点再写一张，继续填正文页" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制下一张图卡" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制首评" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制发布清单" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制评论回复" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制私信承接" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制微信导流" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制线索模板" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制承接优先级" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "复制回复 1" })).toBeInTheDocument();
  expect(screen.getByText("待回复名单")).toBeInTheDocument();
  expect(screen.getByText("经营结果摘要")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "已私信" })).toBeInTheDocument();
  expect(screen.getByText("MCP 发布图片路径")).toBeInTheDocument();
  const mcpPathSection = screen.getByText("MCP 发布图片路径").parentElement;
  const mcpPathTextarea = mcpPathSection?.querySelector("textarea");
  expect(mcpPathTextarea).not.toBeNull();
  expect(mcpPathTextarea).toHaveValue("/tmp/cover.png\n/tmp/page2.png");
  expect(screen.getByText(/MCP 发布结果：已提交图文发布/)).toBeInTheDocument();
  expect(screen.getByText(/https:\/\/www\.xiaohongshu\.com\/explore\/test/)).toBeInTheDocument();
});

test("draft card can preview and switch xiaohongshu cover templates", async () => {
  const previewMock = vi.mocked(previewXiaohongshuCover);
  previewMock.mockResolvedValueOnce({
    title: "测试标题",
    body: "测试正文",
    template_name: "expert_clean",
    available_templates: ["warm_story", "expert_clean", "bold_hook"],
    image_path: "/tmp/xhs-cover-preview.png",
    image_data_url: "data:image/png;base64,preview-default",
  });
  previewMock.mockResolvedValueOnce({
    title: "测试标题",
    body: "测试正文",
    template_name: "bold_hook",
    available_templates: ["warm_story", "expert_clean", "bold_hook"],
    image_path: "/tmp/xhs-cover-preview-bold.png",
    image_data_url: "data:image/png;base64,preview-bold",
  });

  render(
    <XiaohongshuDraftCard
      item={{
        output_text: "先借平台给的流量入口起步。",
        platform_result: {
          event: { event_type: "post", text: "推荐话题：#早餐吃什么" },
          actions: [{ action_type: "note_draft_candidate", title: "小红书笔记草稿", content: "先借平台给的流量入口起步。" }],
        },
      }}
      index={0}
      draft={{
        title: "测试标题",
        body: "测试正文",
        fullText: "标题：测试标题\n\n正文：\n测试正文",
      }}
      autofilling={false}
      autoPublishing={false}
      publishViaMcpPending={false}
      textImageFilling={false}
      leadCapturing={false}
      imagePathsText=""
      onExpand={() => {}}
      onAutofill={() => {}}
      onAutoPublish={() => {}}
      onImagePathsChange={() => {}}
      onPublishViaMcp={() => {}}
      onTextImageAutofill={() => {}}
      onLeadCapture={() => {}}
    />,
  );

  await waitFor(() => {
    expect(screen.getByAltText("封面预览-expert_clean")).toBeInTheDocument();
  });
  expect(previewMock).toHaveBeenCalledWith({ title: "测试标题", body: "测试正文" });

  fireEvent.click(screen.getByRole("button", { name: "强钩子" }));

  await waitFor(() => {
    expect(screen.getByAltText("封面预览-bold_hook")).toBeInTheDocument();
  });
  expect(previewMock).toHaveBeenLastCalledWith({
    title: "测试标题",
    body: "测试正文",
    template_name: "bold_hook",
  });
});

test("lead queue can advance a suggestion from pending to dm follow-up", () => {
  render(
    <XiaohongshuDraftCard
      item={{
        output_text: "先借平台给的流量入口起步。",
        platform_result: {
          event: { event_type: "post", text: "推荐话题：#早餐吃什么" },
          actions: [{ action_type: "note_draft_candidate", title: "小红书笔记草稿", content: "先借平台给的流量入口起步。" }],
        },
      }}
      index={0}
      leadReplyPlan={{
        summary: "当前页已命中 1 条值得优先承接的评论。",
        suggestions: [
          {
            priorityLabel: "优先级 P1：马上承接并尽快导到微信",
            commentLine: "想加微信细聊预算和报价",
            recommendedAction: "先在评论区接住，再马上私信给微信承接话术。",
            replyDraft: "可以，我先在这边接住你。",
          },
        ],
        fullText: "高意向评论优先回复：\n1. 优先级 P1：马上承接并尽快导到微信",
      }}
      autofilling={false}
      autoPublishing={false}
      publishViaMcpPending={false}
      textImageFilling={false}
      leadCapturing={false}
      imagePathsText=""
      onExpand={() => {}}
      onAutofill={() => {}}
      onAutoPublish={() => {}}
      onImagePathsChange={() => {}}
      onPublishViaMcp={() => {}}
      onTextImageAutofill={() => {}}
      onLeadCapture={() => {}}
    />,
  );

  expect(screen.getByText("当前状态：待回复")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "已私信" }));
  expect(screen.getByText("当前状态：已私信")).toBeInTheDocument();
  expect(screen.getByText("成交可能性：高，建议优先跟到底")).toBeInTheDocument();
  expect(
    screen.getByText((content) => content.includes("高意向") && content.includes("已私信 1") && content.includes("已导微信 0")),
  ).toBeInTheDocument();
});

test("lead queue note can raise qualification hint when budget and schedule appear", () => {
  render(
    <XiaohongshuDraftCard
      item={{
        output_text: "先借平台给的流量入口起步。",
        platform_result: {
          event: { event_type: "post", text: "推荐话题：#早餐吃什么" },
          actions: [{ action_type: "note_draft_candidate", title: "小红书笔记草稿", content: "先借平台给的流量入口起步。" }],
        },
      }}
      index={0}
      leadReplyPlan={{
        summary: "当前页已命中 1 条值得优先承接的评论。",
        suggestions: [
          {
            priorityLabel: "优先级 P2：优先回复并继续追问",
            commentLine: "这个适合新手怎么开始？",
            recommendedAction: "先用低压力回复接住，再追问当前阶段和卡点。",
            replyDraft: "可以的。你先说下你现在是刚开始，还是已经发过内容但没转化。",
          },
        ],
        fullText: "高意向评论优先回复：\n1. 优先级 P2：优先回复并继续追问",
      }}
      autofilling={false}
      autoPublishing={false}
      publishViaMcpPending={false}
      textImageFilling={false}
      leadCapturing={false}
      imagePathsText=""
      onExpand={() => {}}
      onAutofill={() => {}}
      onAutoPublish={() => {}}
      onImagePathsChange={() => {}}
      onPublishViaMcp={() => {}}
      onTextImageAutofill={() => {}}
      onLeadCapture={() => {}}
    />,
  );

  expect(screen.getByText("成交可能性：低，先轻量承接观察反应")).toBeInTheDocument();
  fireEvent.change(screen.getByPlaceholderText("例如：预算 3000，本周可聊，想做减脂赛道"), {
    target: { value: "预算 3000，本周可聊，想做减脂赛道" },
  });
  expect(screen.getByText("成交可能性：中，值得继续追问预算和时间")).toBeInTheDocument();
  expect(screen.getByText("当前最值得跟：这个适合新手怎么开始？")).toBeInTheDocument();
  expect(
    screen.getByText((_, element) =>
      element?.tagName.toLowerCase() === "p" &&
      element.textContent === "经营结论：这条内容更适合先引流和筛选意向，继续追问预算与时间。",
    ),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "已导微信" }));
  expect(screen.getByText("成交可能性：高，建议优先跟到底")).toBeInTheDocument();
  expect(
    screen.getByText((content) => content.includes("高意向") && content.includes("已私信 0") && content.includes("已导微信 1")),
  ).toBeInTheDocument();
  expect(
    screen.getByText((_, element) =>
      element?.tagName.toLowerCase() === "p" &&
      element.textContent === "经营结论：这条内容已经出现较强承接苗头，值得继续追并放大同类内容。",
    ),
  ).toBeInTheDocument();
});
