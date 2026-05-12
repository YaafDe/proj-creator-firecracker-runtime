#!/usr/bin/env node
import { createHash } from "node:crypto";
import { createReadStream, existsSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const version = process.env.VERSION;
const baseUrl = process.env.BASE_URL?.replace(/\/$/, "");
const root = process.env.ARTIFACT_ROOT ?? join("artifacts", version ?? "");
const compression = process.env.PROJ_CREATOR_FIRECRACKER_ARTIFACT_COMPRESSION ?? "zstd";

if (!version) {
  throw new Error("VERSION is required, for example VERSION=v2026.05.0");
}
if (!baseUrl) {
  throw new Error("BASE_URL is required, for example BASE_URL=https://github.com/ORG/repo/releases/download/v2026.05.0");
}

const githubReleaseAssetLimitBytes = 2 * 1024 * 1024 * 1024;

function sha256(path) {
  return new Promise((resolve, reject) => {
    const hash = createHash("sha256");
    const stream = createReadStream(path);
    stream.on("data", chunk => hash.update(chunk));
    stream.on("error", reject);
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

async function artifact(fileName, executable = false) {
  const compressed = compression === "zstd";
  const assetName = compressed ? `${fileName}.zst` : fileName;
  const path = join(root, assetName);
  const size = statSync(path).size;
  if (size >= githubReleaseAssetLimitBytes) {
    throw new Error(`${fileName} is ${size} bytes; GitHub release assets must be under 2 GiB`);
  }
  return {
    url: `${baseUrl}/${assetName}`,
    sha256: await sha256(path),
    file_name: fileName,
    asset_file_name: assetName,
    size_bytes: size,
    ...(compressed ? { compression: "zstd" } : {}),
    ...(executable ? { executable: true } : {})
  };
}

async function kernelArtifact() {
  const kernel = await artifact("vmlinux");
  const fragmentPath = join(root, "kernel-artifact.json");
  if (!existsSync(fragmentPath)) return kernel;
  const fragment = JSON.parse(readFileSync(fragmentPath, "utf8"));
  if (fragment?.kernel?.source) {
    kernel.source = fragment.kernel.source;
  }
  return kernel;
}

const manifest = {
  version,
  kernel: await kernelArtifact(),
  rootfs: await artifact("rootfs.ext4"),
  runner: await artifact("firecracker-runner", true)
};

const sums = [
  `${manifest.kernel.sha256}  ${manifest.kernel.asset_file_name}`,
  `${manifest.rootfs.sha256}  ${manifest.rootfs.asset_file_name}`,
  `${manifest.runner.sha256}  ${manifest.runner.asset_file_name}`
].join("\n") + "\n";

writeFileSync(join(root, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
writeFileSync(join(root, "SHA256SUMS"), sums);
console.log(join(root, "manifest.json"));
