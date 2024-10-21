import * as fos from "@fiftyone/state";
import { formatPrimitive } from "@fiftyone/utilities";
import React from "react";
import { useRecoilValue } from "recoil";
import styled from "styled-components";
import RangeSlider from "../../Common/RangeSlider";
import FieldLabelAndInfo from "../../FieldLabelAndInfo";
import Boxes from "./Boxes";
import FilterOption from "./FilterOption";
import Nonfinites from "./Nonfinites";
import Reset from "./Reset";
import * as state from "./state";

const NamedRangeSliderContainer = styled.div`
  margin: 3px;
  font-weight: bold;
`;

const NamedRangeSliderHeader = styled.div`
  display: flex;
  justify-content: space-between;
`;

const RangeSliderContainer = styled.div`
  background: ${({ theme }) => theme.background.level2};
  border: 1px solid var(--fo-palette-divider);
  border-radius: 2px;
  color: ${({ theme }) => theme.text.secondary};
  margin-top: 0.25rem;
  padding: 0.25rem 0.5rem;
`;

type Props = {
  color: string;
  modal: boolean;
  named?: boolean;
  onFocus?: () => void;
  onBlur?: () => void;
  path: string;
};

const NumericFieldFilter = ({ color, modal, named = true, path }: Props) => {
  const name = path.split(".").slice(-1)[0];
  const ftype = useRecoilValue(fos.fieldType({ path }));
  const field = fos.useAssertedRecoilValue(fos.field(path));
  const hasBounds = useRecoilValue(state.hasBounds({ path, modal }));
  const indexed = useRecoilValue(fos.pathHasIndexes(path));
  const queryPerformance = useRecoilValue(fos.queryPerformance);

  const key = path.replace(/[ ,.]/g, "-");
  const excluded = useRecoilValue(fos.numericExcludeAtom({ modal, path }));
  const defaultRange = useRecoilValue(state.hasDefaultRange({ modal, path }));
  const one = useRecoilValue(state.oneBound({ path, modal }));
  const timeZone = useRecoilValue(fos.timeZone);

  if (queryPerformance && !indexed) {
    return <Boxes />;
  }

  if (named && !hasBounds) {
    return null;
  }

  return (
    <NamedRangeSliderContainer onClick={(e) => e.stopPropagation()}>
      {named && name && (
        <FieldLabelAndInfo
          nested
          field={field}
          color={color}
          template={({ label, hoverTarget }) => (
            <NamedRangeSliderHeader>
              <span ref={hoverTarget}>{label}</span>
            </NamedRangeSliderHeader>
          )}
        />
      )}
      <RangeSliderContainer
        onMouseDown={(e) => e.stopPropagation()}
        style={{ cursor: "default" }}
        data-cy={`numeric-slider-container-${key}`}
      >
        {hasBounds &&
          !(excluded && defaultRange) &&
          (one !== null ? (
            formatPrimitive({ ftype, timeZone, value: one })?.toString()
          ) : (
            <RangeSlider
              showBounds={false}
              fieldType={ftype}
              valueAtom={fos.rangeAtom({
                modal,
                path,
                withBounds: true,
              })}
              boundsAtom={fos.boundsAtom({
                path,
                modal,
              })}
              color={color}
            />
          ))}
        {defaultRange && <Nonfinites modal={modal} path={path} />}
        <FilterOption color={color} modal={modal} path={path} />
        <Reset color={color} modal={modal} path={path} />
        {!indexed && !hasBounds && "No results"}
      </RangeSliderContainer>
    </NamedRangeSliderContainer>
  );
};

export default NumericFieldFilter;
