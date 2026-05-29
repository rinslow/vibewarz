---
"@vibewarz/game-ui": minor
---

game-ui: identify the local player ("YOU") by consistent seat color instead of
a separate marker. `BlastReplay` and `CurveReplay` now accept an optional
`mySeat` prop — when set, the viewer's seat row (and the Blast HUD card) is
tinted with that seat's color so "this is me" reads from color alone. Removes
the faint Blast "this is you" halo and the muted lowercase "you" HUD label in
favor of pure color matching. Spectator views (`mySeat` omitted / null) render
unchanged.
