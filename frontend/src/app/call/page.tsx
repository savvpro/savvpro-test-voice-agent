import type { Metadata } from "next";
import { CallConsole } from "@/components/call/CallConsole";

export const metadata: Metadata = {
  title: "Call the clinic · Brightside Voice",
  description: "Talk to the Brightside Dental phone assistant and see what it decided on every turn.",
};

export default function CallPage() {
  return <CallConsole />;
}
