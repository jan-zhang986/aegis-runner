/**
 * @vanguard/dsh-plugin-aegis
 * Enterprise Test-as-Code & Quality Gate Plugin for DeepSeek Harness (dsh)
 * Built on the Cordis Microkernel architecture.
 */

const { execFile } = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * Default Plugin Configuration
 */
const defaultConfig = {
  pythonPath: process.env.PYTHON_PATH || 'python3',
  cliPath: path.resolve(__dirname, '../../src'),
  workspaceRoot: process.cwd(),
};

/**
 * Execute Aegis CLI with JSON output
 */
function runAegisCli(config, subcmd, args = []) {
  return new Promise((resolve, reject) => {
    const python = config.pythonPath || 'python3';
    const cliDir = config.cliPath || path.resolve(__dirname, '../../src');
    const fullArgs = ['-m', 'runner.harness_cli', subcmd, ...args, '--json'];

    const env = {
      ...process.env,
      PYTHONPATH: `${cliDir}:${path.resolve(cliDir, '../packages/aegis-sdk')}:${process.env.PYTHONPATH || ''}`,
    };

    execFile(
      python,
      fullArgs,
      {
        cwd: config.workspaceRoot || process.cwd(),
        env,
        maxBuffer: 10 * 1024 * 1024,
      },
      (error, stdout, stderr) => {
        if (error && !stdout) {
          return reject(new Error(`Aegis CLI failed: ${stderr || error.message}`));
        }
        try {
          const jsonRes = JSON.parse(stdout);
          resolve(jsonRes);
        } catch (e) {
          // If not valid JSON, return raw text
          resolve({ raw: stdout, stderr, exitCode: error ? error.code : 0 });
        }
      }
    );
  });
}

/**
 * Cordis Plugin Entrypoint
 * @param {import('cordis').Context} ctx
 * @param {typeof defaultConfig} config
 */
function apply(ctx, config) {
  const cfg = { ...defaultConfig, ...config };

  // 1. Register Tools into DeepSeek Agent Tool Registry
  if (ctx.tools) {
    // 1.1 aegis_scaffold: 给 Agent 快速生成标准化测试用例
    ctx.tools.register({
      name: 'aegis_scaffold',
      description: '生成符合 Aegis 企业级契约的标准化多语言测试用例骨架 (Python / Java / Go)。',
      parameters: {
        type: 'object',
        properties: {
          lang: { type: 'string', enum: ['python', 'java', 'go'], description: '编程语言' },
          req: { type: 'string', description: '关联需求 ID，如 REQ-TRADE-001' },
          risk: { type: 'string', enum: ['P0', 'P1', 'P2', 'P3'], default: 'P1', description: '风险等级' },
          title: { type: 'string', description: '测试用例标题' },
          out: { type: 'string', description: '输出文件相对路径 (可选)' },
        },
        required: ['lang', 'req'],
      },
      execute: async (args) => {
        const cliArgs = ['--lang', args.lang, '--req', args.req];
        if (args.risk) cliArgs.push('--risk', args.risk);
        if (args.title) cliArgs.push('--title', args.title);
        if (args.out) cliArgs.push('--out', args.out);
        return await runAegisCli(cfg, 'scaffold', cliArgs);
      },
    });

    // 1.2 aegis_scan: 秒级 AST 盘点全仓库用例资产
    ctx.tools.register({
      name: 'aegis_scan',
      description: '毫秒级全工程静态 AST 盘点，提取所有带有 @aegis.case 的用例、关联需求、风险等级及步骤列表。',
      parameters: {
        type: 'object',
        properties: {
          dir: { type: 'string', description: '扫描目录 (默认仓库根目录)' },
        },
      },
      execute: async (args) => {
        const cliArgs = [];
        if (args.dir) cliArgs.push('--dir', args.dir);
        return await runAegisCli(cfg, 'scan', cliArgs);
      },
    });

    // 1.3 aegis_diff: Git 变更覆盖缺口分析 (Gap Analysis)
    ctx.tools.register({
      name: 'aegis_diff',
      description: '对比当前 Git 变更行与已有用例，识别出哪些变动代码缺少测试覆盖，输出未测盲区清单与推荐行动。',
      parameters: {
        type: 'object',
        properties: {
          base: { type: 'string', default: 'HEAD~1', description: '基准分支或 Commit SHA' },
        },
      },
      execute: async (args) => {
        const cliArgs = [];
        if (args.base) cliArgs.push('--base', args.base);
        return await runAegisCli(cfg, 'diff', cliArgs);
      },
    });

    // 1.4 aegis_run: 本地极速运行单测并裁决发布五问门禁
    ctx.tools.register({
      name: 'aegis_run',
      description: '本地极速执行指定测试文件或目录，输出结构化步骤证据、耗时、报错堆栈以及发布前质量风控五问答卷。',
      parameters: {
        type: 'object',
        properties: {
          target: { type: 'string', description: '测试文件或目录路径' },
          lang: { type: 'string', enum: ['python', 'java', 'go'], description: '指定语言' },
          base: { type: 'string', default: 'HEAD~1', description: '基准分支用于风控比对' },
        },
      },
      execute: async (args) => {
        const cliArgs = [args.target || '.'];
        if (args.lang) cliArgs.push('--lang', args.lang);
        if (args.base) cliArgs.push('--base', args.base);
        return await runAegisCli(cfg, 'run', cliArgs);
      },
    });
  }

  // 2. Register Web Client UI Slots (if running under dsh web)
  if (ctx.slots) {
    // 注册侧边栏用例资产树插槽
    ctx.slots.register('workbench.sidebar.panel', {
      id: 'aegis-case-catalog',
      title: 'Aegis 用例资产',
      icon: 'shield-check',
      component: 'AegisCaseCatalogPanel',
    });

    // 注册对话流中用例执行卡片插槽
    ctx.slots.register('chat.message.card', {
      id: 'aegis-execution-card',
      match: (message) => message.type === 'tool_result' && message.toolName === 'aegis_run',
      component: 'AegisExecutionReportCard',
    });
  }
}

module.exports = {
  name: 'aegis',
  apply,
  runAegisCli,
};
