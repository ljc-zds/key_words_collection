#!/usr/bin/env python3
"""Build a self-contained local keyword site-opportunity report."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


EXCLUSION_LABELS = {
    "low_volume": "搜索量不足",
    "navigational": "导航/品牌意图",
    "no_site_fit": "缺少建站承接形态",
    "high_kd": "竞争度过高",
    "missing_metrics": "核心指标缺失",
    "ambiguous_acronym": "缩写含义不明确",
    "question_page": "泛问答页面",
    "policy_risk": "版权或政策风险",
    "weak_comparison": "比较意图偏弱",
    "weak_review": "评测意图偏弱",
    "ambiguous": "搜索意图不明确",
    "physical_product": "实体商品需求",
    "career_query": "招聘/职业需求",
    "branded_product": "品牌产品词",
    "india_market": "印度市场专属需求",
    "local_navigation": "本地导航需求",
    "low_score": "综合评分不足",
    "unclear_tool": "工具形态不明确",
    "physical_tool": "实体工具需求",
    "sports_event": "赛事时效词",
    "non_english": "非英语目标市场",
    "ambiguous_trade": "交易场景不明确",
}


def _fmt_date(value: str | None) -> str:
    if not value:
        return "暂无数据"
    return value[:10]


def _top_names(counter: dict[str, int], limit: int = 3) -> str:
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    return "、".join(name for name, _ in ranked) or "暂无数据"


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build_html(result: dict[str, Any]) -> str:
    """Return a complete offline HTML report from the canonical accepted dataset."""
    summary = result.get("summary", {})
    metadata = result.get("metadata", {})
    projects = result.get("projects", [])
    keywords = result.get("keywords", [])
    accepted = int(summary.get("accepted_keywords", len(keywords)))
    project_count = int(summary.get("project_count", len(projects)))
    raw = int(summary.get("raw_unique_keywords", accepted))
    excluded = int(summary.get("excluded_keywords", max(raw - accepted, 0)))
    priorities = summary.get("priorities", {})
    site_types = summary.get("site_types", {})
    source_statuses = summary.get("source_statuses", {})
    exclusion_counts = summary.get("exclusion_counts", {})
    p0_projects = sum(1 for project in projects if project.get("priority") == "P0")
    top_project = projects[0].get("project_name", "暂无数据") if projects else "暂无数据"

    client_data = {
        "metadata": metadata,
        "summary": summary,
        "projects": projects,
        "keywords": keywords,
        "exclusion_labels": EXCLUSION_LABELS,
    }
    data_json = _json_for_script(client_data)
    title = "关键词建站机会分析"
    generated = _fmt_date(metadata.get("analysis_generated_at"))
    refreshed = _fmt_date(metadata.get("latest_source_retrieved_at"))
    scope = html.escape(str(metadata.get("market_scope", "Similarweb Global / Semrush US")))
    method_version = html.escape(str(metadata.get("method_version", "local-site-fit")))
    top_types = html.escape(_top_names(site_types))
    top_project_escaped = html.escape(str(top_project))

    return f'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{title}</title>
  <style>
    :root{{--ink:#172331;--muted:#617080;--navy:#17354d;--teal:#147d76;--amber:#b56b12;--red:#b9463f;--line:#d9e1e7;--paper:#fff;--wash:#f4f7f8;--soft:#edf4f3}}
    *{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;background:var(--wash);color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;letter-spacing:0}}
    button,input,select{{font:inherit;letter-spacing:0}} button{{cursor:pointer}} .shell{{max-width:1440px;margin:auto;background:var(--paper);min-height:100vh;box-shadow:0 0 0 1px rgba(23,53,77,.05)}}
    header{{background:var(--navy);color:#fff;padding:32px clamp(20px,4vw,56px) 28px}} .eyebrow{{color:#9dd8d2;font-size:12px;font-weight:700;text-transform:uppercase}} h1{{font-size:clamp(28px,4vw,46px);line-height:1.12;margin:7px 0 10px;letter-spacing:0}} .subtitle{{max-width:850px;color:#dce7ed;margin:0}}
    .meta{{display:flex;flex-wrap:wrap;gap:8px 22px;margin-top:20px;color:#bfcdd6;font-size:12px}} nav{{position:sticky;top:0;z-index:10;overflow:auto;white-space:nowrap;background:#fff;border-bottom:1px solid var(--line);padding:0 clamp(20px,4vw,56px)}} nav a{{display:inline-block;color:#34495a;text-decoration:none;padding:13px 14px;border-bottom:3px solid transparent}} nav a:hover{{border-color:var(--teal);color:var(--teal)}}
    main{{padding:28px clamp(20px,4vw,56px) 60px}} section{{scroll-margin-top:60px;margin:0 0 44px}} h2{{font-size:21px;margin:0 0 18px}} h3{{font-size:15px;margin:0 0 10px}} .notice{{border-left:4px solid var(--amber);background:#fff8e9;padding:13px 16px;margin-bottom:24px;color:#5f4a28}}
    .metrics{{display:grid;grid-template-columns:repeat(5,minmax(130px,1fr));gap:10px}} .metric{{border:1px solid var(--line);border-radius:6px;padding:16px;background:#fff}} .metric strong{{display:block;font-size:25px;line-height:1.15;color:var(--navy)}} .metric span{{color:var(--muted);font-size:12px}} .metric.accent strong{{color:var(--teal)}}
    .summary-band{{display:grid;grid-template-columns:1.25fr .75fr;gap:24px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:22px 0}} .summary-band p{{margin:0}} .callout{{background:var(--soft);padding:16px;border-radius:6px}} .callout strong{{display:block;color:var(--teal);font-size:16px}}
    .chart-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}} .chart{{border:1px solid var(--line);border-radius:6px;padding:16px;min-width:0}} .bar-row{{display:grid;grid-template-columns:minmax(92px,1.25fr) 2fr 44px;gap:8px;align-items:center;margin:9px 0;font-size:12px}} .bar-label{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}} .track{{height:8px;background:#e9eef1;border-radius:4px;overflow:hidden}} .fill{{display:block;height:100%;background:var(--teal);border-radius:4px}} .bar-row:nth-child(even) .fill{{background:var(--amber)}} .bar-value{{text-align:right;font-variant-numeric:tabular-nums}}
    .toolbar{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}} .toolbar input,.toolbar select{{border:1px solid #becbd4;border-radius:5px;background:#fff;padding:8px 10px;color:var(--ink);min-height:38px}} .toolbar input{{min-width:240px;flex:1}} .count{{align-self:center;color:var(--muted);font-size:12px;margin-left:auto}}
    .table-wrap{{border:1px solid var(--line);border-radius:6px;overflow:auto;max-height:650px}} table{{border-collapse:collapse;width:100%;min-width:980px}} th{{position:sticky;top:0;z-index:2;background:var(--navy);color:#fff;font-size:12px;text-align:left;padding:10px;white-space:nowrap}} td{{padding:10px;border-bottom:1px solid #e5eaee;vertical-align:top}} tbody tr:hover{{background:#f0f7f6}} .num{{text-align:right;font-variant-numeric:tabular-nums}} .pill{{display:inline-block;min-width:34px;text-align:center;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:700}} .p0{{background:#dcefe8;color:#11604e}} .p1{{background:#fff0cf;color:#875009}} .p2{{background:#e7eef3;color:#40566a}} .detail-btn{{border:1px solid #aac0cd;background:#fff;color:var(--navy);border-radius:4px;padding:5px 9px}} .detail-btn:hover{{border-color:var(--teal);color:var(--teal)}}
    .details{{display:none;position:fixed;inset:0;z-index:30;background:rgba(18,33,44,.38)}} .details.open{{display:block}} .panel{{position:absolute;right:0;top:0;height:100%;width:min(560px,94vw);overflow:auto;background:#fff;padding:26px;box-shadow:-8px 0 24px rgba(17,35,48,.16)}} .panel-head{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;border-bottom:1px solid var(--line);padding-bottom:15px}} .panel-head h2{{margin:0}} .close{{width:36px;height:36px;border:1px solid var(--line);background:#fff;border-radius:50%;font-size:22px;line-height:1}} .detail-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:18px 0}} .detail-item{{border-bottom:1px solid var(--line);padding-bottom:8px}} .detail-item span{{display:block;color:var(--muted);font-size:11px}} .detail-item strong{{word-break:break-word}} .detail-section{{margin-top:20px}} .keyword-list{{display:flex;flex-wrap:wrap;gap:6px}} .keyword-list span{{background:#eef3f5;border-radius:4px;padding:5px 8px}}
    .method{{display:grid;grid-template-columns:1fr 1fr;gap:24px}} .score-list{{margin:0;padding-left:20px}} .score-list li{{margin:7px 0}} .risk-table table{{min-width:520px}} .steps{{counter-reset:step;display:grid;grid-template-columns:repeat(4,1fr);gap:10px}} .step{{border-top:3px solid var(--teal);background:#f7faf9;padding:14px}} .step:before{{counter-increment:step;content:counter(step);display:block;color:var(--teal);font-weight:800;font-size:20px}} footer{{border-top:1px solid var(--line);padding:22px clamp(20px,4vw,56px);color:var(--muted);font-size:12px}}
    @media(max-width:980px){{.metrics{{grid-template-columns:repeat(3,1fr)}}.chart-grid{{grid-template-columns:1fr 1fr}}.steps{{grid-template-columns:1fr 1fr}}}}
    @media(max-width:680px){{header{{padding-top:24px}}main{{padding-top:20px}}.metrics{{grid-template-columns:1fr 1fr}}.chart-grid,.summary-band,.method{{grid-template-columns:1fr}}.steps{{grid-template-columns:1fr}}.toolbar{{align-items:stretch}}.toolbar input,.toolbar select{{width:100%;min-width:0}}.count{{width:100%;margin-left:0}}.detail-grid{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
<div class="shell">
  <header>
    <div class="eyebrow">Local keyword intelligence</div>
    <h1>{title}</h1>
    <p class="subtitle">从本地 Similarweb 与 Semrush 数据中筛出可形成明确产品或内容资产的英语关键词，并按建站项目聚类排序。</p>
    <div class="meta"><span>分析日期：{generated}</span><span>数据更新：{refreshed}</span><span>市场口径：{scope}</span><span>方法版本：{method_version}</span></div>
  </header>
  <nav><a href="#overview">概览</a><a href="#distribution">机会结构</a><a href="#projects">项目排名</a><a href="#keywords">关键词明细</a><a href="#method">口径与风险</a></nav>
  <main>
    <div class="notice"><strong>本报告没有调用 SERP 接口。</strong> 所有结论仅基于现有本地数据；每个候选项目在开发前仍需人工复核 Google SERP、品牌、版权与域名风险。</div>

    <section id="overview">
      <h2>机会概览</h2>
      <div class="metrics">
        <div class="metric"><strong>{raw:,}</strong><span>原始唯一关键词</span></div>
        <div class="metric accent" aria-label="{accepted:,} 个合格关键词"><strong>{accepted:,}</strong><span>个合格关键词</span></div>
        <div class="metric accent" aria-label="{project_count:,} 个建站项目"><strong>{project_count:,}</strong><span>个建站项目</span></div>
        <div class="metric"><strong>{p0_projects:,}</strong><span>P0 建站项目</span></div>
        <div class="metric"><strong>{excluded:,}</strong><span>规则淘汰关键词</span></div>
      </div>
      <div class="summary-band">
        <p><strong>结论：</strong>当前机会集中在 {top_types}。优先从用户动作清晰、单页可交付结果且维护成本可控的项目开始。排名第一的项目是 <strong>{top_project_escaped}</strong>，但排名反映本地需求、难度和产品化信号，不代表已经确认真实 SERP 空档。</p>
        <div class="callout"><strong>先验证，再开发</strong>P0 用于安排人工验证顺序；P1 适合进入候选池；P2 更适合作为同主题扩展页或备选项目。</div>
      </div>
    </section>

    <section id="distribution">
      <h2>机会结构</h2>
      <div class="chart-grid">
        <div class="chart"><h3>优先级分布</h3><div id="priority-chart"></div></div>
        <div class="chart"><h3>数据来源分布</h3><div id="source-chart"></div></div>
        <div class="chart"><h3>站点类型分布</h3><div id="type-chart"></div></div>
      </div>
    </section>

    <section id="projects">
      <h2>建站项目排名</h2>
      <div class="toolbar">
        <input id="project-search" type="search" placeholder="搜索项目或主关键词" aria-label="搜索项目">
        <select id="project-priority" aria-label="项目优先级"><option value="">全部优先级</option><option>P0</option><option>P1</option><option>P2</option></select>
        <select id="project-type" aria-label="项目站点类型"><option value="">全部站点类型</option></select>
        <span class="count" id="project-count"></span>
      </div>
      <div class="table-wrap"><table><thead><tr><th>排名</th><th>优先级</th><th>项目</th><th>主关键词</th><th>站点类型</th><th class="num">得分</th><th class="num">关键词数</th><th class="num">需求量</th><th class="num">KD</th><th>操作</th></tr></thead><tbody id="project-table-body"></tbody></table></div>
    </section>

    <section id="keywords">
      <h2>合格关键词明细</h2>
      <div class="toolbar">
        <input id="keyword-search" type="search" placeholder="搜索关键词或所属项目" aria-label="搜索关键词">
        <select id="keyword-priority" aria-label="关键词优先级"><option value="">全部优先级</option><option>P0</option><option>P1</option><option>P2</option></select>
        <select id="keyword-source" aria-label="关键词来源"><option value="">全部来源</option></select>
        <select id="keyword-type" aria-label="关键词站点类型"><option value="">全部站点类型</option></select>
        <span class="count" id="keyword-count"></span>
      </div>
      <div class="table-wrap"><table><thead><tr><th>排名</th><th>优先级</th><th>关键词</th><th>项目</th><th>站点类型</th><th>来源</th><th class="num">得分</th><th class="num">需求量</th><th class="num">保守 KD</th><th class="num">Semrush CPC</th><th>操作</th></tr></thead><tbody id="keyword-table-body"></tbody></table></div>
    </section>

    <section id="method">
      <h2>评分口径与风险</h2>
      <div class="method">
        <div><h3>100 分结构</h3><ul class="score-list"><li>搜索需求 20 分：采用可用平台中的最高搜索量分档，不跨平台相加。</li><li>SEO 可进入性 25 分：采用两个来源中更保守的 KD。</li><li>产品化程度 20 分：必须能识别工具、资源、比较或内容集群形态。</li><li>变现能力 15 分：参考 CPC、意图和站点类型。</li><li>扩展能力 10 分；数据可信度 10 分；另计明确风险扣分。</li><li>P0 ≥ 80，P1 为 70–79.9，P2 为 60–69.9。</li></ul></div>
        <div class="risk-table"><h3>主要淘汰原因</h3><div class="table-wrap"><table><thead><tr><th>原因</th><th class="num">数量</th><th class="num">占淘汰词</th></tr></thead><tbody id="exclusion-body"></tbody></table></div></div>
      </div>
      <div class="notice" style="margin-top:20px"><strong>限制：</strong>Similarweb Global 与 Semrush US 的指标定义和市场口径不同；搜索量不可相加，KD 仅作竞争参考，CPC 不等于实际收入。“适合建站”也不保证获得流量或收入，且本次未进行实时 SERP 验证。</div>
    </section>

    <section>
      <h2>执行顺序</h2>
      <div class="steps"><div class="step">从 P0 中选择 5–10 个项目做人工 SERP 复核。</div><div class="step">检查弱站、内容缺口、品牌版权和域名风险。</div><div class="step">选 1–2 个需求动作最明确的项目定义 MVP。</div><div class="step">上线后按访问、留存与收入信号决定扩展。</div></div>
    </section>
  </main>
  <footer>本地分析结果 · {generated} · 仅包含通过筛选的关键词</footer>
</div>

<div class="details" id="detail-panel" role="dialog" aria-modal="true" aria-labelledby="detail-title">
  <div class="panel"><div class="panel-head"><h2 id="detail-title">详情</h2><button class="close" id="detail-close" aria-label="关闭详情">×</button></div><div id="detail-content"></div></div>
</div>
<script type="application/json" id="analysis-data">{data_json}</script>
<script>
const DATA=JSON.parse(document.getElementById('analysis-data').textContent);
const $=id=>document.getElementById(id);
const esc=value=>String(value??'暂无数据').replace(/[&<>"']/g,ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
const number=value=>value===null||value===undefined||value===''?'—':Number(value).toLocaleString('en-US',{{maximumFractionDigits:1}});
const money=value=>value===null||value===undefined||value===''?'—':'$'+Number(value).toFixed(2);
const pill=value=>`<span class="pill ${{String(value).toLowerCase()}}">${{esc(value)}}</span>`;

function fillSelect(id,values){{const select=$(id);[...new Set(values.filter(Boolean))].sort().forEach(value=>select.insertAdjacentHTML('beforeend',`<option>${{esc(value)}}</option>`));}}
function bars(id,entries,total){{const max=Math.max(1,...entries.map(([,v])=>v));$(id).innerHTML=entries.map(([label,value])=>`<div class="bar-row" title="${{esc(label)}}：${{number(value)}}"><span class="bar-label">${{esc(label)}}</span><span class="track"><span class="fill" style="width:${{(value/max*100).toFixed(1)}}%"></span></span><span class="bar-value">${{number(value)}}</span></div>`).join('')||'<p>暂无数据</p>';}}

function renderProjects(){{
  const query=$('project-search').value.trim().toLowerCase(),priority=$('project-priority').value,type=$('project-type').value;
  const rows=DATA.projects.filter(item=>(!query||`${{item.project_name}} ${{item.main_keyword}} ${{(item.keywords||[]).join(' ')}}`.toLowerCase().includes(query))&&(!priority||item.priority===priority)&&(!type||item.site_type===type));
  $('project-count').textContent=`显示 ${{rows.length}} / ${{DATA.projects.length}} 个项目`;
  $('project-table-body').innerHTML=rows.map((item,index)=>`<tr><td>${{number(item.rank)}}</td><td>${{pill(item.priority)}}</td><td><strong>${{esc(item.project_name)}}</strong></td><td>${{esc(item.main_keyword)}}</td><td>${{esc(item.site_type)}}</td><td class="num">${{number(item.score)}}</td><td class="num">${{number(item.keyword_count)}}</td><td class="num">${{number(item.main_volume)}}</td><td class="num">${{number(item.main_kd)}}</td><td><button class="detail-btn" data-project-rank="${{item.rank}}">详情</button></td></tr>`).join('')||'<tr><td colspan="10">没有符合条件的项目</td></tr>';
}}

function renderKeywords(){{
  const query=$('keyword-search').value.trim().toLowerCase(),priority=$('keyword-priority').value,source=$('keyword-source').value,type=$('keyword-type').value;
  const rows=DATA.keywords.filter(item=>(!query||`${{item.keyword}} ${{item.project_name}}`.toLowerCase().includes(query))&&(!priority||item.priority===priority)&&(!source||item.source_status===source)&&(!type||item.site_type===type));
  $('keyword-count').textContent=`显示 ${{rows.length}} / ${{DATA.keywords.length}} 个关键词`;
  $('keyword-table-body').innerHTML=rows.map(item=>`<tr><td>${{number(item.rank)}}</td><td>${{pill(item.priority)}}</td><td><strong>${{esc(item.keyword)}}</strong></td><td>${{esc(item.project_name)}}</td><td>${{esc(item.site_type)}}</td><td>${{esc(item.source_status)}}</td><td class="num">${{number(item.score)}}</td><td class="num">${{number(item.demand_volume)}}</td><td class="num">${{number(item.conservative_kd)}}</td><td class="num">${{money(item.semrush_cpc)}}</td><td><button class="detail-btn" data-keyword-rank="${{item.rank}}">详情</button></td></tr>`).join('')||'<tr><td colspan="11">没有符合条件的关键词</td></tr>';
}}

function showDetail(kind,rank){{
  const item=(kind==='project'?DATA.projects:DATA.keywords).find(row=>Number(row.rank)===Number(rank));if(!item)return;
  $('detail-title').textContent=kind==='project'?item.project_name:item.keyword;
  const metrics=kind==='project'
    ?[['优先级',item.priority],['综合得分',number(item.score)],['站点类型',item.site_type],['主关键词',item.main_keyword],['需求量',number(item.main_volume)],['保守 KD',number(item.main_kd)],['关键词数量',number(item.keyword_count)],['SERP 状态','未进行实时 SERP 验证']]
    :[['优先级',item.priority],['综合得分',number(item.score)],['站点类型',item.site_type],['所属项目',item.project_name],['来源',item.source_status],['需求量',number(item.demand_volume)],['保守 KD',number(item.conservative_kd)],['Semrush CPC',money(item.semrush_cpc)],['Similarweb 量 / KD',`${{number(item.similarweb_volume)}} / ${{number(item.similarweb_kd)}}`],['Semrush 量 / KD',`${{number(item.semrush_volume)}} / ${{number(item.semrush_kd)}}`]];
  const reason=item.reason||item.decision_reason||'暂无数据';
  const purpose=kind==='keyword'?`<div class="detail-section"><h3>关键词用途说明</h3><p>${{esc(item.keyword_purpose||'暂无数据')}}</p></div>`:'';
  $('detail-content').innerHTML=`<div class="detail-grid">${{metrics.map(([label,value])=>`<div class="detail-item"><span>${{esc(label)}}</span><strong>${{esc(value)}}</strong></div>`).join('')}}</div>${{purpose}}<div class="detail-section"><h3>推荐理由</h3><p>${{esc(reason)}}</p></div><div class="detail-section"><h3>变现方式</h3><p>${{esc(item.monetization)}}</p></div><div class="detail-section"><h3>风险说明</h3><p>${{esc(item.risk_notes)}}</p></div>${{kind==='project'?`<div class="detail-section"><h3>包含关键词</h3><div class="keyword-list">${{(item.keywords||[]).map(word=>`<span>${{esc(word)}}</span>`).join('')}}</div></div>`:''}}<div class="notice" style="margin-top:20px">未进行实时 SERP 验证</div>`;
  $('detail-panel').classList.add('open');document.body.style.overflow='hidden';
}}
function closeDetail(){{$('detail-panel').classList.remove('open');document.body.style.overflow='';}}

fillSelect('project-type',DATA.projects.map(item=>item.site_type));
fillSelect('keyword-type',DATA.keywords.map(item=>item.site_type));
fillSelect('keyword-source',DATA.keywords.map(item=>item.source_status));
bars('priority-chart',Object.entries(DATA.summary.priorities||{{}}),DATA.keywords.length);
bars('source-chart',Object.entries(DATA.summary.source_statuses||{{}}),DATA.keywords.length);
bars('type-chart',Object.entries(DATA.summary.site_types||{{}}),DATA.keywords.length);
$('exclusion-body').innerHTML=Object.entries(DATA.summary.exclusion_counts||{{}}).sort((a,b)=>b[1]-a[1]).map(([code,value])=>`<tr><td>${{esc(DATA.exclusion_labels[code]||code)}}</td><td class="num">${{number(value)}}</td><td class="num">${{DATA.summary.excluded_keywords?`${{(value/DATA.summary.excluded_keywords*100).toFixed(1)}}%`:'—'}}</td></tr>`).join('');
['project-search','project-priority','project-type'].forEach(id=>$(id).addEventListener(id.includes('search')?'input':'change',renderProjects));
['keyword-search','keyword-priority','keyword-source','keyword-type'].forEach(id=>$(id).addEventListener(id.includes('search')?'input':'change',renderKeywords));
document.addEventListener('click',event=>{{const project=event.target.closest('[data-project-rank]'),keyword=event.target.closest('[data-keyword-rank]');if(project)showDetail('project',project.dataset.projectRank);if(keyword)showDetail('keyword',keyword.dataset.keywordRank);}});
$('detail-close').addEventListener('click',closeDetail);$('detail-panel').addEventListener('click',event=>{{if(event.target===$('detail-panel'))closeDetail();}});document.addEventListener('keydown',event=>{{if(event.key==='Escape')closeDetail();}});
renderProjects();renderKeywords();
</script>
</body>
</html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("outputs/keyword_site_analysis_20260911_local/keyword_site_analysis.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/keyword_site_analysis_20260911_local/关键词建站机会分析.html"))
    args = parser.parse_args()
    result = json.loads(args.input.read_text(encoding="utf-8"))
    page = build_html(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print(f"Wrote {args.output} ({len(result.get('keywords', []))} keywords, {len(result.get('projects', []))} projects)")


if __name__ == "__main__":
    main()
