const { spawn } = require("child_process");
const http = require("http");
const fs = require("fs");
const path = require("path");
const { getRootDir, getFrontendDistDir, isPortAvailable } = require("./platform");

let frontendProcess = null;
let staticServer = null;

async function startFrontend(onLog) {
    const log = (msg) => {
        console.log(`[Frontend] ${msg}`);
        if (onLog) onLog(msg);
    };

    const rootDir = getRootDir();
    const distDir = getFrontendDistDir(rootDir);

    log(`Resolved rootDir: ${rootDir}`);
    log(`Resolved distDir: ${distDir}`);
    log(`frontend/dist/index.html exists: ${fs.existsSync(path.join(distDir, "index.html"))}`);

    const portAvailable = await isPortAvailable(5173);

    if (!portAvailable) {
        log("Port 5173 is already in use. Reusing port 5173.");
        return { running: true, url: "http://127.0.0.1:5173", spawned: false };
    }

    // If frontend/dist exists, serve it via Node http server with API proxying
    if (fs.existsSync(distDir) && fs.existsSync(path.join(distDir, "index.html"))) {
        log(`Serving production frontend build from ${distDir} on 127.0.0.1:5173...`);
        return serveStaticDist(distDir, log);
    }

    // Otherwise, launch Vite dev server (in development)
    const frontendDir = path.join(rootDir, "frontend");
    log(`Launching Vite dev server in ${frontendDir}...`);
    const npmBin = process.platform === "win32" ? "npm.cmd" : "npm";

    try {
        frontendProcess = spawn(npmBin, ["run", "dev"], {
            cwd: frontendDir,
            env: { ...process.env },
            stdio: ["ignore", "pipe", "pipe"]
        });

        frontendProcess.stdout.on("data", (data) => {
            const str = data.toString().trim();
            if (str) log(`[Vite stdout] ${str}`);
        });

        frontendProcess.stderr.on("data", (data) => {
            const str = data.toString().trim();
            if (str) log(`[Vite stderr] ${str}`);
        });

        return { running: true, url: "http://127.0.0.1:5173", spawned: true, process: frontendProcess };
    } catch (err) {
        log(`Failed to launch Vite dev server: ${err.message}`);
        return { running: false, error: err.message };
    }
}

function serveStaticDist(distDir, log) {
    return new Promise((resolve) => {
        const mimeTypes = {
            ".html": "text/html",
            ".js": "text/javascript",
            ".css": "text/css",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".woff2": "font/woff2",
            ".woff": "font/woff",
            ".ttf": "font/ttf"
        };

        staticServer = http.createServer((req, res) => {
            // Proxy /api requests to FastAPI backend on port 8000
            if (req.url.startsWith("/api")) {
                const proxyReq = http.request({
                    hostname: "127.0.0.1",
                    port: 8000,
                    path: req.url,
                    method: req.method,
                    headers: req.headers
                }, (proxyRes) => {
                    res.writeHead(proxyRes.statusCode, proxyRes.headers);
                    proxyRes.pipe(res);
                });

                proxyReq.on("error", (err) => {
                    res.writeHead(502, { "Content-Type": "application/json" });
                    res.end(JSON.stringify({ error: "Backend proxy error", message: err.message }));
                });

                req.pipe(proxyReq);
                return;
            }

            // Serve static files from distDir
            let filePath = path.join(distDir, req.url === "/" ? "index.html" : req.url);
            if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
                filePath = path.join(distDir, "index.html"); // Single page app fallback
            }

            const ext = path.extname(filePath).toLowerCase();
            const contentType = mimeTypes[ext] || "application/octet-stream";

            fs.readFile(filePath, (err, content) => {
                if (err) {
                    res.writeHead(500);
                    res.end("Server Error");
                } else {
                    res.writeHead(200, { "Content-Type": contentType });
                    res.end(content, "utf-8");
                }
            });
        });

        staticServer.listen(5173, "127.0.0.1", () => {
            log("Static server with API proxy listening on http://127.0.0.1:5173");
            resolve({ running: true, url: "http://127.0.0.1:5173", spawned: true, server: staticServer });
        });
    });
}

function stopFrontend() {
    if (frontendProcess && !frontendProcess.killed) {
        console.log("[Frontend] Stopping frontend dev process...");
        frontendProcess.kill("SIGTERM");
        frontendProcess = null;
    }
    if (staticServer) {
        console.log("[Frontend] Closing static server...");
        staticServer.close();
        staticServer = null;
    }
}

module.exports = {
    startFrontend,
    stopFrontend
};
