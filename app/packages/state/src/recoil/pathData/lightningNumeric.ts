import { selectorFamily } from "recoil";
import { lightningQuery } from "../queryPerformance";

export const lightningNumericResults = selectorFamily({
  key: "lightningNumericResults",
  get:
    (path: string) =>
    ({ get }) => {
      const [data] = get(lightningQuery([{ path }]));

      if (data.__typename === "DateLightningResult") {
        return {
          max: data.dateMax,
          min: data.dateMin,
        };
      }

      if (data.__typename === "DateTimeLightningResult") {
        return {
          max: data.datetimeMax,
          min: data.datetimeMin,
        };
      }

      if (data.__typename === "IntLightningResult") {
        return {
          max: data.intMax,
          min: data.intMin,
        };
      }

      if (data.__typename === "FloatLightningResult") {
        return data;
      }

      throw new Error(
        `unexpected ${data.__typename} for path '${path}' in lightningNumericResults`
      );
    },
});

export const lightningBounds = selectorFamily<[number, number] | null, string>({
  key: "lightningBounds",
  get:
    (path) =>
    ({ get }) => {
      const data = get(lightningNumericResults(path));

      if (typeof data.max !== "number" || typeof data.min !== "number") {
        return null;
      }

      return [data.min, data.max];
    },
});

export const lightningNonfinites = selectorFamily({
  key: "lightningNonfinites",
  get:
    (path: string) =>
    ({ get }) => {
      const [data] = get(lightningQuery([{ path }]));
      if (data.__typename === "FloatLightningResult") {
        return {
          inf: data.inf,
          nan: data.nan,
          ninf: data.ninf,
        };
      }

      return {};
    },
});
