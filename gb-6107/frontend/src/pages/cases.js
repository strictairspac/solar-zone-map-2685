import { api } from "../api/workbench.js";
import { errorText, field } from "../components/common/fields.js";
import { empty, pageHeading, section } from "../components/common/panel.js";
import { purgeStatus } from "../components/common/status.js";
import { table } from "../components/common/table.js";
import { submit } from "../hooks/submit.js";
import { navigate } from "../router/router.js";
import { el } from "../utils/dom.js";
import { time } from "../utils/format.js";

function queueForm(config, selected) {
  const form = el("form", {class: "queue-form"},
    field(config.parameter_label, el("input", {
      name: "parameter", type: "number", min: 1, max: config.max_parameter, required: true, value: config.default_parameter,
    })),
    el("button", {type: "submit"}, "提交执行"), errorText());
  submit(form, async values => {
    const run = await api.enqueue(selected.id, {parameter: Number(values.get("parameter"))});
    navigate(`runs/${run.id}`);
  });
  return form;
}

function registration(config, selected) {
  const data = selected?.payload ? JSON.stringify(selected.payload, null, 2) : "{}";
  const form = el("form", {id: "case-form"},
    field("名称", el("input", {name: "title", required: true, minlength: 2, maxlength: 120, value: selected ? `${selected.title} · 复演` : ""})),
    field("说明", el("input", {name: "description", maxlength: 420, value: selected?.description || ""})),
    field("质保到期时间", el("input", {name: "expiry", type: "datetime-local"}), "到期后不再接收该批的新抽检，并清退原始读数。留空表示不设到期。"),
    field(`${config.unit}内容`, el("textarea", {name: "payload", spellcheck: "false", required: true, rows: 12}, data),
      selected?.payload ? "可以保留演示数据，也可以编辑 JSON 后保存。" :
      selected ? "该质保批的原始读数已清退，复演需重新录入业务数据。" : "输入业务 JSON。"),
    errorText(), el("button", {type: "submit"}, "保存资料"));
  submit(form, async values => {
    let payload;
    try {
      payload = JSON.parse(values.get("payload"));
    } catch {
      throw new Error("资料 JSON 无法解析，请检查括号、引号和逗号");
    }
    const expiry = values.get("expiry");
    const entry = await api.createCase({
      title: values.get("title"), description: values.get("description"), payload,
      expires_at: expiry ? Math.floor(new Date(expiry).getTime() / 1000) : null,
    });
    navigate(`cases/${entry.id}`);
  });
  return form;
}

function progressFacts(progress) {
  const facts = [
    ["到期时间", time(progress.expires_at)],
    ["已接收抽检", progress.accepted_runs],
    ["待完成抽检", progress.pending_runs],
    ["原始读数", progress.readings_retained ? "保留" : "已清退"],
    ["执行副本", progress.copies_retained ? "保留中" : "已清退"],
  ];
  if (progress.started_at) facts.push(["开始清退", time(progress.started_at)]);
  if (progress.purged_at) facts.push(["清退完成", time(progress.purged_at)]);
  return el("dl", {class: "metrics", "data-testid": "purge-progress"},
    facts.map(([label, value]) => el("div", {}, el("dt", {}, label), el("dd", {}, value))));
}

function purgePanel(selected, operator) {
  const progress = selected.progress ?? {state: "active"};
  const issue = errorText();
  const facts = progressFacts(progress);
  const refresh = () => window.location.reload();
  if (!operator) {
    return section("清退进度", purgeStatus(progress), facts);
  }
  const button = el("button", {type: "button", disabled: progress.state !== "active" || !progress.expired,
    onclick: async () => {
      button.disabled = true;
      issue.textContent = "";
      try {
        await api.purgeCase(selected.id);
        refresh();
      } catch (error) {
        issue.textContent = error.message;
        button.disabled = false;
      }
    }}, progress.state === "active" ? "清退原始读数" : "已开始清退");
  const hint = progress.state === "active" && !progress.expired ?
    "质保批到期后才能清退原始读数。" :
    progress.state === "purging" ? "等待已接收的抽检完成后清退执行副本。" :
    progress.state === "purged" ? "原始读数和执行副本均已清退。" : null;
  return section("清退进度", el("div", {class: "stack"}, purgeStatus(progress), button, issue,
    hint ? el("p", {class: "empty"}, hint) : null), facts);
}

export async function casesPage(config, user, route) {
  const cases = await api.cases();
  const selected = cases.find(item => item.id === route.id) ?? cases.at(-1);
  const operator = user.role === "operator";
  const accepting = selected?.progress?.state === "active" && !selected.progress.expired;
  return el("div", {class: "page"},
    pageHeading(config.modules[1], `${config.unit} · ${config.fixture}`),
    section("资料目录", cases.length ? table(["编号", "名称", "说明", "清退", "操作"], cases.map(item =>
      [item.code, item.title, item.description, purgeStatus(item.progress),
        el("a", {href: `#cases/${item.id}`, "aria-current": item.id === selected?.id ? "true" : null}, "选用")]), "资料目录") :
      empty("这里还没有资料。")),
    el("div", {class: "split case-split"},
      section(selected ? selected.title : "等待选择资料", selected ?
        [el("p", {}, selected.description),
          operator ? (accepting ? queueForm(config, selected) :
            empty(selected.progress?.expired && selected.progress.state === "active" ?
              "该质保批已到期，不再接收新的抽检；到期前已接收的抽检仍可完成。" :
              "该质保批已开始清退，不再接收新的抽检。")) : empty("当前账号可查看此资料。"),
          selected.payload ? el("details", {}, el("summary", {}, "查看业务数据"), el("pre", {}, JSON.stringify(selected.payload, null, 2))) :
            el("p", {class: "empty"}, "原始读数已清退，不再保留。")] :
        empty("先登记一条资料，再提交执行。")),
      operator ? section("登记新资料", registration(config, selected)) : null),
    selected ? purgePanel(selected, operator) : null);
}
