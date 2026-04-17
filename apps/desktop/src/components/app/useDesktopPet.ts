import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";

import { updatePersonaFeatures } from "../../lib/api";
import type { PersonaProfile } from "../../lib/api";

type UseDesktopPetArgs = {
  onError: (message: string) => void;
  onPersonaChange: (profile: PersonaProfile) => void;
  persona: PersonaProfile | null;
};

type UseDesktopPetResult = {
  petVisible: boolean;
  handlePetEnabledChange: (enabled: boolean) => Promise<void>;
};

export function useDesktopPet({ onError, onPersonaChange, persona }: UseDesktopPetArgs): UseDesktopPetResult {
  const [petVisible, setPetVisible] = useState(false);

  useEffect(() => {
    invoke("pet_is_visible")
      .then((result: any) => {
        if (result && typeof result.visible === "boolean") {
          setPetVisible(result.visible);
        }
      })
      .catch(() => {
        // ignore
      });
  }, []);

  useEffect(() => {
    const enabled = persona?.features?.avatar_enabled ?? false;
    invoke(enabled ? "pet_show" : "pet_close")
      .then((result: any) => {
        if (result && typeof result.visible === "boolean") {
          setPetVisible(result.visible);
        } else {
          setPetVisible(enabled);
        }
      })
      .catch(() => {
        // ignore
      });
  }, [persona?.features?.avatar_enabled]);

  async function handlePetEnabledChange(enabled: boolean) {
    try {
      onError("");
      const updated = await updatePersonaFeatures({ avatar_enabled: enabled });
      onPersonaChange(updated.profile);
      setPetVisible(enabled);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : typeof err === "string"
            ? err
            : err
              ? JSON.stringify(err)
              : "";
      onError(message || "宠物操作失败");
    }
  }

  return { petVisible, handlePetEnabledChange };
}
