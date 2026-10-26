import { render, screen, within } from "@testing-library/react";
import { bookingTurn } from "../test/fixtures";
import { BrainPanel } from "./BrainPanel";

describe("BrainPanel", () => {
  it("shows intent, confidence, source and the top 3 alternatives", () => {
    render(<BrainPanel turn={bookingTurn} />);
    expect(screen.getByText("book_appointment", { selector: ".intent" })).toBeInTheDocument();
    expect(screen.getByText("ml")).toHaveClass("source-ml");
    expect(screen.getByRole("meter", { name: "confidence" })).toHaveAttribute("aria-valuenow", "87");
    const alternatives = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(alternatives).toEqual(["book_appointment 0.87", "inform 0.08", "check_availability 0.03"]);
  });

  it("shows only the entities that were found, plus state, frame and timings", () => {
    const { container } = render(<BrainPanel turn={bookingTurn} />);
    const entities = container.querySelectorAll(".row.top")[1];
    expect(within(entities as HTMLElement).getByText("department")).toBeInTheDocument();
    expect(within(entities as HTMLElement).getByText("morning")).toBeInTheDocument();
    expect(within(entities as HTMLElement).queryByText("phone")).toBeNull();
    expect(screen.getByText("OFFER_SLOTS")).toBeInTheDocument();
    expect(screen.getByText("STT 412.3 ms")).toBeInTheDocument();
  });

  it("explains itself before the first turn", () => {
    render(<BrainPanel turn={null} />);
    expect(screen.getByText(/intent, entities and dialogue state/)).toBeInTheDocument();
  });
});
