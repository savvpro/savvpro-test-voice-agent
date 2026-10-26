type Name =
  | "river"
  | "arrow"
  | "bag"
  | "phone"
  | "wallet"
  | "keys"
  | "mic"
  | "stop"
  | "sound"
  | "mute"
  | "check"
  | "help";
const paths: Record<Name, string> = {
  river:
    "M3 6c5-5 7 5 12 0s7 5 6 6M3 12c5-5 7 5 12 0s7 5 6 6M3 18c5-5 7 5 12 0",
  arrow: "M4 12h15m-6-6 6 6-6 6",
  bag: "M5 7h14l1 14H4L5 7Zm3 0V6a4 4 0 0 1 8 0v1",
  phone:
    "M7 2h10a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1Zm3 17h4",
  wallet: "M20 7H5a2 2 0 0 1 0-4h13v4M4 7v13h16V7m-4 5h4v4h-4v-4Z",
  keys: "M14 3a6 6 0 1 1-4 10l-7 7H1v-3l7-7a6 6 0 0 1 6-7Zm2 4h.01",
  mic: "M9 5a3 3 0 0 1 6 0v7a3 3 0 0 1-6 0V5Zm-4 6v1a7 7 0 0 0 14 0v-1M12 19v3m-4 0h8",
  stop: "M6 6h12v12H6Z",
  sound: "M3 9h4l5-4v14l-5-4H3V9Zm13-2a7 7 0 0 1 0 10m3-13a11 11 0 0 1 0 16",
  mute: "M3 9h4l5-4v14l-5-4H3V9Zm13 0 5 6m0-6-5 6",
  check: "m5 12 4 4L19 6",
  help: "M9 8a3 3 0 1 1 5 2c-2 1-2 2-2 3m0 4h.01M22 12A10 10 0 1 1 2 12a10 10 0 0 1 20 0Z",
};
export function Icon({ name, size = 20 }: { name: Name; size?: number }) {
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={paths[name]} />
    </svg>
  );
}
