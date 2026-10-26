import { rmSync } from "node:fs";
export default async function setup() {
  return async () => {
    if (process.env.MEZBAN_TEST_DB)
      rmSync(process.env.MEZBAN_TEST_DB, { force: true });
  };
}
