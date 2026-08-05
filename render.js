#!/usr/bin/env node
/**
 * Called by backend/app/routers/render.py as:
 *   node render.js --props <scene-graph.json> --output <final.mp4>
 *
 * Pipeline:
 *   1. Remotion renders the composition to a silent MP4 from the Scene Graph JSON.
 *   2. FFmpeg does the final pass: mux in narration/music (once TTS/music assets
 *      are wired via providers.py), loudness-normalize, and encode for the
 *      target platform's aspect ratio (already baked into composition dimensions).
 *
 * This file intentionally keeps step 2 minimal (just re-encode/copy) until
 * AudioAgent's cues are resolved to real audio asset URIs — extend the
 * ffmpeg filter graph there to add music ducking, SFX, and narration mixing.
 */
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

function parseArgs() {
  const args = process.argv.slice(2);
  const out = {};
  for (let i = 0; i < args.length; i += 2) {
    out[args[i].replace(/^--/, "")] = args[i + 1];
  }
  return out;
}

async function main() {
  const { props, output } = parseArgs();
  if (!props || !output) {
    console.error("Usage: node render.js --props <path.json> --output <path.mp4>");
    process.exit(1);
  }

  const rawFrames = path.join(path.dirname(output), `${path.basename(output, ".mp4")}-raw.mp4`);

  console.log("[render-engine] Rendering composition with Remotion...");
  execSync(
    `npx remotion render src/index.ts Documentary "${rawFrames}" --props="${props}"`,
    { stdio: "inherit", cwd: __dirname }
  );

  console.log("[render-engine] Mastering with FFmpeg...");
  // Placeholder mastering pass: normalize loudness, ensure faststart for web
  // playback. Extend this with -filter_complex audio mixing once narration/
  // music asset URIs are available on the scene graph.
  execSync(
    `ffmpeg -y -i "${rawFrames}" -af loudnorm -movflags +faststart -c:v copy "${output}"`,
    { stdio: "inherit" }
  );

  fs.unlinkSync(rawFrames);
  console.log(`[render-engine] Done -> ${output}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
