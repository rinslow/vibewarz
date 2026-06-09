"use client";

import { type ReactNode } from "react";

// The three social-media aspect ratios replays support. Each game renders its
// board natively at one of these (its `nativeRatio`), so the default replay is
// already perfectly framed; the viewer can re-frame into the others.
export type AspectRatio = "9:16" | "16:9" | "1:1";

export const ASPECT_RATIOS: AspectRatio[] = ["16:9", "9:16", "1:1"];

const RATIO_CLASS: Record<AspectRatio, string> = {
  "16:9": "vw-frame--16x9",
  "9:16": "vw-frame--9x16",
  "1:1": "vw-frame--1x1",
};

const RATIO_GLYPH: Record<AspectRatio, string> = {
  "16:9": "▭",
  "9:16": "▯",
  "1:1": "◻",
};

// A fixed-aspect stage that meet-fits the game board inside it. When `ratio`
// equals the board's `nativeRatio` the board fills edge-to-edge with no bands;
// otherwise it centers on a branded backdrop. A wordmark (plus optional `brand`
// node) overlays a corner in every case so captured clips are branded.
export function ReplayFrame({
  ratio,
  nativeRatio,
  brand,
  children,
}: {
  ratio: AspectRatio;
  // The board's intrinsic ratio. Accepted for clarity and as the seam for any
  // future per-ratio framing (e.g. crop instead of letterbox); rendering is
  // uniform meet-fit, so a matching ratio fills exactly with no extra logic.
  nativeRatio: AspectRatio;
  brand?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={`vw-frame ${RATIO_CLASS[ratio]}`} data-native-ratio={nativeRatio}>
      <div className="vw-frame__stage">{children}</div>
      <div className="vw-frame__brand">
        {brand}
        <span className="vw-replay__wordmark">vibewarz</span>
      </div>
    </div>
  );
}

export function AspectSelect({
  value,
  options = ASPECT_RATIOS,
  onChange,
}: {
  value: AspectRatio;
  options?: AspectRatio[];
  onChange: (ratio: AspectRatio) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as AspectRatio)}
      className="vw-replay__speed"
      aria-label="aspect ratio"
    >
      {options.map((r) => (
        <option key={r} value={r}>
          {RATIO_GLYPH[r]} {r}
        </option>
      ))}
    </select>
  );
}
