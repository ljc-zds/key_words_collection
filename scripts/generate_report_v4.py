import json, html
from collections import Counter, defaultdict
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'outputs/keyword_site_analysis_20260911'
data = json.loads((out / 'site_keywords.json').read_text())

def number(x):
    try: return float(x or 0)
    except (TypeError, ValueError): return 0.0

def theme(keyword):
    q = keyword.lower()
    if any(w in q for w in ('calculator','analyzer','planner','generator','checker')): return '计算器和分析工具'
    if any(w in q for w in ('game','minecraft','pokemon','football','fifa','steam','roblox')): return '游戏辅助和数据工具'
    if any(w in q for w in ('download','mp3','video','audio','pdf','image','png')): return '图片、音频、视频处理'
    if any(w in q for w in ('font','template','icon','wallpaper','logo')): return '字体、模板和素材'
    if any(w in q for w in ('meaning','what is','wiki','list','guide')): return '内容解释和资料查询'
    return '其他可产品化需求'

def bucket(value, ranges):
    for label, low, high in ranges:
        if low <= value < high: return label
    return ranges[-1][0]

for item in data: item['_theme'] = theme(str(item.get('keyword','')))
themes = defaultdict(list)
for item in data: themes[item['_theme']].append(item)
source = Counter(str(x.get('provider','未知')) for x in data)
site = Counter(str(x.get('site_type','未知')) for x in data)
priority = Counter(str(x.get('priority','未知')) for x in data)
volume = Counter(bucket(number(x.get('volume')), [('5,000–9,999',5000,10000),('10,000–29,999',10000,30000),('30,000–99,999',30000,100000),('100,000+',100000,float('inf'))]) for x in data)
kd = Counter(bucket(number(x.get('kd')), [('0–30',0,31),('31–45',31,46),('46–60',46,61)]) for x in data)
cpc = Counter(bucket(number(x.get('cpc')), [('0.01–0.49',.01,.5),('0.50–0.99',.5,1),('1.00–2.99',1,3),('3.00+',3,float('inf'))]) for x in data)

def bars(counter):
    top = max(counter.values()) if counter else 1
    return ''.join(f'<div class="bar"><span>{html.escape(k)}</span><i style="width:{max(2,v/top*100):.1f}%"></i><b>{v:,}</b></div>' for k,v in counter.most_common())

theme_rows=[]
for name, items in sorted(themes.items(), key=lambda pair: -len(pair[1])):
    best=max(items,key=lambda x:number(x.get('volume')))
    theme_rows.append(f'<tr><td>{name}</td><td>{len(items):,}</td><td>{sum(number(x.get("volume")) for x in items):,.0f}</td><td>{sum(number(x.get("volume")) for x in items)/len(items):,.0f}</td><td>{sum(number(x.get("kd")) for x in items)/len(items):.1f}</td><td>{sum(number(x.get("cpc")) for x in items)/len(items):.2f}</td><td>{html.escape(str(best.get("keyword","")))}</td></tr>')

