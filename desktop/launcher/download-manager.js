const path = require("path");
const fs = require("fs");
const os = require("os");
const { getRootDir } = require("./platform");

function getSystemSpecs() {
    const totalRamGb = Math.round((os.totalmem() / (1024 * 1024 * 1024)) * 10) / 10;
    const freeRamGb = Math.round((os.freemem() / (1024 * 1024 * 1024)) * 10) / 10;

    let freeDiskGb = 50; // Fallback estimate
    try {
        if (fs.statfsSync) {
            const rootDir = getRootDir();
            const stats = fs.statfsSync(rootDir);
            freeDiskGb = Math.round(((stats.bfree * stats.bsize) / (1024 * 1024 * 1024)) * 10) / 10;
        }
    } catch {
        // Ignored
    }

    return {
        platform: process.platform,
        arch: process.arch,
        cpus: os.cpus().length,
        cpuModel: os.cpus()[0] ? os.cpus()[0].model : "Unknown CPU",
        totalRamGb,
        freeRamGb,
        freeDiskGb,
        passRamCheck: totalRamGb >= 15,
        passDiskCheck: freeDiskGb >= 20
    };
}

function checkModelStatus() {
    const rootDir = getRootDir();
    const modelsDir = path.join(rootDir, "models");

    const sarvamModelFile = path.join(modelsDir, "sarvam-30b-Q4_K_M.gguf-00001-of-00006.gguf");
    const hfCacheDir = path.join(
        process.env.HOME || process.env.USERPROFILE || "",
        ".cache", "huggingface", "hub", "models--sarvamai--sarvam-30b-gguf"
    );

    const hasSarvamModel = fs.existsSync(sarvamModelFile) || fs.existsSync(hfCacheDir);

    const indictransDir = path.join(modelsDir, "indictrans2-en-indic-ct2-int8");
    const hasIndicTrans = fs.existsSync(indictransDir);

    const sttWhisper = path.join(modelsDir, "whisper-small");
    const hasStt = fs.existsSync(sttWhisper);

    return {
        specs: getSystemSpecs(),
        sarvamModel: {
            installed: hasSarvamModel,
            path: hasSarvamModel ? (fs.existsSync(sarvamModelFile) ? sarvamModelFile : hfCacheDir) : null
        },
        indictrans: {
            installed: hasIndicTrans
        },
        stt: {
            installed: hasStt
        },
        modelsDirExists: fs.existsSync(modelsDir),
        allRequiredInstalled: hasSarvamModel
    };
}

module.exports = {
    getSystemSpecs,
    checkModelStatus
};
