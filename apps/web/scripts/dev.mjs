import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const argumentsFromCaller = process.argv.slice(2);
const managedPreview = argumentsFromCaller.includes("--strictPort");
const nextArguments = [managedPreview ? "start" : "dev"];

for (let index = 0; index < argumentsFromCaller.length; index += 1) {
  const argument = argumentsFromCaller[index];
  if (argument === "--strictPort") continue;
  if (argument === "--host") {
    nextArguments.push("--hostname", argumentsFromCaller[index + 1] ?? "0.0.0.0");
    index += 1;
    continue;
  }
  nextArguments.push(argument);
}

const nextBinary = fileURLToPath(new URL("../node_modules/next/dist/bin/next", import.meta.url));
const child = spawn(process.execPath, [nextBinary, ...nextArguments], { stdio: "inherit" });

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => child.kill(signal));
}

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 1);
});
