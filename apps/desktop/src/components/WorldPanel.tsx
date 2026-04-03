import type { InnerWorldState } from "../lib/api";

type WorldPanelProps = {
  world: InnerWorldState | null;
};

export function WorldPanel({ world }: WorldPanelProps) {
  return (
    <section>
      <h2>Inner World</h2>
      {world ? (
        <>
          <p>Time: {world.time_of_day}</p>
          <p>Energy: {world.energy}</p>
          <p>Mood: {world.mood}</p>
          <p>Focus: {world.focus_tension}</p>
        </>
      ) : (
        <p>World state is loading.</p>
      )}
    </section>
  );
}