doc = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>关键词建站机会分析报告</title><style>body{font:15px Arial,sans-serif;color:#172033;background:#f3f6fa;margin:0}main{max-width:1220px;margin:24px auto;background:#fff;padding:36px}h1{margin-top:0}h2{margin-top:38px;border-left:5px solid #2463a6;padding-left:12px}.cards{display:flex;gap:12px;flex-wrap:wrap}.card{background:#eaf3ff;border-radius:8px;padding:16px 22px;min-width:145px}.card b{font-size:26px}table{border-collapse:collapse;width:100%;margin:12px 0 26px}th{background:#173b63;color:#fff}td,th{padding:9px;border-bottom:1px solid #dce3ea;text-align:left}.grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}.bar{display:flex;align-items:center;gap:8px;margin:10px 0}.bar span{width:145px}.bar i{height:18px;background:#4b91d1;display:inline-block}.bar b{margin-left:auto}.box{background:#f8fafc;border-radius:8px;padding:16px}li{margin:8px 0}@media(max-width:800px){.grid{grid-template-columns:1fr}main{margin:0;padding:20px}}</style></head><body><main>'''
doc += f'<h1>关键词建站机会分析报告</h1><h2>一、报告概览</h2><p>分析日期：2026-09-11　数据更新时间：2026-09-11　数据来源：Similarweb、Semrush　覆盖市场：Global / US</p><div class="cards"><div class="card">原始候选<br><b>15,936</b></div><div class="card">最终保留<br><b>{len(data):,}</b></div><div class="card">Similarweb<br><b>{source.get("similarweb",0):,}</b></div><div class="card">Semrush<br><b>{source.get("semrush",0):,}</b></div><div class="card">高优先级<br><b>{priority.get("高",0):,}</b></div></div><p class="box">筛选条件：搜索量 ≥ 5,000；CPC ≥ 0.01；KD 分档上限 30 / 45 / 60；排除明显敏感、品牌和版权风险词。</p>'
doc += '<h2>二、执行结论</h2><p>当前机会主要集中在计算器和分析工具、游戏辅助和数据工具、媒体文件处理、字体模板素材及内容解释。最适合快速做 MVP 的是计算器、生成器、分析器和追踪器，因为用户目标明确，单页可以直接交付结果。高 CPC 方向优先考虑订阅或付费导出，高流量内容方向优先考虑广告。</p><ul><li>最值得优先验证：计算器和游戏数据工具。</li><li>最适合快速开发：单页计算器、生成器、转换器和追踪器。</li><li>最适合广告：内容解释、游戏资料、字体素材。</li><li>最高风险：品牌导航、版权下载、成人敏感和强品牌 SERP。</li></ul>'
doc += f'<h2>三、数据来源分析</h2><div class="grid"><section><h3>来源分布</h3>{bars(source)}<p>Similarweb 适合发现扩展词；Semrush 适合搜索量、KD、CPC 验证。两者口径不同，搜索量不可直接相加。</p></section><section><h3>推荐站点类型</h3>{bars(site)}<h3>优先级</h3>{bars(priority)}</section></div>'
doc += f'<h2>四、关键词机会结构</h2><div class="grid"><section><h3>搜索量区间</h3>{bars(volume)}<p>高搜索量且 KD 不超过 30 的词，通常更适合优先验证。</p><h3>KD 区间</h3>{bars(kd)}</section><section><h3>CPC 区间</h3>{bars(cpc)}<p>CPC 越高通常商业意图越明确，但竞争也可能更强。</p><h3>阅读方式</h3><p>这些分布用于判断主题结构，不替代单词 SERP、品牌和版权复核。</p></section></div>'
doc += '<h2>五、主题聚类分析</h2><table><tr><th>主题</th><th>关键词数</th><th>总搜索量</th><th>平均搜索量</th><th>平均KD</th><th>平均CPC</th><th>代表高流量词</th></tr>'+''.join(theme_rows)+'</table>'
doc += '<h2>六、每个主题的建站方案</h2><div class="box"><h3>计算器和分析工具</h3><p>用户输入数字、选项或对象，获得计算、比较或评分结果。MVP：输入表单、结果卡片、解释、复制分享、FAQ；后续增加历史记录、PDF 导出和会员报告。变现：广告、订阅、付费导出。SEO：按对象、场景和地区扩展页面。</p><h3>游戏辅助和数据工具</h3><p>用户查询角色、装备、交易或进度。MVP 先覆盖一个游戏和一个场景，再扩展数据库页面。变现：广告、会员、赞助。风险：数据稳定性和游戏政策。</p><h3>图片、音频、视频处理</h3><p>用户上传文件并转换、压缩、裁剪或下载。MVP：上传、处理、结果下载；批量处理和高级格式可做订阅。风险：版权和平台条款。</p><h3>字体、模板和素材</h3><p>用户筛选、预览和下载可用资源。MVP：分类、预览、授权说明、下载；变现：付费资源、联盟、广告。</p><h3>内容解释和资料查询</h3><p>用户想知道含义、背景、用法或完整列表。MVP：解释页、FAQ、专题集群；变现：广告、赞助、线索获客。</p></div>'
doc += '<h2>七、优先级建议</h2><div class="box"><b>优先验证：</b>搜索量较高、KD 较低、用户动作明确、单页可交付结果且有 CPC 或付费空间。<br><b>次优先验证：</b>模板、素材和内容专题，需要内容深度、授权或差异化。<br><b>暂缓：</b>品牌导航、版权下载、成人敏感、搜索意图不稳定、强品牌 SERP 或无明确变现方式。</div><h2>八、变现机会分析</h2><p>广告适合高流量内容和游戏资料；订阅适合分析、批量处理和高级报告；一次性付费适合报告与导出；联盟适合模板、字体和产品推荐；游戏内广告与赞助适合游戏工具；付费资源适合模板素材；线索获客适合 B2B 需求。</p><h2>九、风险与限制</h2><ul><li>Similarweb 与 Semrush 数据口径不同，不能简单相加。</li><li>KD 和 CPC 只是参考，必须人工查看 Google SERP。</li><li>CPC 不等于实际收入，AI 判断不能替代市场验证。</li><li>品牌、下载器、字体、图片和游戏数据可能有商标、版权或平台政策风险。</li><li>适合建站不代表一定获得流量或收入。</li></ul><h2>十、下一步执行计划</h2><ol><li>从高优先级主题中选择 5–10 个项目。</li><li>复核 SERP、弱站、域名、品牌与版权风险。</li><li>确定页面类型和 MVP 功能范围。</li><li>上线 1–2 个 MVP，接入分析、广告和转化追踪。</li><li>依据真实访问、留存、点击和收入决定是否扩展。</li></ol></main></body></html>'
(out/'keyword_site_analysis_final.html').write_text(doc)
print(len(data), len(doc))
