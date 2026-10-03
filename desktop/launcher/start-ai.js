const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");
const http = require("http");
const { getRootDir, getUserDataDir, getLlamaExecutable, loadEnvConfig, isPortAvailable, isAppPackaged } = require("./platform");

let aiProcess = null;

function checkLlamaHealth() {
    return new Promise((resolve) => {
        const req = http.get("http://127.0.0.1:8081/health", { timeout: 2000 }, (res) => {
            if (res.statusCode === 200) {
                resolve(true);
            } else {
                resolve(false);
            }
        });
        req.on("error", () => resolve(false));
        req.on("timeout", () => {
            req.destroy();
            resolve(false);
        });
    });
}

async function waitForLlama(maxRetries = 20, intervalMs = 1000, onLog) {
    for (let i = 1; i <= maxRetries; i++) {
        const ok = await checkLlamaHealth();
        if (ok) return true;
        if (onLog) onLog(`Waiting for llama-server at 127.0.0.1:8081 (Attempt ${i}/${maxRetries})...`);
        await new Promise((r) => setTimeout(r, intervalMs));
    }
    return false;
}

async function startAI(onLog) {
    const log = (msg) => {
        console.log(`[AI] ${msg}`);
        if (onLog) onLog(msg);
    };

    const rootDir = getRootDir();
    const userDataDir = getUserDataDir();
    const envConfig = loadEnvConfig(rootDir);

    // Enforce AI_MODE=local in production release (never fallback to mock silently in production)
    const packaged = isAppPackaged();
    const aiMode = packaged ? "local" : (envConfig.AI_MODE || "local");

    const arch = process.arch;
    const platform = process.platform;
    log(`Detected system: platform=${platform}, arch=${arch}, packaged=${packaged}`);

    if (aiMode !== "local") {
        log(`AI_MODE is set to '${aiMode}' in dev mode. Skipping local llama-server process creation.`);
        return { running: true, mode: aiMode, spawned: false };
    }

    const portAvailable = await isPortAvailable(8081);
    if (!portAvailable) {
        log("Port 8081 is already in use. Reusing existing running llama-server.");
        const healthy = await checkLlamaHealth();
        return { running: true, mode: "local", spawned: false, healthy };
    }

    const llamaBin = getLlamaExecutable(rootDir);

    // Look for Sarvam 30B GGUF model in root models/, userData/models, or HF cache
    const locations = [
        path.join(rootDir, "models", "sarvam-30b-Q4_K_M.gguf-00001-of-00006.gguf"),
        path.join(userDataDir, "models", "sarvam-30b-Q4_K_M.gguf-00001-of-00006.gguf"),
        path.join(process.env.HOME || process.env.USERPROFILE || "", ".cache", "huggingface", "hub", "models--sarvamai--sarvam-30b-gguf")
    ];

    let modelPath = null;
    let isHf = false;

    for (const loc of locations) {
        if (fs.existsSync(loc)) {
            modelPath = loc;
            if (loc.includes(".cache")) isHf = true;
            break;
        }
    }

    if (!modelPath) {
        log("Sarvam 30B GGUF model not found in local paths or HF cache. Local AI requires setup/download.");
        return { running: false, mode: "local", modelMissing: true };
    }

    const modelArg = isHf ? ["-hf", "sarvamai/sarvam-30b-gguf:Q4_K_M", "--offline"] : ["-m", modelPath];
    log(`Using Sarvam model at: ${modelPath}`);

    const args = [
        ...modelArg,
        "--port", "8081",
        "-c", "4096",
        "-t", "4",
        "-np", "1",
        "-b", "512",
        "--reasoning-budget", "0"
    ];

    log(`Spawning llama-server (${llamaBin}) on port 8081...`);

    try {
        aiProcess = spawn(llamaBin, args, {
            cwd: rootDir,
            env: { ...process.env },
            stdio: ["ignore", "pipe", "pipe"]
        });

        aiProcess.stdout.on("data", (data) => {
            const str = data.toString().trim();
            if (str) log(`[llama stdout] ${str}`);
        });

        aiProcess.stderr.on("data", (data) => {
            const str = data.toString().trim();
            if (str) log(`[llama stderr] ${str}`);
        });

        aiProcess.on("error", (err) => {
            log(`Failed to start llama-server process: ${err.message}`);
        });

        aiProcess.on("exit", (code, signal) => {
            log(`llama-server process exited with code ${code} signal ${signal}`);
            aiProcess = null;
        });

        const healthy = await waitForLlama(15, 1000, log);

        return { running: true, mode: "local", spawned: true, healthy, process: aiProcess };
    } catch (err) {
        log(`Exception starting llama-server: ${err.message}`);
        return { running: false, error: err.message };
    }
}

function stopAI() {
    if (aiProcess && !aiProcess.killed) {
        console.log("[AI] Stopping llama-server process...");
        aiProcess.kill("SIGTERM");
        aiProcess = null;
    }
}

module.exports = {
    startAI,
    stopAI,
    checkLlamaHealth
};
