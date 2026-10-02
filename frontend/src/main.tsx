import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { HttpApi } from "./adapters/httpApi";
import "./styles.css";

const api = new HttpApi("");
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App api={api} />
  </React.StrictMode>,
);
