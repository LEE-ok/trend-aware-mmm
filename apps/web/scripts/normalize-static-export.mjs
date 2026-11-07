// Next.js can write nested RSC segment paths on Windows while the browser
// requests dot-separated filenames. Add portable aliases in generated out/ only.
// Upstream: https://github.com/vercel/next.js/issues/92339
import { constants } from "node:fs";
import { copyFile, readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const output = fileURLToPath(new URL("../out/", import.meta.url));
let aliases = 0;

async function aliasSegments(directory, destination, parts) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const source = path.join(directory, entry.name);
    const segments = [...parts, entry.name];
    if (entry.isDirectory()) {
      await aliasSegments(source, destination, segments);
    } else if (entry.isFile() && entry.name.endsWith(".txt")) {
      const target = path.join(destination, segments.join("."));
      try {
        await copyFile(source, target, constants.COPYFILE_EXCL);
        aliases += 1;
      } catch (error) {
        if (error.code !== "EEXIST") throw error;
        const [existing, generated] = await Promise.all([readFile(target), readFile(source)]);
        if (!existing.equals(generated)) throw new Error(`Conflicting static segment: ${target}`);
      }
    }
  }
}

async function visit(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === "_next") continue;
    const child = path.join(directory, entry.name);
    if (entry.name.startsWith("__next.")) {
      await aliasSegments(child, directory, [entry.name]);
    } else {
      await visit(child);
    }
  }
}

await visit(output);
console.log(`Static export: added ${aliases} Windows RSC path aliases.`);
