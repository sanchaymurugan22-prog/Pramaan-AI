const path = require("path");
const fs = require("fs");
const net = require("net");
const dotenv = require("dotenv");

let electronApp = null;
try {
    electronApp = require("electron").app;
} catch (e) {
    // Non-electron environment fallback
}

function isAppPackaged() {
    if (electronApp) return electronApp.isPackaged;
    return Boolean(process.mainModule && process.mainModule.filename.includes("app.asar"));
}

function getUserDataDir() {
    if (electronApp) {
        return electronApp.getPath("userData");
    }
    const homeDir = process.env.HOME || process.env.USERPROFILE || "";
    return path.join(homeDir, ".pramaan-ai");
}

function getRootDir() {
    const isPackaged = isAppPackaged();
    
    if (isPackaged) {
        const resPath = process.resourcesPath;
        if (fs.existsSync(path.join(resPath, "backend")) || fs.existsSync(path.join(resPath, "frontend", "dist"))) {
            return resPath;
        }
    }

    const desktopDir = path.dirname(__dirname);
    const parentDir = path.dirname(desktopDir);

    if (fs.existsSync(path.join(parentDir, "backend"))) {
        return parentDir;
    }
    if (fs.existsSync(path.join(desktopDir, "backend"))) {
        return desktopDir;
    }

    return parentDir;
}

function getFrontendDistDir(rootDir) {
    const root = rootDir || getRootDir();
    
    const locs = [
        path.join(root, "frontend", "dist"),
        path.join(root, "dist"),
        path.join(process.resourcesPath || root, "frontend", "dist")
    ];

    for (const loc of locs) {
        if (fs.existsSync(path.join(loc, "index.html"))) {
            return loc;
        }
    }
    return path.join(root, "frontend", "dist");
}

function getPlatform() {
    const p = process.platform;
    if (p === "darwin") return "mac";
    if (p === "win32") return "win";
    return "linux";
}

function getPlatformArchString() {
    const platform = process.platform; // darwin, win32, linux
    const arch = process.arch; // x64, arm64
    return `${platform}-${arch}`;
}

function getPythonExecutable(rootDir) {
    const root = rootDir || getRootDir();
    const isWin = process.platform === "win32";

    // 1. Check for platform standalone binary executable in resources (PyInstaller output)
    const platformArch = getPlatformArchString();
    const exeName = isWin ? `pramaan-backend-${platformArch}.exe` : `pramaan-backend-${platformArch}`;
    const bundledExe = path.join(root, "bin", exeName);
    if (fs.existsSync(bundledExe)) {
        return bundledExe;
    }

    // 2. Check virtual environment inside backend/.venv
    const venvPythonWin = path.join(root, "backend", ".venv", "Scripts", "python.exe");
    const venvPythonUnix = path.join(root, "backend", ".venv", "bin", "python");

    if (isWin && fs.existsSync(venvPythonWin)) return venvPythonWin;
    if (!isWin && fs.existsSync(venvPythonUnix)) return venvPythonUnix;

    // 3. Fallback to system python
    return isWin ? "python" : "python3";
}

function getLlamaExecutable(rootDir) {
    const root = rootDir || getRootDir();
    const isWin = process.platform === "win32";
    const platformArch = getPlatformArchString();
    const exeName = isWin ? `llama-server-${platformArch}.exe` : `llama-server-${platformArch}`;

    const bundledBin = path.join(root, "bin", exeName);
    const homeDir = process.env.HOME || process.env.USERPROFILE || "";
    const llamaHome = path.join(homeDir, "llama", isWin ? "llama-server.exe" : "llama-server");
    const llamaProject = path.join(root, "models", "llama-server", isWin ? "llama-server.exe" : "llama-server");

    if (fs.existsSync(bundledBin)) return bundledBin;
    if (fs.existsSync(llamaHome)) return llamaHome;
    if (fs.existsSync(llamaProject)) return llamaProject;

    return isWin ? "llama-server.exe" : "llama-server";
}

function loadEnvConfig(rootDir) {
    const root = rootDir || getRootDir();
    const envPath = path.join(root, ".env");
    const envExamplePath = path.join(root, ".env.example");
    
    let targetPath = envPath;
    if (!fs.existsSync(targetPath) && fs.existsSync(envExamplePath)) {
        targetPath = envExamplePath;
    }

    if (fs.existsSync(targetPath)) {
        try {
            const envContent = fs.readFileSync(targetPath, "utf-8");
            return dotenv.parse(envContent);
        } catch (err) {
            console.error("[Platform] Error reading .env:", err);
        }
    }
    return {};
}

function isPortAvailable(port, host = "127.0.0.1") {
    return new Promise((resolve) => {
        const server = net.createServer();
        server.once("error", (err) => {
            if (err.code === "EADDRINUSE") {
                resolve(false);
            } else {
                resolve(false);
            }
        });
        server.once("listening", () => {
            server.close(() => resolve(true));
        });
        server.listen(port, host);
    });
}

module.exports = {
    isAppPackaged,
    getUserDataDir,
    getRootDir,
    getFrontendDistDir,
    getPlatform,
    getPlatformArchString,
    getPythonExecutable,
    getLlamaExecutable,
    loadEnvConfig,
    isPortAvailable
};
