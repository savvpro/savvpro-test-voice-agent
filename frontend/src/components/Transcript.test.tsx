import { render, screen } from "@testing-library/react";
import { Transcript } from "./Transcript";

describe("Transcript", () => {
  it("renders caller and agent bubbles in order", () => {
    const { container } = render(
      <Transcript
        messages={[
          { id: 0, role: "agent", text: "Hello, how can I help?" },
          { id: 1, role: "caller", text: "Book a dentist" },
          { id: 2, role: "caller", text: "" },
        ]}
      />,
    );
    const roles = [...container.querySelectorAll(".bubble")].map((b) => b.getAttribute("data-role"));
    expect(roles).toEqual(["agent", "caller", "caller"]);
    expect(screen.getByText("Book a dentist")).toBeInTheDocument();
    expect(screen.getByText("(silence)")).toBeInTheDocument();
  });

  it("invites the user to start a call when empty", () => {
    render(<Transcript messages={[]} />);
    expect(screen.getByText(/Start call/)).toBeInTheDocument();
  });
});
