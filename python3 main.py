/**
 * Bothost auto-Dockerfile sometimes emits:
 *   CMD ["node", "python3 main.py"]
 * Node then loads this filename (one argument with a space).
 */
const { spawn } = require("child_process");
const py = process.env.PYTHON || "python3";
const child = spawn(py, ["main.py"], { stdio: "inherit", cwd: __dirname });
child.on("error", (err) => {
  console.error(err);
  process.exit(1);
});
child.on("exit", (code, signal) => {
  process.exit(signal ? 1 : code ?? 0);
});
