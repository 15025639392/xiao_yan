import { post } from "./apiClient";

export type XiaohongshuCreatorHomeTopic = {
  topic: string;
  participation_count?: string | null;
  view_count?: string | null;
};

export type XiaohongshuCreatorHomeActivity = {
  title: string;
  date_range?: string | null;
  incentive_hint?: string | null;
};

export type XiaohongshuCreatorHomePreviewRequest = {
  account_name?: string | null;
  topics: XiaohongshuCreatorHomeTopic[];
  activities: XiaohongshuCreatorHomeActivity[];
  message?: string | null;
};

export type XiaohongshuCreatorHomeCaptureResponse = {
  source_url: string;
  account_name?: string | null;
  raw_text: string;
  topics: XiaohongshuCreatorHomeTopic[];
  activities: XiaohongshuCreatorHomeActivity[];
};

export type XiaohongshuPublishAutofillRequest = {
  title: string;
  body: string;
};

export type XiaohongshuPublishAutofillResponse = {
  status: string;
  publish_url: string;
  title: string;
  body: string;
  filled_title: boolean;
  filled_body: boolean;
  message: string;
};

export type XiaohongshuPublishViaMcpRequest = {
  title: string;
  body: string;
  image_paths: string[];
};

export type XiaohongshuPublishViaMcpResponse = {
  status: string;
  message: string;
  published_title: string;
  image_count: number;
  image_paths: string[];
  post_url?: string | null;
  platform_post_id?: string | null;
};

export type XiaohongshuTextImageAutofillRequest = {
  cards: string[];
  trigger_generate?: boolean;
};

export type XiaohongshuTextImageAutofillResponse = {
  status: string;
  publish_url: string;
  cards: string[];
  filled_cards: number;
  clicked_generate: boolean;
  message: string;
};

export type XiaohongshuLeadCaptureRequest = {
  title_hint?: string | null;
};

export type XiaohongshuLeadCaptureResponse = {
  source_url: string;
  note_title: string;
  raw_text: string;
  like_count?: string | null;
  collect_count?: string | null;
  comment_count?: string | null;
  share_count?: string | null;
  direct_message_signal_count: number;
  wechat_signal_count: number;
  purchase_signal_count: number;
  lead_keywords: string[];
  matched_comment_lines: string[];
  tracking_template: string;
  message: string;
};

export type PlatformPreviewLeadAssessment = {
  is_lead: boolean;
  intent_level: "low" | "medium" | "high";
  lead_stage: "ignore" | "observe" | "engage" | "follow_up";
  suggested_action: "ignore" | "reply_comment" | "prepare_note" | "follow_up_manually";
  follow_up_hint?: string | null;
  reasons: string[];
};

export type PlatformPreviewAction = {
  action_type: string;
  title?: string | null;
  content: string;
};

export type PlatformPreviewEvent = {
  event_type: string;
  text: string;
  metadata?: Record<string, unknown>;
};

export type XiaohongshuImageCardDraftItem = {
  title: string;
  body: string;
};

export type XiaohongshuStructuredPublishDraft = {
  title: string;
  opening: string;
  body_sections: string[];
  closing_cta: string;
  first_comment: string;
  image_cards: XiaohongshuImageCardDraftItem[];
};

export type XiaohongshuCreatorPreviewItem = {
  output_text: string;
  platform_result: {
    event: PlatformPreviewEvent;
    actions: PlatformPreviewAction[];
  };
  lead_assessment?: PlatformPreviewLeadAssessment | null;
  publish_draft?: XiaohongshuStructuredPublishDraft | null;
};

export function previewXiaohongshuCreatorHome(
  body: XiaohongshuCreatorHomePreviewRequest,
): Promise<XiaohongshuCreatorPreviewItem[]> {
  return post<XiaohongshuCreatorPreviewItem[]>("/platform-adapters/xiaohongshu/creator-home-preview", body);
}

export function captureXiaohongshuCreatorHome(): Promise<XiaohongshuCreatorHomeCaptureResponse> {
  return post<XiaohongshuCreatorHomeCaptureResponse>("/platform-adapters/xiaohongshu/creator-home-capture");
}

export function autofillXiaohongshuPublishDraft(
  body: XiaohongshuPublishAutofillRequest,
): Promise<XiaohongshuPublishAutofillResponse> {
  return post<XiaohongshuPublishAutofillResponse>("/platform-adapters/xiaohongshu/publish-autofill", body);
}

export function publishXiaohongshuViaMcp(
  body: XiaohongshuPublishViaMcpRequest,
): Promise<XiaohongshuPublishViaMcpResponse> {
  return post<XiaohongshuPublishViaMcpResponse>("/platform-adapters/xiaohongshu/publish-via-mcp", body);
}

export function autofillXiaohongshuTextImageCards(
  body: XiaohongshuTextImageAutofillRequest,
): Promise<XiaohongshuTextImageAutofillResponse> {
  return post<XiaohongshuTextImageAutofillResponse>("/platform-adapters/xiaohongshu/text-image-autofill", body);
}

export function captureXiaohongshuLeadSignals(
  body: XiaohongshuLeadCaptureRequest,
): Promise<XiaohongshuLeadCaptureResponse> {
  return post<XiaohongshuLeadCaptureResponse>("/platform-adapters/xiaohongshu/lead-capture", body);
}
