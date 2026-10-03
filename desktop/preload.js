const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("electronAPI", {
    getPlatform: () => ipcRenderer.invoke("get-platform"),
    getAppVersion: () => ipcRenderer.invoke("get-app-version"),
    checkModelStatus: () => ipcRenderer.invoke("check-model-status"),
    getSystemStatus: () => ipcRenderer.invoke("get-system-status"),
    minimizeWindow: () => ipcRenderer.send("window-minimize"),
    maximizeWindow: () => ipcRenderer.send("window-maximize"),
    closeWindow: () => ipcRenderer.send("window-close")
});
