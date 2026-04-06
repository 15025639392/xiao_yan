import { EmptyState } from "./ui/EmptyState";
import { Panel } from "./ui/Panel";

type AutobioPanelProps = { entries: string[] };

export function AutobioPanel({ entries }: AutobioPanelProps) {
  const uniqueEntries = Array.from(new Set(entries));

  return (
    <Panel icon="📖" title="自我叙事" subtitle="近期记忆">
      {uniqueEntries.length === 0 ? (
        <EmptyState size="small">
          <p>还没有形成自我叙事。</p>
        </EmptyState>
      ) : (
        <ul className="narrative-list">
          {uniqueEntries.map((entry) => (
            <li key={entry} className="narrative-list__item">
              {entry}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
