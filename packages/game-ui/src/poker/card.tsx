// Single playing-card SVG. Cards come from the engine as two-char strings:
// "As" (ace of spades), "Td" (ten of diamonds), etc. Rank chars are 2..9, T,
// J, Q, K, A. Suit chars are s (spades), h (hearts), d (diamonds), c (clubs).

const MONO = "ui-monospace, 'JetBrains Mono', Menlo, Consolas, monospace";

const SUIT_GLYPH: Record<string, string> = {
  s: "♠",
  h: "♥",
  d: "♦",
  c: "♣",
};

const SUIT_COLOR: Record<string, string> = {
  s: "#0a0a0b",
  c: "#0a0a0b",
  h: "#dc2626",
  d: "#dc2626",
};

export type CardSize = "sm" | "md" | "lg";

const SIZES: Record<CardSize, { w: number; h: number; rankFs: number; pipFs: number; pad: number }> = {
  sm: { w: 26, h: 38, rankFs: 11, pipFs: 13, pad: 3 },
  md: { w: 40, h: 58, rankFs: 16, pipFs: 22, pad: 4 },
  lg: { w: 56, h: 80, rankFs: 22, pipFs: 32, pad: 6 },
};

function rankDisplay(r: string): string {
  return r === "T" ? "10" : r;
}

export function Card({
  card,
  size = "md",
}: {
  card: string | null;
  size?: CardSize;
}) {
  const dims = SIZES[size];
  if (!card) {
    // Face-down: dark patterned back, matching the felt rail accent.
    return (
      <div
        style={{
          width: dims.w,
          height: dims.h,
          borderRadius: 6,
          background:
            "repeating-linear-gradient(45deg, #1e3a8a 0 4px, #1e40af 4px 8px), radial-gradient(circle at center, #1e40af, #0f172a)",
          backgroundBlendMode: "overlay",
          border: "1px solid #0f172a",
          boxShadow: "0 1px 3px rgba(0,0,0,0.6)",
        }}
      />
    );
  }
  const rank = card[0];
  const suit = card[1];
  const color = SUIT_COLOR[suit] ?? "#0a0a0b";
  const glyph = SUIT_GLYPH[suit] ?? suit;
  return (
    <div
      style={{
        width: dims.w,
        height: dims.h,
        position: "relative",
        fontFamily: MONO,
        borderRadius: 6,
        background: "linear-gradient(180deg, #fafaf9 0%, #f1f1ee 100%)",
        color,
        border: "1px solid #cbd5e1",
        padding: dims.pad,
        boxShadow: "0 2px 4px rgba(0,0,0,0.45)",
      }}
    >
      {/* Top-left rank + suit (small index) */}
      <div style={{ fontSize: dims.rankFs, lineHeight: 1, fontWeight: 700, letterSpacing: "-0.5px" }}>
        {rankDisplay(rank)}
      </div>
      <div style={{ fontSize: Math.round(dims.rankFs * 0.9), lineHeight: 1, marginTop: 1 }}>
        {glyph}
      </div>
      {/* Center pip — the suit big in the middle */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          fontSize: dims.pipFs,
          lineHeight: 1,
          opacity: 0.85,
        }}
      >
        {glyph}
      </div>
      {/* Bottom-right mirrored index */}
      <div
        style={{
          position: "absolute",
          bottom: dims.pad,
          right: dims.pad,
          fontSize: dims.rankFs,
          lineHeight: 1,
          fontWeight: 700,
          transform: "rotate(180deg)",
          letterSpacing: "-0.5px",
        }}
      >
        {rankDisplay(rank)}
      </div>
    </div>
  );
}

export function CardRow({
  cards,
  empty = 0,
  size = "md",
  gap = 6,
}: {
  cards: string[];
  empty?: number;
  size?: CardSize;
  gap?: number;
}) {
  const placeholders = Math.max(0, empty - cards.length);
  return (
    <div style={{ display: "flex", gap }}>
      {cards.map((c, i) => (
        <Card key={i} card={c} size={size} />
      ))}
      {Array.from({ length: placeholders }).map((_, i) => (
        <div
          key={`p${i}`}
          style={{
            width: SIZES[size].w,
            height: SIZES[size].h,
            borderRadius: 6,
            background: "rgba(255,255,255,0.03)",
            border: "1px dashed rgba(255,255,255,0.08)",
          }}
        />
      ))}
    </div>
  );
}
