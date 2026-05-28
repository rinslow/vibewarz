// Visual primitives: a stack of betting chips with a label, and a tiny
// dealer-button disc. These are the at-table indicators; they sit in front
// of each seat (chips) or beside the button-holder (dealer disc).

const MONO = "ui-monospace, 'JetBrains Mono', Menlo, Consolas, monospace";

export function ChipStack({ amount }: { amount: number }) {
  if (amount <= 0) return null;
  // Pick a chip color by denomination, mostly cosmetic.
  const tier =
    amount >= 500 ? "#dc2626" : amount >= 100 ? "#10b981" : amount >= 25 ? "#3b82f6" : "#f59e0b";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        fontFamily: MONO,
        fontSize: 12,
        background: "rgba(0,0,0,0.45)",
        border: "1px solid rgba(255,255,255,0.06)",
        borderRadius: 999,
        padding: "2px 8px 2px 4px",
        boxShadow: "0 2px 6px rgba(0,0,0,0.4)",
      }}
    >
      <span
        style={{
          width: 14,
          height: 14,
          borderRadius: 999,
          background: `radial-gradient(circle at 30% 30%, ${tier}, ${tier}aa)`,
          border: `1.5px dashed rgba(255,255,255,0.85)`,
          boxShadow: "0 0 0 1px rgba(0,0,0,0.5)",
        }}
      />
      <span style={{ color: "#fff" }}>{amount}</span>
    </div>
  );
}

export function DealerButton() {
  return (
    <div
      title="dealer"
      style={{
        width: 22,
        height: 22,
        borderRadius: 999,
        background: "radial-gradient(circle at 30% 30%, #ffffff, #d4d4d4)",
        color: "#0a0a0b",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: MONO,
        fontSize: 11,
        fontWeight: 800,
        border: "1px solid #525252",
        boxShadow: "0 2px 4px rgba(0,0,0,0.6)",
      }}
    >
      D
    </div>
  );
}
