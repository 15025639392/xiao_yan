import { MemoryBatchToolbar } from "./memory/MemoryBatchToolbar";
import { MemoryDeleteModal } from "./memory/MemoryDeleteModal";
import { MemoryFooter } from "./memory/MemoryFooter";
import { MemoryItem } from "./memory/MemoryItem";
import { MemoryList } from "./memory/MemoryList";
import { MemoryStatsHeader } from "./memory/MemoryStatsHeader";
import { MemoryCreateForm, MemoryToolbar } from "./memory/MemoryToolbar";
import { useMemoryPanelState } from "./memory/useMemoryPanel";

type MemoryPanelProps = {
  assistantName?: string;
  className?: string;
};

export function MemoryPanel({ assistantName = "小晏", className }: MemoryPanelProps) {
  const state = useMemoryPanelState();

  return (
    <section className={`memory-panel ${className ?? ""}`}>
      <MemoryStatsHeader
        summary={state.summary}
        activeFilter={state.activeFilter}
        onFilterToggle={(kind) => state.setActiveFilter(state.activeFilter === kind ? null : kind)}
      />

      <MemoryToolbar
        searchQuery={state.searchQuery}
        onSearchQueryChange={state.setSearchQuery}
        onClearSearch={state.clearSearch}
        isBatchMode={state.isBatchMode}
        onToggleBatchMode={state.toggleBatchMode}
        isCreating={state.isCreating}
        onToggleCreateForm={state.toggleCreateForm}
        viewMode={state.viewMode}
        onViewModeChange={state.setViewMode}
      />

      <MemoryCreateForm
        open={state.isCreating}
        createContent={state.createContent}
        onCreateContentChange={state.setCreateContent}
        createKind={state.createKind}
        onCreateKindChange={state.setCreateKind}
        submitting={state.createSubmitting}
        onSubmit={state.handleCreateMemory}
        inputRef={state.createInputRef}
      />

      <div className="memory-list">
        <MemoryList
          loading={state.loading}
          entries={state.displayEntries}
          viewMode={state.viewMode}
          renderItem={(entry) => (
            <MemoryItem
              key={entry.id}
              entry={entry}
              assistantName={assistantName}
              isBatchMode={state.isBatchMode}
              isSelected={state.selectedIds.has(entry.id)}
              isEditing={state.editingId === entry.id}
              isDeleting={state.deletingId === entry.id}
              editContent={state.editContent}
              onEditContentChange={state.setEditContent}
              onToggleSelection={state.toggleSelection}
              onStar={state.handleStar}
              onStartEdit={state.handleStartEdit}
              onCancelEdit={state.handleCancelEdit}
              onSaveEdit={state.handleSaveEdit}
              onRequestDelete={(id, content) => {
                state.setDeleteModalTarget({ id, content });
                state.setDeleteModalOpen(true);
              }}
            />
          )}
        />
      </div>

      <MemoryFooter
        loading={state.loading}
        displayCount={state.displayEntries.length}
        showSearchOnly={state.showSearchOnly}
        searchQuery={state.searchQuery}
        onClearSearch={state.clearSearch}
      />

      <MemoryBatchToolbar
        show={state.isBatchMode}
        selectedCount={state.selectedIds.size}
        totalDisplayCount={state.displayEntries.length}
        batchDeleting={state.batchDeleting}
        onToggleSelectAll={state.toggleSelectAll}
        onBatchDelete={state.handleBatchDelete}
        onCancel={state.toggleBatchMode}
      />

      <MemoryDeleteModal
        open={Boolean(state.deleteModalOpen && state.deleteModalTarget)}
        contentPreview={
          state.deleteModalTarget
            ? state.deleteModalTarget.content.length > 100
              ? state.deleteModalTarget.content.slice(0, 100) + "..."
              : state.deleteModalTarget.content
            : ""
        }
        deleting={Boolean(state.deleteModalTarget && state.deletingId === state.deleteModalTarget.id)}
        onCancel={state.closeDeleteModal}
        onConfirm={() => state.deleteModalTarget && state.handleDelete(state.deleteModalTarget.id)}
      />
    </section>
  );
}

