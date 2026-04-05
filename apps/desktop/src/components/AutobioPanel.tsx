type AutobioPanelProps = {
  entries: string[];
};

export function AutobioPanel({ entries }: AutobioPanelProps) {
  const uniqueEntries = Array.from(new Set(entries));

  return (
    <section className="panel">
      <div className="panel__header">
        <div className="panel__title-group">
          <div className="panel__icon">📖</div>
          <div>
            <h2 className="panel__title">自我叙事</h2>
            <p className="panel__subtitle">近期记忆</p>
          </div>
        </div>
      </div>

      <div className="panel__content">
        {uniqueEntries.length === 0 ? (
          <div className="empty-state empty-state--small">
            <p>还没有形成自我叙事。</p>
          </div>
        ) : (
          <ul className="narrative-list">
            {uniqueEntries.map((entry) => (
              <li key={entry} className="narrative-list__item">
                {entry}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
