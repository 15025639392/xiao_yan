import { MemoryPanel } from "../components/MemoryPanel";

export function MemoryPage({ assistantName }: { assistantName: string }) {
  return (
    <div className="memory-page">
      <header className="memory-page__header">
        <h2 className="memory-page__title">记忆库</h2>
        <p className="memory-page__subtitle">浏览和管理数字人的记忆</p>
      </header>
      <div className="memory-page__content">
        <MemoryPanel assistantName={assistantName} />
      </div>
    </div>
  );
}

