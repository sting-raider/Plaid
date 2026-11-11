import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { APP_NAME, DEV } from "./stage";

// the taskbar and Alt+Tab name; the tauri.conf title is the release name
if (DEV) getCurrentWindow().setTitle(APP_NAME).catch(() => {});

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
