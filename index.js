#!/usr/bin/env node
/**
 * Bothost often auto-detects Node because of local/package.json and then
 * picks a random .mjs as CMD. This root index.js is first in their Node
 * entrypoint list and starts the Python bot instead.
 */
const { spawn } = require("child_process");
const py = process.env.PYTHON || "python3";
const child = spawn(py, ["main.py"], { stdio: "inherit", cwd: __dirname });
child.on("error", (err) => {
  console.error("Failed to start Python bot:", err);
  process.exit(1);
});
child.on("exit", (code, signal) => {
  if (signal) process.exit(1);
  process.exit(code ?? 0);
});
