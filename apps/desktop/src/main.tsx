import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AvatarWindow } from "./components/avatar/AvatarWindow";
import "./styles/index";
import "./memory.css";
import "./styles/workbench.css";

const isAvatarWindow = window.location.hash === "#/avatar";

if (isAvatarWindow) {
  document.body.classList.add("avatar-window-body");
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {isAvatarWindow ? <AvatarWindow /> : <App />}
  </React.StrictMode>
);
