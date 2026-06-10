"use client";

import { type Dispatch, type SetStateAction, useEffect, useRef, useState } from "react";

const SPEEDS = [0.25, 0.5, 1, 2, 4, 8] as const;

export type PlaybackState = {
  frame: number;
  setFrame: Dispatch<SetStateAction<number>>;
  playing: boolean;
  setPlaying: Dispatch<SetStateAction<boolean>>;
  speed: number;
  setSpeed: Dispatch<SetStateAction<number>>;
};

// Per-game live tick cadence. Mirrors `game.meta.tick_interval_ms` in the
// engines:
//   curve: 50ms tick  → 20 Hz
//   blast: 100ms tick → 10 Hz
//   poker: 0ms tick (event-paced, no wall-clock floor) → we pick a
//   readable replay cadence; one action per ~500ms feels natural for
//   turn-based playback.
// "1×" speed should make replay playback match what a human watching live
// would have seen, which is what the engine cadence defines — so each
// renderer passes its own constant here instead of inheriting a single
// global default.
export function usePlayback(
  totalFrames: number,
  baseTicksPerSec: number,
): PlaybackState {
  const initialFrame = (() => {
    if (typeof window === "undefined") return 0;
    const t = new URL(window.location.href).searchParams.get("t");
    if (!t) return 0;
    const n = parseInt(t, 10);
    if (Number.isNaN(n)) return 0;
    return Math.max(0, Math.min(Math.max(0, totalFrames - 1), n));
  })();

  const [frame, setFrame] = useState(initialFrame);
  const [playing, setPlaying] = useState(initialFrame === 0 && totalFrames > 1);
  const [speed, setSpeed] = useState<number>(1);

  const lastTickAdvance = useRef<number>(0);
  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const step = (ts: number) => {
      if (!lastTickAdvance.current) lastTickAdvance.current = ts;
      const elapsed = ts - lastTickAdvance.current;
      const tickMs = 1000 / (baseTicksPerSec * speed);
      if (elapsed >= tickMs) {
        const steps = Math.floor(elapsed / tickMs);
        lastTickAdvance.current = ts;
        setFrame((f) => {
          const next = f + steps;
          if (next >= totalFrames - 1) {
            setPlaying(false);
            return totalFrames - 1;
          }
          return next;
        });
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, totalFrames, baseTicksPerSec]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === " ") {
        e.preventDefault();
        setPlaying((p) => !p);
      } else if (e.key === "ArrowLeft") {
        setFrame((f) => Math.max(0, f - 1));
      } else if (e.key === "ArrowRight") {
        setFrame((f) => Math.min(totalFrames - 1, f + 1));
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [totalFrames]);

  return { frame, setFrame, playing, setPlaying, speed, setSpeed };
}

// Fullscreens the replay root (frame + controls together, so the scrubber and
// ratio selector stay usable) via the Fullscreen API. The element keeps its
// chosen aspect frame — `.vw-replay:fullscreen` CSS meet-fits it to the screen.
function FullscreenButton() {
  const [active, setActive] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);

  const toggle = () => {
    if (document.fullscreenElement) {
      void document.exitFullscreen();
      return;
    }
    const root = ref.current?.closest(".vw-replay");
    if (root instanceof HTMLElement) void root.requestFullscreen?.();
  };

  useEffect(() => {
    const sync = () => setActive(!!document.fullscreenElement);
    const onKey = (e: KeyboardEvent) => {
      const t = e.target;
      if (t instanceof HTMLElement && /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)) return;
      if (e.key === "f") toggle();
    };
    document.addEventListener("fullscreenchange", sync);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("fullscreenchange", sync);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  return (
    <button
      ref={ref}
      type="button"
      onClick={toggle}
      className="vw-replay__btn-fullscreen"
      title={active ? "exit fullscreen (f)" : "fullscreen (f)"}
      aria-label={active ? "exit fullscreen" : "enter fullscreen"}
    >
      {active ? "⛶ exit" : "⛶"}
    </button>
  );
}

export function PlaybackControls({
  totalFrames,
  currentTick,
  maxTick,
  playback,
  extra,
}: {
  totalFrames: number;
  currentTick: number;
  maxTick: number;
  playback: PlaybackState;
  // Optional game-specific control (e.g. Poker POV selector) rendered next
  // to the speed dropdown.
  extra?: React.ReactNode;
}) {
  const { frame, setFrame, playing, setPlaying, speed, setSpeed } = playback;
  return (
    <div className="vw-replay__controls">
      <span className="vw-replay__wordmark">vibewarz</span>
      <button
        type="button"
        onClick={() => setPlaying((p) => !p)}
        className="vw-replay__btn-play"
      >
        {playing ? "pause" : "play"}
      </button>
      <button
        type="button"
        onClick={() => setFrame(0)}
        className="vw-replay__btn-reset"
      >
        ⏮ reset
      </button>
      <div className="vw-replay__scrubber">
        <input
          type="range"
          min={0}
          max={Math.max(0, totalFrames - 1)}
          value={frame}
          onChange={(e) => {
            setFrame(parseInt(e.target.value, 10));
            setPlaying(false);
          }}
        />
      </div>
      <div className="vw-replay__tick">
        tick {currentTick}/{maxTick}
      </div>
      <select
        value={speed}
        onChange={(e) => setSpeed(parseFloat(e.target.value))}
        className="vw-replay__speed"
      >
        {SPEEDS.map((s) => (
          <option key={s} value={s}>
            {s}×
          </option>
        ))}
      </select>
      {extra}
      <FullscreenButton />
    </div>
  );
}
