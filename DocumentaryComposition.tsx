import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  interpolate,
  Img,
  staticFile,
} from "remotion";

export const FPS = 30;

export type Shot = {
  order: number;
  durationMs: number;
  cameraMove: string;
  transitionIn: string;
  assetType: string | null;
  assetSpec: Record<string, any>;
  motionParams: Record<string, any>;
  audioCues: Record<string, any>;
  subtitleParams: Record<string, any>;
};

export type SceneNode = {
  order: number;
  scriptText: string;
  shots: Shot[];
};

export type SceneGraphProps = {
  title: string;
  platform: string;
  brandKit: { primaryColor: string; accentColor: string; fontHeading: string } | null;
  scenes: SceneNode[];
};

export function flattenShots(scenes: SceneNode[]): Shot[] {
  return scenes.flatMap((s) => s.shots);
}

const msToFrames = (ms: number) => Math.round((ms / 1000) * FPS);

/**
 * Renders every shot in sequence, driven purely by the Scene Graph JSON
 * produced by the agent pipeline — no hardcoded content. This is the
 * mechanical "last step": all creative decisions already happened upstream
 * in ScriptAgent/EditorAgent/StoryboardAgent/VisualAgent/MotionAgent.
 *
 * Asset rendering here is intentionally a placeholder (colored panel + spec
 * label) until VisualAgent's fetch/generate calls (providers.py) are wired
 * to real media — swap <AssetPlaceholder> for an <Img>/<Video> once
 * shot.assetSpec resolves to a real asset URI on the Shot model.
 */
export const DocumentaryComposition: React.FC<SceneGraphProps> = ({ scenes, brandKit }) => {
  let frameCursor = 0;
  const accent = brandKit?.accentColor ?? "#FF4D00";

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {scenes.flatMap((scene) =>
        scene.shots.map((shot) => {
          const from = frameCursor;
          const durationInFrames = msToFrames(shot.durationMs);
          frameCursor += durationInFrames;
          return (
            <Sequence key={`${scene.order}-${shot.order}`} from={from} durationInFrames={durationInFrames}>
              <ShotRenderer shot={shot} captionSource={scene.scriptText} accent={accent} />
            </Sequence>
          );
        })
      )}
    </AbsoluteFill>
  );
};

const ShotRenderer: React.FC<{ shot: Shot; captionSource: string; accent: string }> = ({
  shot,
  captionSource,
  accent,
}) => {
  const frame = useCurrentFrame();
  const durationInFrames = msToFrames(shot.durationMs);
  const progress = durationInFrames > 0 ? frame / durationInFrames : 0;

  const zoomStart = shot.motionParams?.zoom_start ?? 1.0;
  const zoomEnd = shot.motionParams?.zoom_end ?? 1.0;
  const scale = interpolate(progress, [0, 1], [zoomStart, zoomEnd]);

  const panX = shot.motionParams?.pan_x ?? 0;
  const panY = shot.motionParams?.pan_y ?? 0;
  const translateX = interpolate(progress, [0, 1], [0, panX]);
  const translateY = interpolate(progress, [0, 1], [0, panY]);

  const opacity =
    shot.transitionIn === "crossfade"
      ? interpolate(frame, [0, 8], [0, 1], { extrapolateRight: "clamp" })
      : 1;

  return (
    <AbsoluteFill style={{ opacity }}>
      <AbsoluteFill
        style={{
          transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
        }}
      >
        <AssetPlaceholder shot={shot} />
      </AbsoluteFill>
      <Captions text={captionSource} params={shot.subtitleParams} accent={accent} />
    </AbsoluteFill>
  );
};

const AssetPlaceholder: React.FC<{ shot: Shot }> = ({ shot }) => (
  <AbsoluteFill
    style={{
      backgroundColor: "#151515",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color: "#666",
      fontFamily: "Inter, sans-serif",
      fontSize: 28,
      textAlign: "center",
      padding: 40,
    }}
  >
    <div>
      <div style={{ fontSize: 16, letterSpacing: 2, textTransform: "uppercase", marginBottom: 12 }}>
        {shot.assetType ?? "asset"}
      </div>
      <div>{JSON.stringify(shot.assetSpec)}</div>
    </div>
  </AbsoluteFill>
);

const Captions: React.FC<{ text: string; params: Record<string, any>; accent: string }> = ({
  text,
  params,
  accent,
}) => (
  <div
    style={{
      position: "absolute",
      bottom: 80,
      width: "100%",
      textAlign: "center",
      fontFamily: params?.font ?? "Inter, sans-serif",
      fontSize: 44,
      fontWeight: 700,
      color: "#fff",
      textShadow: "0 2px 12px rgba(0,0,0,0.8)",
      padding: "0 80px",
    }}
  >
    <span style={{ color: params?.highlight_color ?? accent }}>{text}</span>
  </div>
);
