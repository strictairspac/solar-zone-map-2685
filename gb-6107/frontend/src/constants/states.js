export const States = Object.freeze({
  queued: "等待执行", done: "已完成", failed: "执行失败",
});

export const PurgeStates = Object.freeze({
  active: "保留原始读数", purging: "清退中", purged: "已清退",
});

export const Actions = Object.freeze({
  create_case: "登记资料", enqueue: "提交执行", done: "执行完成", failed: "执行失败", review: "复核签署",
  purge_start: "开始清退", purge_done: "清退完成",
});
