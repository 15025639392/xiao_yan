import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/index";
import "./memory.css";
import "./styles/workbench.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
