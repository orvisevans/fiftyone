/**
 * Copyright 2017-2021, Voxel51, Inc.
 */

import {
  DASH_COLOR,
  DASH_LENGTH,
  MASK_ALPHA,
  SELECTED_MASK_ALPHA,
} from "../constants";
import { BaseState, Coordinates } from "../state";
import { distanceFromLineSegment } from "../util";
import { CONTAINS, CoordinateOverlay, PointInfo, RegularLabel } from "./base";
import { t } from "./util";

interface PolylineLabel extends RegularLabel {
  points: Coordinates[][];
  closed: boolean;
  filled: boolean;
}

export default class PolylineOverlay<
  State extends BaseState
> extends CoordinateOverlay<State, PolylineLabel> {
  constructor(field: string, label: PolylineLabel) {
    super(field, label);
  }

  containsPoint(state: Readonly<State>): CONTAINS {
    return CONTAINS.NONE;
  }

  draw(ctx: CanvasRenderingContext2D, state: Readonly<State>) {
    const color = this.getColor(state);
    const selected = this.isSelected(state);

    for (const path of this.label.points) {
      if (path.length < 2) {
        continue;
      }

      if (selected) {
        this.strokePath(ctx, state, path, DASH_COLOR, false, false);
      }

      this.strokePath(
        ctx,
        state,
        path,
        color,
        this.label.filled,
        selected,
        DASH_LENGTH
      );
    }
  }

  getMouseDistance(state: Readonly<State>): number {
    const distances = [];
    const [w, h] = state.config.dimensions;
    for (const shape of this.label.points) {
      for (let i = 0; i < shape.length - 1; i++) {
        distances.push(
          distanceFromLineSegment(
            state.pixelCoordinates,
            [w * shape[i][0], h * shape[i][1]],
            [w * shape[i + 1][0], h * shape[i + 1][1]]
          )
        );
      }
      // acheck final line segment if closed
      if (this.label.closed) {
        distances.push(
          distanceFromLineSegment(
            state.pixelCoordinates,
            [w * shape[0][0], h * shape[0][1]],
            [w * shape[shape.length - 1][0], h * shape[shape.length - 1][1]]
          )
        );
      }
    }
    return Math.min(...distances);
  }

  getPointInfo(state: Readonly<State>): PointInfo {
    return {
      field: this.field,
      label: this.label,
      type: "Polyline",
      color: this.getColor(state),
    };
  }

  getPoints(): Coordinates[] {
    return getPolylinePoints([this.label]);
  }

  private strokePath(
    ctx: CanvasRenderingContext2D,
    state: Readonly<State>,
    path: Coordinates[],
    color: string,
    filled: boolean,
    selected: boolean,
    dash?: number
  ) {
    ctx.beginPath();
    ctx.lineWidth = state.strokeWidth;
    ctx.strokeStyle = color;
    ctx.setLineDash(dash ? [dash] : []);
    ctx.moveTo(...t(state, path[0][0], path[0][1]));
    for (const [x, y] of path.slice(1)) {
      ctx.lineTo(...t(state, x, y));
    }
    if (filled) {
      ctx.fillStyle = color;
      ctx.globalAlpha = selected ? SELECTED_MASK_ALPHA : MASK_ALPHA;
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    if (this.label.closed) {
      ctx.closePath();
    }
    ctx.stroke();
  }
}

export const getPolylinePoints = (labels: PolylineLabel[]): Coordinates[] => {
  let points = [];
  labels.forEach((label) => {
    label.points.forEach((line) => {
      points = [...points, ...line];
    });
  });
  return points;
};
