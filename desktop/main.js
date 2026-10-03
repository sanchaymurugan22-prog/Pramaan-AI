const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const fs = require("fs");
const { getRootDir, getFrontendDistDir, getPythonExecutable, getLlamaExecutable, getPlatform, loadEnvConfig, isAppPackaged } = require("./launcher/platform");
const { startBackend, stopBackend } = require("./launcher/start-backend");
const { startAI, stopAI } = require("./launcher/start-ai");
const { startFrontend, stopFrontend } = require("./launcher/start-frontend");
const { waitForBackend, waitForFrontend, checkBackendHealth } = require("./launcher/health-check");
const { checkModelStatus } = require("./launcher/download-manager");

let mainWindow = null;
let splashWindow = null;
let isQuitting = false;

function logElectron(moduleName, message) {
    console.log(`[${moduleName}] ${message}`);
}

function printDiagnostics() {
    const rootDir = getRootDir();
    const distDir = getFrontendDistDir(rootDir);
    const pythonBin = getPythonExecutable(rootDir);
    const llamaBin = getLlamaExecutable(rootDir);
    const envConfig = loadEnvConfig(rootDir);
    const envPath = path.join(rootDir, ".env");

    logElectron("Pramaan Electron", "=================== PACKAGED RUNTIME DIAGNOSTICS ===================");
    logElectron("Pramaan Electron", `app.isPackaged: ${app.isPackaged}`);
    logElectron("Pramaan Electron", `process.resourcesPath: ${process.resourcesPath}`);
    logElectron("Pramaan Electron", `app.getAppPath(): ${app.getAppPath()}`);
    logElectron("Pramaan Electron", `process.cwd(): ${process.cwd()}`);
    logElectron("Pramaan Electron", `Resolved rootDir: ${rootDir}`);
    logElectron("Pramaan Electron", `Resolved frontend/dist: ${distDir}`);
    logElectron("Pramaan Electron", `frontend/dist/index.html exists: ${fs.existsSync(path.join(distDir, "index.html"))}`);
    logElectron("Pramaan Electron", `Backend dir path: ${path.join(rootDir, "backend")}`);
    logElectron("Pramaan Electron", `Backend dir exists: ${fs.existsSync(path.join(rootDir, "backend"))}`);
    logElectron("Pramaan Electron", `Python binary path: ${pythonBin}`);
    logElectron("Pramaan Electron", `Python binary exists: ${fs.existsSync(pythonBin)}`);
    logElectron("Pramaan Electron", `.env file path: ${envPath}`);
    logElectron("Pramaan Electron", `.env exists: ${fs.existsSync(envPath)}`);
    logElectron("Pramaan Electron", `AI_MODE setting: ${envConfig.AI_MODE || "local"}`);
    logElectron("Pramaan Electron", `Llama binary path: ${llamaBin}`);
    logElectron("Pramaan Electron", `Llama binary exists: ${fs.existsSync(llamaBin)}`);
    logElectron("Pramaan Electron", "====================================================================");
}

