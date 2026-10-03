const http = require("http");

function checkBackendHealth() {
    return new Promise((resolve) => {
        const req = http.get("http://127.0.0.1:8000/api/health", { timeout: 2000 }, (res) => {
            if (res.statusCode === 200) {
                let body = "";
                res.on("data", (chunk) => body += chunk);
                res.on("end", () => {
                    try {
                        const json = JSON.parse(body);
                        resolve({ ok: true, data: json });
                    } catch {
                        resolve({ ok: true, raw: body });
                    }
                });
            } else {
                resolve({ ok: false, statusCode: res.statusCode });
            }
        });

        req.on("error", (err) => resolve({ ok: false, error: err.message }));
        req.on("timeout", () => {
            req.destroy();
            resolve({ ok: false, timeout: true });
        });
    });
}

async function waitForBackend(maxRetries = 30, intervalMs = 1000, onStatus) {
    for (let i = 1; i <= maxRetries; i++) {
        const statusMsg = `Polling backend at 127.0.0.1:8000/api/health (Attempt ${i}/${maxRetries})...`;
        console.log(`[Health] ${statusMsg}`);
        if (onStatus) onStatus(statusMsg);
        
        const res = await checkBackendHealth();
        if (res.ok) {
            const readyMsg = "FastAPI backend is ready (HTTP 200 OK)";
            console.log(`[Health] ${readyMsg}`);
            if (onStatus) onStatus(readyMsg);
            return true;
        }
        await new Promise((r) => setTimeout(r, intervalMs));
    }
    console.error("[Health] FastAPI backend health check timed out");
    return false;
}

function checkFrontendHealth() {
    return new Promise((resolve) => {
        const req = http.get("http://127.0.0.1:5173/", { timeout: 2000 }, (res) => {
            if (res.statusCode === 200) {
                resolve({ ok: true });
            } else {
                resolve({ ok: false, statusCode: res.statusCode });
            }
        });

        req.on("error", (err) => resolve({ ok: false, error: err.message }));
        req.on("timeout", () => {
            req.destroy();
            resolve({ ok: false, timeout: true });
        });
    });
}

async function waitForFrontend(maxRetries = 20, intervalMs = 500, onStatus) {
    for (let i = 1; i <= maxRetries; i++) {
        const statusMsg = `Polling frontend at 127.0.0.1:5173/ (Attempt ${i}/${maxRetries})...`;
        console.log(`[Health] ${statusMsg}`);
        if (onStatus) onStatus(statusMsg);

        const res = await checkFrontendHealth();
        if (res.ok) {
            const readyMsg = "Frontend server is reachable (HTTP 200 OK)";
            console.log(`[Health] ${readyMsg}`);
            if (onStatus) onStatus(readyMsg);
            return true;
        }
        await new Promise((r) => setTimeout(r, intervalMs));
    }
    console.error("[Health] Frontend health check timed out");
    return false;
}

function testRealAIInference() {
    return new Promise((resolve) => {
        const postData = JSON.stringify({
            model: "sarvam-30b",
            messages: [{ role: "user", content: "Namaste" }],
            max_tokens: 16
        });

        const req = http.request({
            hostname: "127.0.0.1",
            port: 8081,
            path: "/v1/chat/completions",
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Content-Length": Buffer.byteLength(postData)
            },
            timeout: 10000
        }, (res) => {
            let body = "";
            res.on("data", (chunk) => body += chunk);
            res.on("end", () => {
                if (res.statusCode === 200) {
                    try {
                        const json = JSON.parse(body);
                        const hasChoices = json.choices && json.choices.length > 0;
                        resolve({ ok: true, generatedText: hasChoices ? json.choices[0].message.content : "" });
                    } catch {
                        resolve({ ok: true, raw: body });
                    }
                } else {
                    resolve({ ok: false, statusCode: res.statusCode, body });
                }
            });
        });

        req.on("error", (err) => resolve({ ok: false, error: err.message }));
        req.on("timeout", () => {
            req.destroy();
            resolve({ ok: false, timeout: true });
        });

        req.write(postData);
        req.end();
    });
}

module.exports = {
    checkBackendHealth,
    waitForBackend,
    checkFrontendHealth,
    waitForFrontend,
    testRealAIInference
};
