#!/usr/bin/env node
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const version = process.env.VERSION;
const baseUrl = process.env.BASE_URL?.replace(/\/$/, "");
const root = process.env.ARTIFACT_ROOT ?? join("artifacts", version ?? "");

if (!version) {
  throw new Error("VERSION is required, for example VERSION=v2026.05.0");
}
if (!baseUrl) {
  throw new Error("BASE_URL is required, for example BASE_URL=https://github.com/ORG/repo/releases/download/v2026.05.0");
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function artifact(fileName, executable = false) {
  const path = join(root, fileName);
  return {
    url: `${baseUrl}/${fileName}`,
    sha256: sha256(path),
    file_name: fileName,
    ...(executable ? { executable: true } : {})
  };
}

const manifest = {
  version,
  kernel: artifact("vmlinux"),
  rootfs: artifact("rootfs.ext4"),
  runner: artifact("firecracker-runner", true)
};

const sums = [
  `${manifest.kernel.sha256}  vmlinux`,
  `${manifest.rootfs.sha256}  rootfs.ext4`,
  `${manifest.runner.sha256}  firecracker-runner`
].join("\n") + "\n";

writeFileSync(join(root, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
writeFileSync(join(root, "SHA256SUMS"), sums);
console.log(join(root, "manifest.json"));
