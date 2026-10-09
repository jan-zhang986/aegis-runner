/**
 * 验证 dsh-plugin-aegis 插件的工具执行与 Node.js 互通
 */
const { runAegisCli } = require('./index');
const path = require('path');

async function testPlugin() {
  console.log('🚀 开始测试 dsh-plugin-aegis Node.js 插件桥接...');

  const config = {
    pythonPath: 'python3',
    cliPath: path.resolve(__dirname, '../../src'),
    workspaceRoot: path.resolve(__dirname, '../../'),
  };

  // 1. 测试 scan 工具
  console.log('1. 正在调用 aegis_scan...');
  const scanRes = await runAegisCli(config, 'scan', ['--dir', config.workspaceRoot]);
  console.log(`✅ Scan 返回成功! 总用例数: ${scanRes.totalCases}, 覆盖需求数: ${scanRes.linkedRequirementsCount}`);
  if (scanRes.cases && scanRes.cases.length > 0) {
    console.log(`   样例用例: [${scanRes.cases[0].id}] ${scanRes.cases[0].title}`);
  }

  // 2. 测试 scaffold 工具
  console.log('\n2. 正在调用 aegis_scaffold...');
  const scaffoldRes = await runAegisCli(config, 'scaffold', [
    '--lang', 'python',
    '--req', 'REQ-DSH-001',
    '--risk', 'P0',
    '--title', '验证 DeepSeek Harness 插件自动化单测生成'
  ]);
  console.log(`✅ Scaffold 返回成功! 生成用例 ID: ${scaffoldRes.caseId}`);
  console.log(`   用例语言: ${scaffoldRes.lang}, 风险: ${scaffoldRes.risk}`);

  // 3. 测试 diff 工具
  console.log('\n3. 正在调用 aegis_diff...');
  const diffRes = await runAegisCli(config, 'diff', ['--base', 'HEAD~1']);
  console.log(`✅ Diff 返回成功! 变更源码数: ${diffRes.totalSourceFilesChanged}, 缺口数: ${diffRes.gapCount}`);

  console.log('\n🎉 dsh-plugin-aegis 核心插件链路 100% 验证通过！');
}

testPlugin().catch((err) => {
  console.error('❌ 测试失败:', err);
  process.exit(1);
});
