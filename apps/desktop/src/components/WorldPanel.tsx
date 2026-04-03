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
          {world.focus_stage && world.focus_stage !== "none" ? (
            <p>Phase: {world.focus_stage}</p>
          ) : null}
          {world.focus_step ? <p>Step: {world.focus_step}</p> : null}
          {world.latest_event ? <p>Latest Event: {world.latest_event}</p> : null}
        </>
      ) : (
        <p>World state is loading.</p>
      )}
    </section>
  );
}
