import { useEffect, useState } from "react";
import type {
  GoalAdmissionConfigHistoryEntry,
  GoalAdmissionCandidateSnapshot,
  GoalAdmissionRuntimeConfig,
  GoalAdmissionStats,
} from "../../lib/api";
import {
  fetchGoalAdmissionCandidates,
  fetchGoalAdmissionConfigHistory,
  fetchGoalAdmissionStats,
  rollbackGoalAdmissionConfig,
  updateGoalAdmissionConfig,
} from "../../lib/api";
import { subscribeAppRealtime } from "../../lib/realtime";
import { GoalsAdmissionCandidates } from "./GoalsAdmissionCandidates";
import { GoalsAdmissionOverview } from "./GoalsAdmissionOverview";
import { GoalsRelationshipGuidance } from "./GoalsRelationshipGuidance";
import type { RelationshipSummary } from "../../lib/api";

type RuntimePayload = {
  goal_admission_stats?: GoalAdmissionStats | null;
  goal_admission_candidates?: GoalAdmissionCandidateSnapshot | null;
};

function syncAdmissionFromRuntime(
  runtimePayload: RuntimePayload,
  setAdmissionStats: (value: GoalAdmissionStats | null) => void,
  setAdmissionCandidates: (value: GoalAdmissionCandidateSnapshot | null) => void,
) {
  if (runtimePayload.goal_admission_stats !== undefined) {
    setAdmissionStats(runtimePayload.goal_admission_stats ?? null);
  }
  if (runtimePayload.goal_admission_candidates !== undefined) {
    setAdmissionCandidates(runtimePayload.goal_admission_candidates ?? null);
  }
}

export function GoalsGovernanceSection({ relationship }: { relationship: RelationshipSummary | null }) {
  const [admissionStats, setAdmissionStats] = useState<GoalAdmissionStats | null>(null);
  const [admissionCandidates, setAdmissionCandidates] = useState<GoalAdmissionCandidateSnapshot | null>(null);
  const [admissionConfigHistory, setAdmissionConfigHistory] = useState<GoalAdmissionConfigHistoryEntry[]>([]);

  useEffect(() => {
    const unsubscribe = subscribeAppRealtime((event) => {
      const runtimePayload =
        event.type === "snapshot" ? event.payload.runtime : event.type === "runtime_updated" ? event.payload : null;
      if (runtimePayload) {
        syncAdmissionFromRuntime(runtimePayload, setAdmissionStats, setAdmissionCandidates);
      }
    });

    return () => unsubscribe();
  }, []);

  useEffect(() => {
    let cancelled = false;

    fetchGoalAdmissionStats()
      .then((stats) => {
        if (!cancelled) {
          setAdmissionStats(stats);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAdmissionStats(null);
        }
      });

    fetchGoalAdmissionCandidates()
      .then((snapshot) => {
        if (!cancelled) {
          setAdmissionCandidates(snapshot);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAdmissionCandidates(null);
        }
      });

    fetchGoalAdmissionConfigHistory(10)
      .then((history) => {
        if (!cancelled) {
          setAdmissionConfigHistory(history.items);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAdmissionConfigHistory([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleUpdateAdmissionThresholds(patch: Partial<GoalAdmissionRuntimeConfig>): Promise<void> {
    await updateGoalAdmissionConfig(patch);
    const [latest, history] = await Promise.all([
      fetchGoalAdmissionStats(),
      fetchGoalAdmissionConfigHistory(10),
    ]);
    setAdmissionStats(latest);
    setAdmissionConfigHistory(history.items);
  }

  async function handleRollbackAdmissionThresholds(): Promise<void> {
    await rollbackGoalAdmissionConfig();
    const [latest, history] = await Promise.all([
      fetchGoalAdmissionStats(),
      fetchGoalAdmissionConfigHistory(10),
    ]);
    setAdmissionStats(latest);
    setAdmissionConfigHistory(history.items);
  }

  return (
    <>
      <GoalsRelationshipGuidance relationship={relationship} />
      <GoalsAdmissionOverview
        stats={admissionStats}
        history={admissionConfigHistory}
        onUpdateStabilityThresholds={handleUpdateAdmissionThresholds}
        onRollbackStabilityThresholds={handleRollbackAdmissionThresholds}
      />
      <GoalsAdmissionCandidates snapshot={admissionCandidates} />
    </>
  );
}
