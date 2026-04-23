import { post } from "./apiClient";

export type XiaohongshuCoverPreviewRequest = {
  title: string;
  body: string;
  template_name?: string | null;
};

export type XiaohongshuCoverPreviewResponse = {
  title: string;
  body: string;
  template_name: string;
  available_templates: string[];
  image_path: string;
  image_data_url: string;
};

export function previewXiaohongshuCover(
  body: XiaohongshuCoverPreviewRequest,
): Promise<XiaohongshuCoverPreviewResponse> {
  return post<XiaohongshuCoverPreviewResponse>("/platform-adapters/xiaohongshu/cover-preview", body);
}
