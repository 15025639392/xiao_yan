type AutobioPanelProps = {
  entries: string[];
};

export function AutobioPanel({ entries }: AutobioPanelProps) {
  const uniqueEntries = Array.from(new Set(entries));

  return (
    <section className="panel panel--rail">
      <div className="panel__header">
        <div>
          <p className="panel__eyebrow">近期记忆</p>
          <h2 className="panel__title">自我叙事</h2>
        </div>
      </div>
      {uniqueEntries.length === 0 ? (
        <p className="empty-state">还没有形成自我叙事。</p>
      ) : (
        <ul className="narrative-list">
          {uniqueEntries.map((entry) => (
            <li key={entry}>{entry}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
