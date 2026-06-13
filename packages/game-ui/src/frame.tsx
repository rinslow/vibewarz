"use client";

import { type CSSProperties, type ReactNode } from "react";

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

const RATIO_VALUE: Record<AspectRatio, number> = {
  "16:9": 16 / 9,
  "9:16": 9 / 16,
  "1:1": 1,
};

// A fixed-aspect stage that meet-fits the game board inside it. When `ratio`
// equals the board's `nativeRatio` the board fills edge-to-edge with no bands;
// otherwise it centers on a branded backdrop. A wordmark (plus optional `brand`
// node) overlays a corner in every case so captured clips are branded.
//
// When re-framed off the native ratio the letterbox bands are dead space, so an
// optional `legend` fills them — placed where attention/social safe-zones favor
// it: the LEFT band when the frame is wider than native (pillarbox; LTR reading
// enters top-left, the right band is the low-attention "fallow" zone), or the
// TOP band when it's taller (letterbox; the bottom is the platform caption /
// action-button clutter zone on TikTok/Reels/Shorts).
export function ReplayFrame({
  ratio,
  nativeRatio,
  brand,
  legend,
  children,
}: {
  ratio: AspectRatio;
  // The board's intrinsic ratio. Drives where the dead-space bands fall (and so
  // where `legend` is placed); rendering is uniform meet-fit, so a matching
  // ratio fills exactly with no extra logic.
  nativeRatio: AspectRatio;
  brand?: ReactNode;
  // Optional roster/legend shown in the letterbox band(s) when re-framed off the
  // native ratio (never in native, where there are no bands).
  legend?: ReactNode;
  children: ReactNode;
}) {
  const band =
    ratio === nativeRatio
      ? undefined
      : RATIO_VALUE[ratio] > RATIO_VALUE[nativeRatio]
        ? "side"
        : "block";

  // Place the legend in the MIDDLE of the letterbox band (between the board edge
  // and the frame edge), not pinned to the edge. The board is meet-fit centered,
  // so each band spans a `bandFrac` of the frame along the band's axis (width for
  // side bands, height for block bands); expose its center + size as CSS vars so
  // the stylesheet positions the legend generally, for any game's native ratio.
  let legendStyle: CSSProperties | undefined;
  if (band) {
    const boardFrac =
      band === "side"
        ? RATIO_VALUE[nativeRatio] / RATIO_VALUE[ratio] // board width / frame width
        : RATIO_VALUE[ratio] / RATIO_VALUE[nativeRatio]; // board height / frame height
    const bandFrac = (1 - boardFrac) / 2;
    legendStyle = {
      "--vw-band-center": `${((bandFrac / 2) * 100).toFixed(3)}%`,
      "--vw-band-size": `${(bandFrac * 100).toFixed(3)}%`,
    } as CSSProperties;
  }

  return (
    <div
      className={`vw-frame ${RATIO_CLASS[ratio]}`}
      data-native-ratio={nativeRatio}
      data-band={band}
    >
      <div className="vw-frame__stage">{children}</div>
      {band && legend && (
        <div className="vw-frame__legend" style={legendStyle}>
          {legend}
        </div>
      )}
      <div className="vw-frame__brand">
        <span className="vw-replay__wordmark">vibewarz</span>
        {brand}
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
