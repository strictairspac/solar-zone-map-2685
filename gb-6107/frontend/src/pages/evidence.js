import { api } from "../api/workbench.js";
import { errorText, field } from "../components/common/fields.js";
import { empty, pageHeading, section } from "../components/common/panel.js";
import { purgeStatus } from "../components/common/status.js";
import { resultTable } from "../components/common/table.js";
import { submit } from "../hooks/submit.js";
import { el } from "../utils/dom.js";
import { cell, download, time } from "../utils/format.js";

function reviewForm(id, saved) {
  const form = el("form", {id: "review-form"},
    field("复核意见", el("textarea", {name: "note", required: true, minlength: 3, maxlength: 500, rows: 3})),
    errorText(), el("button", {type: "submit"}, "签署复核"));
  submit(form, async values => saved(await api.submitReview(id, {note: values.get("note")})));
  return form;
}

function signature(review) {
  return el("div", {"data-testid": "reviewed", class: "signature"},
    el("strong", {}, `已签署 · ${review.actor}`), el("p", {}, review.note), el("time", {}, time(review.created_at)));
}

/** Evidence shown for a run: its live result, or the copy frozen into its receipt. */
export function receiptEvidence(run, review) {
  if (run?.result) return run.result;
  if (review?.evidence) return review.evidence;
  return null;
}

function purgeProgress(progress) {
  if (!progress) return null;
  const facts = [
    ["清退状态", purgeStatus(progress)],
    ["到期时间", time(progress.expires_at)],
    ["已接收抽检", progress.accepted_runs],
    ["待完成抽检", progress.pending_runs],
    ["原始读数", progress.readings_retained ? "保留" : "已清退"],
    ["执行副本", progress.copies_retained ? "保留中" : "已清退"],
  ];
  if (progress.started_at) facts.push(["开始清退", time(progress.started_at)]);
  if (progress.purged_at) facts.push(["清退完成", time(progress.purged_at)]);
  return section("质保批清退进度", el("dl", {class: "metrics", "data-testid": "receipt-purge-progress"},
    facts.map(([label, value]) => el("div", {}, el("dt", {}, label), el("dd", {}, value)))));
}

export async function evidencePage(config, user, route) {
  const runs = (await api.runs()).filter(item => item.status === "done");
  const run = route.id ? await api.run(route.id) : runs[0];
  const review = run ? await api.review(run.id) : null;
  const evidence = receiptEvidence(run, review);
  if (!run) return el("div", {class: "page"},
    pageHeading(config.modules[3], null), empty("成功执行一个批次后可以查看、签核和下载证据。"),
    el("a", {href: "#runs"}, config.modules[2]));
  if (!evidence) return el("div", {class: "page"},
    pageHeading(config.modules[3], run.case_title), empty("该批次的执行副本已随质保批清退，且没有签署回执可保留。"),
    el("a", {href: "#runs"}, config.modules[2]));

  const batch = await api.case(run.case_id);
  const purged = !run.result;
  const issue = errorText();
  const button = el("button", {type: "button", onclick: async () => {
    button.disabled = true;
    issue.textContent = "";
    try {
      await download(await api.export(run.id), `evidence-${run.id}.json`);
    } catch (error) {
      issue.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }}, "导出证据");
  const signing = el("div", {});
  signing.append(review ? signature(review) :
    purged ? empty("该批次的执行副本已清退，不能再签署新的复核。") :
    user.role === "reviewer" ? reviewForm(run.id, data => signing.replaceChildren(signature(data))) :
    empty("待复核员签署。"));
  const options = el("select", {"aria-label": "选择已完成的批次", onchange: event => {
    location.hash = `evidence/${event.target.value}`;
  }}, runs.map(item => el("option", {value: item.id, selected: item.id === run.id}, `#${item.id} ${item.case_title}`)));
  return el("div", {class: "page evidence"},
    pageHeading(config.modules[3], run.case_title, button),
    issue, options,
    purged ? el("p", {class: "empty", "data-testid": "purge-note"},
      `执行副本已随质保批清退，以下为签署回执保留的当时依据（清退于 ${time(run.purged_at)}）。`) : null,
    el("section", {class: "feature evidence-summary"}, el("div", {}, el("h2", {}, "批次判定"), el("p", {}, evidence.summary)),
      el("details", {}, el("summary", {}, "证据摘要"), el("code", {}, evidence.digest))),
    el("dl", {class: "metrics"}, Object.entries(evidence.metrics).map(([label, value]) =>
      el("div", {}, el("dt", {}, label), el("dd", {}, cell(value))))),
    section("业务结果明细", evidence.rows.length ? resultTable(evidence.rows) : empty("此批次无明细。")),
    section("复核签署", signing),
    purgeProgress(batch?.progress));
}
