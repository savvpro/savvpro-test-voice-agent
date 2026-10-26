import type { SessionView } from "../../api/client";

export function DecisionInspector({
  session,
}: {
  session: SessionView | null;
}) {
  return (
    <details className="inspector">
      <summary>How the assistant decided</summary>
      <div className="inspector-content">
        <p>
          Decisions come from explicit Python rules. Matching points express
          similarity, not the probability of ownership.
        </p>
        {session && (
          <>
            <dl>
              <div>
                <dt>Conversation state</dt>
                <dd>{session.state}</dd>
              </div>
              <div>
                <dt>Rule applied</dt>
                <dd>{session.trace.rule}</dd>
              </div>
              <div>
                <dt>Turn version</dt>
                <dd>{session.version}</dd>
              </div>
            </dl>
            <p>{session.trace.explanation}</p>
            {session.candidates.map((candidate) => (
              <div className="score-row" key={candidate.label}>
                <span>{candidate.label}</span>
                <span>{candidate.score} / 100 points</span>
                <p>
                  {Object.entries(candidate.signals)
                    .map(
                      ([name, score]) =>
                        `${name.replace("_", " ")} ${score > 0 ? "+" : ""}${score}`,
                    )
                    .join(" · ")}
                </p>
              </div>
            ))}
          </>
        )}
      </div>
    </details>
  );
}
