import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Composer } from "./Composer";

function stubMicrophone(getUserMedia: () => Promise<MediaStream>) {
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
  vi.stubGlobal("MediaRecorder", Object.assign(function () {}, { isTypeSupported: () => true }));
}

afterEach(() => vi.unstubAllGlobals());

describe("Composer", () => {
  it("shows a clear error when microphone permission is denied", async () => {
    stubMicrophone(() => Promise.reject(new DOMException("Permission denied", "NotAllowedError")));
    render(<Composer disabled={false} onAudio={vi.fn()} onText={vi.fn()} />);
    fireEvent.pointerDown(screen.getByRole("button", { name: "Hold to talk" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Microphone permission was denied/);
    // the text fallback still works
    expect(screen.getByRole("textbox", { name: "Type a message" })).toBeEnabled();
  });

  it("sends typed text and clears the box", async () => {
    const onText = vi.fn();
    render(<Composer disabled={false} onAudio={vi.fn()} onText={onText} />);
    const box = screen.getByRole("textbox", { name: "Type a message" });
    await userEvent.type(box, "  where are you located  {enter}");
    expect(onText).toHaveBeenCalledWith("where are you located");
    expect(box).toHaveValue("");
  });
});
