import { createElement } from "react";

import { apiFetch } from "./api";

/** Load module settings; clears stale errors on success. */
export function loadSettings(path, setForm, setError) {
  setError("");
  return apiFetch(path)
    .then((data) => {
      setForm(data);
      setError("");
    })
    .catch((err) => {
      setError(err.message);
    });
}

/** Save module settings; only one of error/saved should show at a time. */
export async function saveSettings(path, form, { setForm, setError, setSaved }) {
  setError("");
  setSaved(false);
  try {
    const data = await apiFetch(path, { method: "PUT", body: JSON.stringify(form) });
    setForm(data);
    setError("");
    setSaved(true);
  } catch (err) {
    setSaved(false);
    setError(err.message);
  }
}

/** Show either the error or success line — never both. */
export function SettingsStatusMessages({ error, saved, savedText = "Settings saved." }) {
  if (error) {
    return createElement("p", { className: "crm-error crm-mt" }, error);
  }
  if (saved) {
    return createElement("p", { className: "crm-success crm-mt" }, savedText);
  }
  return null;
}
