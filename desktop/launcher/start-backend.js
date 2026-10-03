const { spawn } = require("child_process");
const path = require("path");
const { getRootDir, getPythonExecutable, isPortAvailable } = require("./platform");

let backendProcess = null;

async function startBackend(onLog) {
    const log = (msg) => {
        console.log(`[Backend] ${msg}`);
        if (onLog) onLog(msg);
    };

    const rootDir = getRootDir();
    const portAvailable = await isPortAvailable(8000);

    if (!portAvailable) {
        log("Port 8000 is already in use. Reusing existing running FastAPI backend.");
        return { running: true, spawned: false };
    }

    const pythonBin = getPythonExecutable(rootDir);
    const backendDir = path.join(rootDir, "backend");

    log(`Starting backend server from ${backendDir} using ${pythonBin}...`);

    const args = [
        "-m", "uvicorn",
        "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8000"
    ];

    try {
        backendProcess = spawn(pythonBin, args, {
            cwd: backendDir,
            env: {
                ...process.env,
                PYTHONUNBUFFERED: "1"
            },
            stdio: ["ignore", "pipe", "pipe"]
        });

        backendProcess.stdout.on("data", (data) => {
            const str = data.toString().trim();
            if (str) log(`[stdout] ${str}`);
        });

        backendProcess.stderr.on("data", (data) => {
            const str = data.toString().trim();
            if (str) log(`[stderr] ${str}`);
        });

        backendProcess.on("error", (err) => {
            log(`Failed to start backend process: ${err.message}`);
        });

        backendProcess.on("exit", (code, signal) => {
            log(`Backend process exited with code ${code} signal ${signal}`);
            backendProcess = null;
        });

        return { running: true, spawned: true, process: backendProcess };
    } catch (err) {
        log(`Exception launching backend: ${err.message}`);
        return { running: false, error: err.message };
    }
}

function stopBackend() {
    if (backendProcess && !backendProcess.killed) {
        console.log("[Backend] Stopping FastAPI backend process...");
        backendProcess.kill("SIGTERM");
        backendProcess = null;
    }
}

module.exports = {
    startBackend,
    stopBackend
};
