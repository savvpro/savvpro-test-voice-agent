import { describe, expect, it } from "vitest";
import { filledCount, slotRows, stateLabel } from "./labels";

const empty = { service: null, date: null, time: null, name: null, phone: null };

describe("labels", () => {
  it("knows every state and falls back to the raw name", () => {
    expect(stateLabel("confirm")).toBe("Waiting for confirmation");
    expect(stateLabel("something_new")).toBe("something_new");
  });

  it("lists the five slots in order", () => {
    expect(slotRows(empty).map((row) => row.label)).toEqual([
      "Treatment", "Date", "Time", "Patient", "Phone",
    ]);
  });

  it("counts filled slots", () => {
    expect(filledCount(empty)).toBe(0);
    expect(filledCount({ ...empty, service: "cleaning", time: "14:00" })).toBe(2);
  });
});
