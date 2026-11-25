/**
 * @typedef {{state:string, expired:boolean, expires_at:number|null, started_at:number|null,
 *   purged_at:number|null, accepted_runs:number, pending_runs:number,
 *   readings_retained:boolean, copies_retained:boolean}} PurgeProgress
 * @typedef {{id:number, code:string, title:string, description:string, payload:Object|null,
 *   created_by:string, progress:PurgeProgress}} Case
 * @typedef {{id:number, case_id:number, case_title:string, status:string, parameter:number,
 *   result:Object|null, accepted_at:number|null, purged_at:number|null}} Run
 * @typedef {{run_id:number, actor:string, note:string, created_at:number, evidence:Object|null}} Review
 */

/** Reject a malformed configuration before rendering its navigation. */
export function validateConfig(config) {
  if (!config || !Array.isArray(config.modules) || config.modules.length !== 4 ||
      !Number.isInteger(config.default_parameter) || !config.title) {
    throw new Error("工作台配置不完整");
  }
  return config;
}
