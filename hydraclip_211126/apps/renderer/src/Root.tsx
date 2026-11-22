import React from "react";
import { Composition } from "remotion";
import {
  HydraClipShort,
  calculateMetadata,
  defaultProps,
  type HydraClipProps,
} from "./HydraClipShort";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="HydraClipShort"
      component={HydraClipShort}
      durationInFrames={900}
      fps={30}
      width={1080}
      height={1920}
      defaultProps={defaultProps as HydraClipProps}
      calculateMetadata={calculateMetadata}
    />
  );
};
