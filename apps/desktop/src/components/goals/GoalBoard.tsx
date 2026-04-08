import type { Goal, RelationshipSummary } from "../../lib/api";
import { EmptyState } from "../ui/EmptyState";
import { GoalItem } from "./GoalItem";
import type { GoalColumn } from "./goalsUtils";

type GoalBoardProps = {
  columns: GoalColumn[];
  collapsedColumns: Set<string>;
  onToggleColumn: (columnId: string) => void;
  onAbandonClick: (goalId: string, goalTitle: string) => void;
  onCompleteClick: (goalId: string, goalTitle: string) => void;
  onUpdateGoalStatus: (goalId: string, status: Goal["status"]) => void;
  onDecomposeGoal: (goalId: string) => void;
  loadingDecompose: Set<string>;
  relationship: RelationshipSummary | null;
};

export function GoalBoard({
  columns,
  collapsedColumns,
  onToggleColumn,
  onAbandonClick,
  onCompleteClick,
  onUpdateGoalStatus,
  onDecomposeGoal,
  loadingDecompose,
  relationship,
}: GoalBoardProps) {
  return (
    <section className="goal-board">
      <div className="goal-board__row">
        {columns
          .filter((column) => column.id === "active" || column.id === "paused")
          .map((column) => {
            const isCollapsed = collapsedColumns.has(column.id);
            const isActiveColumn = column.id === "active";
            return (
              <section
                key={column.id}
                className={`goal-column ${isCollapsed ? "goal-column--collapsed" : ""} ${isActiveColumn ? "goal-column--wide" : "goal-column--narrow"}`}
              >
                <button
                  className="goal-column__header"
                  onClick={() => onToggleColumn(column.id)}
                  type="button"
                  title={isCollapsed ? "展开" : "折叠"}
                >
                  <h3 className="goal-column__title">{column.title}</h3>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                    <span className="goal-column__count">{column.goals.length}</span>
                    <span className="goal-column__toggle">{isCollapsed ? "▸" : "▾"}</span>
                  </div>
                </button>

                {!isCollapsed ? (
                  <>
                    {column.goals.length === 0 ? (
                      <EmptyState size="small">
                        <p style={{ fontSize: "0.8125rem" }}>{column.description}</p>
                      </EmptyState>
                    ) : (
                      <ul className="goal-list">
                        {column.goals.map((goal) => (
                          <GoalItem
                            key={goal.id}
                            goal={goal}
                            onAbandonClick={onAbandonClick}
                            onCompleteClick={onCompleteClick}
                            onUpdateGoalStatus={onUpdateGoalStatus}
                            onDecomposeGoal={onDecomposeGoal}
                            loadingDecompose={loadingDecompose}
                            relationship={relationship}
                          />
                        ))}
                      </ul>
                    )}
                  </>
                ) : null}
              </section>
            );
          })}
      </div>

      {(() => {
        const closedColumn = columns.find((column) => column.id === "closed");
        if (!closedColumn) return null;
        const isCollapsed = collapsedColumns.has("closed");

        return (
          <section className={`goal-column goal-column--full ${isCollapsed ? "goal-column--collapsed" : ""}`}>
            <button
              className="goal-column__header"
              onClick={() => onToggleColumn("closed")}
              type="button"
              title={isCollapsed ? "展开" : "折叠"}
            >
              <h3 className="goal-column__title">{closedColumn.title}</h3>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                <span className="goal-column__count">{closedColumn.goals.length}</span>
                <span className="goal-column__toggle">{isCollapsed ? "▸" : "▾"}</span>
              </div>
            </button>

            {!isCollapsed ? (
              <>
                {closedColumn.goals.length === 0 ? (
                  <EmptyState size="small">
                    <p style={{ fontSize: "0.8125rem" }}>{closedColumn.description}</p>
                  </EmptyState>
                ) : (
                  <ul className="goal-list goal-list--horizontal">
                    {closedColumn.goals.map((goal) => (
                      <GoalItem
                        key={goal.id}
                        goal={goal}
                        onAbandonClick={onAbandonClick}
                        onCompleteClick={onCompleteClick}
                        onUpdateGoalStatus={onUpdateGoalStatus}
                        onDecomposeGoal={onDecomposeGoal}
                        loadingDecompose={loadingDecompose}
                        relationship={relationship}
                      />
                    ))}
                  </ul>
                )}
              </>
            ) : null}
          </section>
        );
      })()}
    </section>
  );
}
