import { copyFileSync } from "node:fs";
import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm", "cjs"],
  dts: true,
  sourcemap: true,
  clean: true,
  external: ["react", "react-dom"],
  // Ship styles.css as a sibling of the JS bundles. Consumers opt in with
  //   import "@vibewarz/game-ui/styles.css";
  // — keeping it out of the JS entry means the library stays tree-shakable
  // and doesn't accidentally inject CSS into apps that don't want it.
  async onSuccess() {
    copyFileSync("src/styles.css", "dist/styles.css");
  },
});
