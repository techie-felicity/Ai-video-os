import React from "react";
import { Composition, getInputProps } from "remotion";
import { DocumentaryComposition, SceneGraphProps, FPS, flattenShots } from "./compositions/DocumentaryComposition";

const inputProps = getInputProps() as unknown as SceneGraphProps;

const fallbackProps: SceneGraphProps = {
  title: "Untitled",
  platform: "youtube",
  brandKit: null,
  scenes: [],
};

export const RemotionRoot: React.FC = () => {
  const props = inputProps && inputProps.scenes ? inputProps : fallbackProps;
  const totalFrames = Math.max(
    FPS * 3,
    Math.round((flattenShots(props.scenes).reduce((sum, s) => sum + s.durationMs, 0) / 1000) * FPS)
  );
  // Rendering at 720p instead of 1080p roughly halves the pixel count
  // Chrome has to hold in memory per frame — this is a deliberate tradeoff
  // to fit render jobs within a constrained memory budget (e.g. Railway's
  // free tier). Bump back to 1920x1080 / 1080x1920 once more memory is
  // available.
  const dimensions = props.platform === "tiktok" || props.platform === "instagram"
    ? { width: 720, height: 1280 }
    : { width: 1280, height: 720 };

  return (
    <Composition
      id="Documentary"
      component={DocumentaryComposition}
      durationInFrames={totalFrames}
      fps={FPS}
      width={dimensions.width}
      height={dimensions.height}
      defaultProps={props}
    />
  );
};
