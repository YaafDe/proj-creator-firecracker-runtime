#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";

const source = process.env.RUNTIME_INPUT_URL || process.env.RUNTIME_INPUT_FILE || "runtime-input.json";

async function readSource(value) {
  if (value.startsWith("http://") || value.startsWith("https://")) {
    const response = await fetch(value);
    if (!response.ok) {
      throw new Error(`failed to fetch ${value}: ${response.status} ${response.statusText}`);
    }
    return await response.text();
  }
  return readFileSync(value, "utf8");
}

function requireString(object, path) {
  const parts = path.split(".");
  let value = object;
  for (const part of parts) value = value?.[part];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${path} is required in ${source}`);
  }
  return value.trim();
}

const input = JSON.parse(await readSource(source));
const resolved = {
  firecracker_ref: requireString(input, "firecracker_ref"),
  kernel_version: requireString(input, "kernel_version"),
  rootfs_url: requireString(input, "rootfs.url"),
  rootfs_sha256: requireString(input, "rootfs.sha256"),
  runner_url: requireString(input, "runner.url"),
  runner_sha256: requireString(input, "runner.sha256")
};

const githubOutput = process.env.GITHUB_OUTPUT;
if (githubOutput) {
  writeFileSync(
    githubOutput,
    Object.entries(resolved).map(([key, value]) => `${key}=${value}`).join("\n") + "\n",
    { flag: "a" }
  );
} else {
  process.stdout.write(JSON.stringify(resolved, null, 2) + "\n");
}
