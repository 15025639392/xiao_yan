type AutobioPanelProps = {
  entries: string[];
};

export function AutobioPanel({ entries }: AutobioPanelProps) {
  const uniqueEntries = Array.from(new Set(entries));

  return (
    <section>
      <h2>Self Narrative</h2>
      {uniqueEntries.length === 0 ? (
        <p>No autobiographical reflection yet.</p>
      ) : (
        <ul>
          {uniqueEntries.map((entry) => (
            <li key={entry}>{entry}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
