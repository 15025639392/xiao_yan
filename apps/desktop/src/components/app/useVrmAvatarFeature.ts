import { updatePersonaFeatures } from "../../lib/api";
import { setAvatarWindowVisible } from "../avatar/avatarWindowController";
import type { PersonaProfile } from "../../lib/api";

type UseVrmAvatarFeatureArgs = {
  onError: (message: string) => void;
  onPersonaChange: (profile: PersonaProfile) => void;
};

type UseVrmAvatarFeatureResult = {
  handleAvatarEnabledChange: (enabled: boolean) => Promise<void>;
};

export function useVrmAvatarFeature({ onError, onPersonaChange }: UseVrmAvatarFeatureArgs): UseVrmAvatarFeatureResult {
  async function handleAvatarEnabledChange(enabled: boolean) {
    try {
      onError("");
      const updated = await updatePersonaFeatures({ avatar_enabled: enabled });
      onPersonaChange(updated.profile);
      await setAvatarWindowVisible(enabled);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : typeof err === "string"
            ? err
            : err
              ? JSON.stringify(err)
              : "";
      onError(message || "VRM 外显开关更新失败");
    }
  }

  return { handleAvatarEnabledChange };
}
