import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  interpolate,
  Img,
  Audio,
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
  assetUri: string | null;
  motionParams: Record<string, any>;
  audioCues: Record<string, any>;
  subtitleParams: Record<string, any>;
  captionText: string;
};

export type SceneNode = {
  order: number;
  scriptText: string;
  shots: Shot[];
};

export type SceneGraphProps = {
  title: string;
  platform: string;
  narrationAudioUri: string | null;
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
 * Real assets: shots with a resolved `assetUri` (currently: stock images via
 * Pexels) render as actual <Img>. Anything without a resolved asset yet
 * (charts, maps, ai_image, etc. — not wired to a provider yet) falls back to
 * <AssetPlaceholder> so a single missing provider doesn't break the render.
 * Narration is a single uploaded voiceover file spanning the whole video
 * (see providers.py / orchestrator._rescale_to_narration) — not generated
 * per-scene. Captions are sliced per-shot proportionally from that upload's
 * real duration, not the whole scene's script text anymore.
 */
export const DocumentaryComposition: React.FC<SceneGraphProps> = ({ scenes, brandKit, narrationAudioUri }) => {
  let frameCursor = 0;
  const accent = brandKit?.accentColor ?? "#FF4D00";

  const shotSequences = scenes.flatMap((scene) =>
    scene.shots.map((shot) => {
      const from = frameCursor;
      const durationInFrames = msToFrames(shot.durationMs);
      frameCursor += durationInFrames;
      return (
        <Sequence key={`${scene.order}-${shot.order}`} from={from} durationInFrames={durationInFrames}>
          <ShotRenderer shot={shot} accent={accent} />
        </Sequence>
      );
    })
  );
  const totalDurationInFrames = frameCursor;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {narrationAudioUri && (
        <Sequence from={0} durationInFrames={totalDurationInFrames}>
          <Audio src={narrationAudioUri} />
        </Sequence>
      )}
      {shotSequences}
    </AbsoluteFill>
  );
};

const ShotRenderer: React.FC<{ shot: Shot; accent: string }> = ({ shot, accent }) => {
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
        {shot.assetUri ? (
          <Img src={shot.assetUri} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <AssetPlaceholder shot={shot} />
        )}
      </AbsoluteFill>
      <Captions text={shot.captionText} params={shot.subtitleParams} accent={accent} />
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