function createSplashWindow() {
    logElectron("Window", "Creating visible splash window...");
    splashWindow = new BrowserWindow({
        width: 540,
        height: 380,
        transparent: false,
        frame: false,
        resizable: false,
        alwaysOnTop: true,
        center: true,
        title: "Pramaan AI Launcher",
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    const splashHtml = `
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Pramaan AI Launcher</title>
            <style>
                * { box-sizing: border-box; }
                body {
                    margin: 0;
                    padding: 32px;
                    background: #15206B;
                    color: #ffffff;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    border: 1px solid rgba(255,255,255,0.15);
                    border-radius: 12px;
                    user-select: none;
                }
                .logo-circle {
                    width: 72px;
                    height: 72px;
                    border-radius: 50%;
                    background: #1E2F8F;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin-bottom: 16px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.35);
                    border: 2px solid rgba(255,255,255,0.25);
                }
                .tick {
                    font-size: 38px;
                    font-weight: bold;
                    background: linear-gradient(135deg, #F28C28 30%, #3DBA4A 100%);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }
                h1 {
                    margin: 0 0 6px 0;
                    font-size: 26px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                }
                p.sub {
                    margin: 0 0 24px 0;
                    font-size: 13px;
                    color: #FFDDB8;
                    opacity: 0.9;
                }
                .status-container {
                    width: 100%;
                    background: rgba(255,255,255,0.08);
                    border: 1px solid rgba(255,255,255,0.12);
                    padding: 12px 20px;
                    border-radius: 20px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 12px;
                }
                .status-text {
                    font-size: 13px;
                    color: #D2D8F4;
                    text-align: center;
                }
                .spinner {
                    width: 18px;
                    height: 18px;
                    border: 2px solid rgba(255,255,255,0.2);
                    border-top: 2px solid #F28C28;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                    flex-shrink: 0;
                }
                .error-box {
                    display: none;
                    background: #A3261B;
                    color: #FFFFFF;
                    padding: 14px;
                    border-radius: 8px;
                    font-size: 13px;
                    width: 100%;
                    margin-top: 10px;
                    text-align: center;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        </head>
        <body>
            <div class="logo-circle">
                <span class="tick">✓</span>
            </div>
            <h1>Pramaan AI</h1>
            <p class="sub">Content You Can Prove — Offline Desktop Platform</p>
            <div class="status-container" id="status-container">
                <div class="spinner" id="spinner"></div>
                <div class="status-text" id="status-text">Starting Pramaan AI launcher...</div>
            </div>
            <div class="error-box" id="error-box"></div>
        </body>
        </html>
    `;

    splashWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(splashHtml)}`);
}

function updateSplashStatus(message, isError = false, errorDetail = "") {
    if (splashWindow && !splashWindow.isDestroyed()) {
        const js = `
            (function() {
                const textEl = document.getElementById("status-text");
                const spinnerEl = document.getElementById("spinner");
                const errorBox = document.getElementById("error-box");
                if (textEl) textEl.innerText = ${JSON.stringify(message)};
                if (${isError}) {
                    if (spinnerEl) spinnerEl.style.display = "none";
                    if (errorBox) {
                        errorBox.style.display = "block";
                        errorBox.innerText = ${JSON.stringify(errorDetail || message)};
                    }
                }
            })();
        `;
        splashWindow.webContents.executeJavaScript(js).catch(() => {});
    }
}

async function createMainWindow(frontendUrl) {
    logElectron("Window", `Creating main BrowserWindow pointing to ${frontendUrl}...`);
    mainWindow = new BrowserWindow({
        width: 1440,
        height: 900,
        minWidth: 1100,
        minHeight: 700,
        title: "Pramaan AI",
        show: false,
        backgroundColor: "#FBF8F2",
        webPreferences: {
            contextIsolation: true,
            nodeIntegration: false,
            preload: path.join(__dirname, "preload.js")
        }
    });

    // Diagnostic logging for render process & window events
    mainWindow.webContents.on("did-fail-load", (event, errorCode, errorDescription, validatedURL) => {
        logElectron("Window", `[did-fail-load] Failed to load URL ${validatedURL}: [${errorCode}] ${errorDescription}`);
        updateSplashStatus("Failed to load user interface", true, `Error ${errorCode}: ${errorDescription}`);
        dialog.showErrorBox("Pramaan AI Load Error", `Failed to load interface from ${validatedURL}.\nError: ${errorDescription} (${errorCode})`);
    });

    mainWindow.webContents.on("render-process-gone", (event, details) => {
        logElectron("Window", `[render-process-gone] Renderer process exited: reason=${details.reason}, exitCode=${details.exitCode}`);
    });

    mainWindow.webContents.on("console-message", (event, level, message, line, sourceId) => {
        logElectron("RendererConsole", `[Level ${level}] ${message} (${sourceId}:${line})`);
    });

    logElectron("Window", `Loading URL: ${frontendUrl}`);
    await mainWindow.loadURL(frontendUrl);

    mainWindow.once("ready-to-show", () => {
        logElectron("Window", "Main window ready-to-show. Closing splash window and displaying main window.");
        if (splashWindow && !splashWindow.isDestroyed()) {
            splashWindow.close();
            splashWindow = null;
        }
        mainWindow.show();
        mainWindow.focus();
    });

    mainWindow.on("closed", () => {
        logElectron("Window", "Main window closed.");
        mainWindow = null;
    });
}

// IPC Registration
ipcMain.handle("get-platform", () => getPlatform());
ipcMain.handle("get-app-version", () => app.getVersion());
ipcMain.handle("check-model-status", () => checkModelStatus());
ipcMain.handle("get-system-status", async () => {
    const health = await checkBackendHealth();
    return {
        backend: health,
        models: checkModelStatus()
    };
});

ipcMain.on("window-minimize", () => {
    if (mainWindow) mainWindow.minimize();
});
ipcMain.on("window-maximize", () => {
    if (mainWindow) {
        if (mainWindow.isMaximized()) mainWindow.unmaximize();
        else mainWindow.maximize();
    }
});
ipcMain.on("window-close", () => {
    if (mainWindow) mainWindow.close();
});

// App Lifecycle
app.whenReady().then(async () => {
    logElectron("Pramaan Electron", "Pramaan AI Desktop app.whenReady fired.");
    
    // Print comprehensive diagnostic output
    printDiagnostics();

    // Step 2: Show visible splash screen immediately
    createSplashWindow();

    try {
        // Step 3: Start AI engine if AI_MODE=local
        logElectron("AI", "Initializing AI launcher...");
        updateSplashStatus("Checking AI model configuration...");
        const aiResult = await startAI((msg) => updateSplashStatus(msg));
        if (aiResult.error) {
            logElectron("AI", `AI engine startup error: ${aiResult.error}`);
        }

        // Step 4: Start FastAPI backend on 127.0.0.1:8000
        logElectron("Backend", "Launching FastAPI backend server...");
        updateSplashStatus("Starting FastAPI backend server...");
        const backendResult = await startBackend((msg) => updateSplashStatus(msg));
        if (!backendResult.running) {
            const err = `Backend launch failed: ${backendResult.error || "Unknown error"}`;
            logElectron("Backend", err);
            updateSplashStatus("FastAPI Backend Failed to Start", true, err);
            dialog.showErrorBox("Startup Error", err);
            return;
        }

        // Step 5: Wait until http://127.0.0.1:8000/api/health returns HTTP 200
        logElectron("Health", "Waiting for FastAPI backend to respond on http://127.0.0.1:8000/api/health...");
        updateSplashStatus("Waiting for FastAPI backend health check...");
        const backendReady = await waitForBackend(30, 1000, (msg) => updateSplashStatus(msg));
        if (!backendReady) {
            const err = "FastAPI backend server failed to respond on http://127.0.0.1:8000/api/health within 30 seconds.";
            logElectron("Health", err);
            updateSplashStatus("Backend Health Check Failed", true, err);
            dialog.showErrorBox("Backend Health Error", err);
            return;
        }
        logElectron("Health", "FastAPI backend confirmed operational (HTTP 200 OK).");

        // Step 6: Start production frontend server from ../frontend/dist on 127.0.0.1:5173
        logElectron("Frontend", "Launching production frontend server...");
        updateSplashStatus("Starting frontend server...");
        const frontendResult = await startFrontend((msg) => updateSplashStatus(msg));
        if (!frontendResult.running) {
            const err = `Frontend server launch failed: ${frontendResult.error || "Unknown error"}`;
            logElectron("Frontend", err);
            updateSplashStatus("Frontend Server Failed to Start", true, err);
            dialog.showErrorBox("Frontend Error", err);
            return;
        }

        // Step 7: Wait until http://127.0.0.1:5173/ is actually reachable
        logElectron("Health", "Waiting for frontend server to become reachable on http://127.0.0.1:5173/...");
        updateSplashStatus("Waiting for frontend interface server...");
        const frontendReady = await waitForFrontend(20, 500, (msg) => updateSplashStatus(msg));
        if (!frontendReady) {
            const err = "Frontend server failed to respond on http://127.0.0.1:5173/ within 10 seconds.";
            logElectron("Health", err);
            updateSplashStatus("Frontend Reachability Failed", true, err);
            dialog.showErrorBox("Frontend Reachability Error", err);
            return;
        }
        logElectron("Health", "Frontend server confirmed operational (HTTP 200 OK).");

        // Step 8 & 9: ONLY AFTER BOTH backend and frontend are ready, create/show main window and load http://127.0.0.1:5173/
        logElectron("Window", "Both backend and frontend are healthy. Spawning main BrowserWindow.");
        updateSplashStatus("Opening Pramaan AI...");
        await createMainWindow(frontendResult.url || "http://127.0.0.1:5173/");

    } catch (err) {
        logElectron("Pramaan Electron", `Unhandled exception during startup lifecycle: ${err.stack || err.message}`);
        updateSplashStatus("Application Startup Failed", true, err.message);
        dialog.showErrorBox("Startup Exception", err.message);
    }

    app.on("activate", () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createMainWindow("http://127.0.0.1:5173/");
        }
    });
});

function cleanupServices() {
    if (isQuitting) return;
    isQuitting = true;
    logElectron("Pramaan Electron", "Application shutting down. Cleaning up backend, AI, and frontend child processes...");
    stopBackend();
    stopAI();
    stopFrontend();
    logElectron("Pramaan Electron", "Service cleanup complete.");
}

app.on("before-quit", () => {
    cleanupServices();
});

app.on("window-all-closed", () => {
    cleanupServices();
    if (process.platform !== "darwin") {
        app.quit();
    }
});