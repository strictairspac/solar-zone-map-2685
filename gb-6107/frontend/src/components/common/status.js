import { PurgeStates, States } from "../../constants/states.js";
import { el } from "../../utils/dom.js";

export function status(value) {
  return el("span", {class: `status state-${value}`, "data-state": value}, States[value] || value);
}

export function purgeStatus(progress) {
  const state = progress?.state || "active";
  const label = progress?.expired && state === "active" ? "已到期待清退" : PurgeStates[state] || state;
  return el("span", {class: `status purge-${state}`, "data-purge": state, "data-expired": progress?.expired ? "true" : null}, label);
}
