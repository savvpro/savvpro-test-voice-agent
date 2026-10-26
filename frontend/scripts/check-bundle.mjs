import { readdir, readFile } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import path from "node:path";

const directory = path.resolve(import.meta.dirname, "../dist/assets");
const scripts = (await readdir(directory)).filter((name) =>
  name.endsWith(".js"),
);
if (!scripts.length)
  throw new Error("No built JavaScript found. Run npm run build first.");
let bytes = 0;
for (const script of scripts)
  bytes += gzipSync(await readFile(path.join(directory, script))).byteLength;
console.log(
  JSON.stringify({
    gzipJavaScriptKiB: Number((bytes / 1024).toFixed(2)),
    limitKiB: 200,
  }),
);
if (bytes > 200 * 1024)
  throw new Error(
    "The JavaScript bundle exceeds the approved 200 KiB gzip budget.",
  );
