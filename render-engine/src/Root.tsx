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
  const dimensions = props.platform === "tiktok" || props.platform === "instagram"
    ? { width: 1080, height: 1920 }
    : { width: 1920, height: 1080 };

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
