import {
  VibelordsAssetSheet,
  VibelordsReplay,
  BlastReplay,
  CurveReplay,
  PokerReplay,
  RockPaperScissorsReplay,
  detectGameId,
  type RawReplay,
} from "@vibewarz/game-ui";
import "@vibewarz/game-ui/styles.css";
import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";

function App() {
  const [replay, setReplay] = useState<RawReplay | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // The match_id is passed in the query string for parity with how the
    // platform's /replays/{id} pages work, but the Python CLI server actually
    // serves the replay envelope from a single endpoint (/replay.json) — the
    // ID is just for the title bar. If a server ever decides to multiplex
    // multiple replays on one port, /replay.json could become
    // /replay/{id}.json without any client-side changes here.
    fetch("/replay.json")
      .then((r) => {
        if (!r.ok) throw new Error(`http ${r.status}`);
        return r.json();
      })
      .then((d) => setReplay(d as RawReplay))
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : String(e));
      });
  }, []);

  if (error) {
    return (
      <div className="vw-app__error vw-app__error--err">
        Failed to load replay: {error}
      </div>
    );
  }
  if (!replay) {
    return <div className="vw-app__error">loading…</div>;
  }

  const game = detectGameId(replay);
  const names = (
    replay.events.find((e) => e.type === "game_start") as
      | { names?: Record<string, string> }
      | undefined
  )?.names;
  const matchup = names
    ? Object.entries(names)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([, n]) => n)
        .join(" vs ")
    : null;
  return (
    <>
      <p className="vw-app__title">
        <strong>{matchup ?? replay.match_id}</strong> · {game ?? "(unknown)"} ·{" "}
        {replay.events.length} events
      </p>
      {game === "curve" ? (
        <CurveReplay events={replay.events} />
      ) : game === "vibelords" ? (
        <VibelordsReplay events={replay.events} />
      ) : game === "blast" ? (
        <BlastReplay events={replay.events} />
      ) : game === "poker" ? (
        <PokerReplay events={replay.events} />
      ) : game === "rock-paper-scissors" ? (
        <RockPaperScissorsReplay events={replay.events} />
      ) : (
        <div className="vw-app__error">
          Replay loaded ({replay.events.length} events), but no renderer is
          registered for game "{game ?? "(unknown)"}".
        </div>
      )}
    </>
  );
}

const root = document.getElementById("root");
if (!root) throw new Error("missing #root");
const showAssets =
  typeof window !== "undefined" &&
  new URLSearchParams(window.location.search).has("assets");
createRoot(root).render(
  <StrictMode>{showAssets ? <VibelordsAssetSheet /> : <App />}</StrictMode>,
);
