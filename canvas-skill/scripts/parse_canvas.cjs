#!/usr/bin/env node
/**
 * parse_canvas.cjs — 把 Obsidian .canvas 架构图机械解析为「可执行契约」文本。
 *
 * 用法:
 *   node parse_canvas.cjs "H:/path/to/架构.canvas"
 *
 * 输出（markdown 到 stdout）:
 *   1. 分组（group 及其包含节点、label 语义）
 *   2. 节点清单（按类型：file / text / group / link），text 节点全文展开
 *   3. 连线清单（含边 label ＝ 条件或产出说明）
 *   4. 拓扑执行序（Kahn）
 *   5. 自动告警（file 未被读取风险、孤立节点、悬空连线、长文本规则节点）
 *
 * 设计目标：消除"把 canvas 当示意图、漏读文字节点/分组/边标签"的隐患。
 */
const fs = require('fs');
const path = require('path');

function main() {
  const file = process.argv[2];
  if (!file) {
    console.error('缺少参数：canvas 文件路径');
    process.exit(1);
  }
  const abs = path.resolve(file);
  const raw = fs.readFileSync(abs, 'utf8');
  let data;
  try {
    data = JSON.parse(raw);
  } catch (e) {
    console.error('canvas 不是合法 JSON：' + e.message);
    process.exit(1);
  }

  const nodes = data.nodes || [];
  const edges = data.edges || [];
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const groups = nodes.filter((n) => n.type === 'group');
  const isInside = (n, g) =>
    n.type !== 'group' &&
    n.x >= g.x && n.y >= g.y &&
    n.x + (n.width || 0) <= g.x + g.width &&
    n.y + (n.height || 0) <= g.y + g.height;

  const groupOf = new Map();
  for (const g of groups) {
    for (const n of nodes) {
      if (isInside(n, g)) groupOf.set(n.id, g);
    }
  }

  const short = (n) => {
    if (!n) return '(缺失节点)';
    if (n.type === 'file') return 'FILE:' + n.file;
    if (n.type === 'group') return 'GROUP:' + (n.label || '');
    if (n.type === 'link') return 'LINK:' + (n.url || '');
    const t = (n.text || '').replace(/\s+/g, ' ').trim();
    return 'TEXT:' + (t.length > 28 ? t.slice(0, 28) + '…' : t);
  };

  const out = [];
  const w = (s) => out.push(s);

  w('# Canvas 契约解析：' + path.basename(abs));
  w('');
  w('> 本输出是**执行契约**，不是示意图描述。所有节点/分组/边标签均为硬约束。');
  w('');

  // ── 1. 分组 ──
  w('## 1. 分组（group 的 label 是语义容器，其内部节点受该 label 约束）');
  w('');
  if (!groups.length) {
    w('- （无分组）');
  } else {
    for (const g of groups) {
      const members = nodes.filter((n) => groupOf.get(n.id) === g);
      w('- **[' + (g.label || '(无label)') + ']** id=' + g.id + '，包含 ' + members.length + ' 个节点：');
      for (const m of members) w('    - ' + short(m));
      if (/约束|全局|规则|constraint/i.test(g.label || '')) {
        w('    - ⚠ 该分组是**全局约束容器**：其内部所有指令必须贯穿全流程，不得当作局部说明。');
      }
    }
  }
  w('');

  // ── 2. 节点 ──
  const files = nodes.filter((n) => n.type === 'file');
  const texts = nodes.filter((n) => n.type === 'text');
  const links = nodes.filter((n) => n.type === 'link');

  w('## 2. 节点清单');
  w('');
  w('### 2.1 文件节点（`file`）—— 必须实际读取，禁止凭印象代写');
  w('');
  if (!files.length) w('- （无）');
  for (const n of files) {
    w('- `' + n.file + '`（id=' + n.id + (groupOf.get(n.id) ? '，分组=' + groupOf.get(n.id).label : '') + '）');
  }
  w('');
  w('### 2.2 指令节点（`text`）—— 逐条执行；长文即为规则全文');
  w('');
  if (!texts.length) w('- （无）');
  texts.forEach((n, i) => {
    const inG = groupOf.get(n.id);
    const tag = inG ? ' ｜ 分组=' + (inG.label || '') : '';
    w('#### 指令节点 ' + (i + 1) + '（id=' + n.id + tag + '，' + (n.text || '').length + ' 字）');
    w('');
    w('```text');
    w((n.text || '').replace(/\r\n/g, '\n'));
    w('```');
    w('');
  });
  if (links.length) {
    w('### 2.3 链接节点（`link`）');
    w('');
    for (const n of links) w('- ' + (n.url || JSON.stringify(n)));
    w('');
  }

  // ── 3. 连线 ──
  w('## 3. 连线（方向＝执行流；边 label＝条件或产出说明）');
  w('');
  if (!edges.length) w('- （无）');
  edges.forEach((e, i) => {
    const f = byId.get(e.fromNode);
    const t = byId.get(e.toNode);
    w((i + 1) + '. ' + short(f) + '  --' + (e.label ? '[' + e.label + ']' : '') + '-->  ' + short(t));
  });
  w('');
  w('> 连线两侧的 `fromSide/toSide` 只表示视觉方位，**不改变语义方向**：`from → to` 即「产出 → 输入」。');
  w('');

  // ── 4. 拓扑执行序 ──
  w('## 4. 拓扑执行序（Kahn；同层内可并行）');
  w('');
  const ids = nodes.map((n) => n.id);
  const indeg = new Map(ids.map((id) => [id, 0]));
  const adj = new Map(ids.map((id) => [id, []]));
  const validEdges = edges.filter((e) => byId.has(e.fromNode) && byId.has(e.toNode));
  for (const e of validEdges) {
    adj.get(e.fromNode).push(e.toNode);
    indeg.set(e.toNode, indeg.get(e.toNode) + 1);
  }
  const q = ids.filter((id) => indeg.get(id) === 0);
  const order = [];
  while (q.length) {
    const cur = q.shift();
    order.push(cur);
    for (const nx of adj.get(cur)) {
      indeg.set(nx, indeg.get(nx) - 1);
      if (indeg.get(nx) === 0) q.push(nx);
    }
  }
  order.forEach((id, i) => w((i + 1) + '. ' + short(byId.get(id))));
  if (order.length < ids.length) {
    const rest = ids.filter((id) => !order.includes(id));
    w('');
    w('⚠ 存在环或未排序节点：');
    for (const id of rest) w('- ' + short(byId.get(id)));
  }
  w('');

  // ── 5. 告警 ──
  w('## 5. 自动告警（必须逐条回应）');
  w('');
  const mentionedInEdge = new Set();
  for (const e of validEdges) { mentionedInEdge.add(e.fromNode); mentionedInEdge.add(e.toNode); }
  const isolated = nodes.filter((n) => n.type !== 'group' && !mentionedInEdge.has(n.id));
  if (files.length) w('- ⚠ 存在 ' + files.length + ' 个文件节点，必须在生成前**逐个打开读取**，并核对语义（文件名含「规则/说明/规范/模板」的往往是约束，不是产物）。');
  if (isolated.length) {
    w('- ⚠ 孤立节点（无连线，极易被漏读）：');
    for (const n of isolated) w('    - ' + short(n));
  }
  const noLabelEdges = validEdges.filter((e) => !e.label);
  w('- 边标签缺失 ' + noLabelEdges.length + '/' + validEdges.length + ' 条：这些连线只有流向，语义靠上下文推断，需显式写清。');
  const dangling = edges.filter((e) => !byId.has(e.fromNode) || !byId.has(e.toNode));
  if (dangling.length) w('- ⚠ 悬空连线 ' + dangling.length + ' 条（端点节点不存在）。');
  w('- ⚠ 完成自检：必须输出「节点核对表」，逐节点标注 已执行/不适用＋依据，禁止跳过任何 text/file 节点。');
  w('');

  // ── 6. skill 调用清单（强制）──
  w('## 6. skill 调用清单（强制调用 + 按连线维度调用）');
  w('');
  w('> canvas 点名 skill 的节点必须**实际调用**；调用位置由连线决定：');
  w('> 入边＝输入来源，出边＝产出与去向，位置＝时序。只读说明不执行＝未执行。');
  w('');
  const skillNodes = nodes.filter((n) => n.type === 'text' && /（skill）|\(skill\)|skill/i.test(n.text || ''));
  if (!skillNodes.length) {
    w('- （未识别到 skill 节点）');
  } else {
    skillNodes.forEach((n, i) => {
      const ins = validEdges.filter((e) => e.toNode === n.id);
      const outs = validEdges.filter((e) => e.fromNode === n.id);
      w('### S' + (i + 1) + '. ' + short(n));
      w('- **调用要求**：必须实际调用该 skill，并产出其定义产物。');
      w('- **输入（入边）**：' + (ins.length ? ins.map((e) => short(byId.get(e.fromNode)) + (e.label ? ' --[' + e.label + ']' : '')).join('；') : '（无入边，需向用户确认输入）'));
      w('- **产出与去向（出边）**：' + (outs.length ? outs.map((e) => short(byId.get(e.toNode)) + (e.label ? ' --[' + e.label + ']' : '')).join('；') : '（无出边，需向用户确认去向）'));
      w('- **时序**：只能在本节点所在步骤调用，禁止提前/延后/合并/跳过。');
      w('');
    });
  }

  process.stdout.write(out.join('\n'));
}

main();
