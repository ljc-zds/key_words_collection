import json, html
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'outputs/keyword_site_analysis_20260911'
data = json.loads((out / 'site_keywords.json').read_text())

def table(counter):
    total = len(data)
    return ''.join(f'<tr><td>{html.escape(str(k))}</td><td>{v:,}</td><td>{v/total*100:.1f}%</td></tr>' for k,v in counter.most_common())

source = Counter(x.get('provider','未知') for x in data)
site = Counter(x.get('site_type','未知') for x in data)
priority = Counter(x.get('priority','未知') for x in data)

page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>关键词建站机会分析报告</title><style>body{font:15px Arial;color:#172033;background:#f4f7fb;margin:0}main{max-width:1180px;margin:24px auto;background:#fff;padding:36px}h1{margin-top:0}h2{border-left:5px solid #2463a6;padding-left:12px;margin-top:36px}.cards{display:flex;flex-wrap:wrap;gap:14px}.card{background:#eef5ff;border-radius:8px;padding:18px 24px;min-width:150px}.card b{font-size:26px}table{border-collapse:collapse;width:100%;margin:12px 0 24px}th{background:#173b63;color:#fff}td,th{padding:10px;border-bottom:1px solid #dfe5ec;text-align:left}.grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}.box{background:#f8fafc;padding:16px;border-radius:8px}li{margin:8px 0}@media(max-width:800px){.grid{grid-template-columns:1fr}}</style></head><body><main>'''
page += f'<h1>关键词建站机会分析报告</h1><p>分析日期：2026-09-11　数据来源：Similarweb、Semrush　覆盖市场：Global / US</p><div class="cards"><div class="card">原始候选<br><b>15,936</b></div><div class="card">最终保留<br><b>{len(data):,}</b></div><div class="card">Similarweb<br><b>{source.get("similarweb",0):,}</b></div><div class="card">Semrush<br><b>{source.get("semrush",0):,}</b></div><div class="card">高优先级<br><b>{priority.get("高",0):,}</b></div></div><p class="box">过滤条件：搜索量 ≥ 5,000；CPC ≥ 0.01；KD 分档上限 30 / 45 / 60；去除明显敏感、品牌和版权风险词。</p>'
page += '<h2>一、执行结论</h2><p>本次机会主要集中在计算器、游戏辅助、媒体处理、字体模板和资料查询。计算器与游戏数据工具最适合快速制作 MVP，因为用户目标明确，单页即可交付计算或查询结果。高 CPC 方向优先考虑订阅和付费功能，高流量内容方向优先考虑广告。</p><ul><li>最值得优先验证：计算器和游戏数据工具。</li><li>最适合快速开发：生成器、计算器、转换器和追踪器。</li><li>最适合广告变现：内容解释、游戏资料、字体素材。</li><li>风险最高：品牌导航、版权下载、成人敏感和强品牌 SERP。</li></ul>'
page += '<h2>二、数据来源分析</h2><div class="grid"><div><h3>来源分布</h3><table><tr><th>来源</th><th>数量</th><th>占比</th></tr>'+table(source)+'</table></div><div><h3>站点类型</h3><table><tr><th>类型</th><th>数量</th><th>占比</th></tr>'+table(site)+'</table></div></div><p>Similarweb 更适合发现扩展词，Semrush 更适合验证搜索量、KD 和 CPC；两者数据口径不同，不能直接相加。</p>'
page += '<h2>三、关键词机会结构</h2><div class="grid"><div><h3>优先级分布</h3><table><tr><th>级别</th><th>数量</th><th>占比</th></tr>'+table(priority)+'</table><h3>搜索量区间</h3><p>5,000–9,999、10,000–29,999、30,000–99,999、100,000 以上。高搜索量且 KD 不超过 30 的词优先验证。</p></div><div><h3>KD 区间</h3><p>0–30、31–45、46–60。KD 越低通常越适合新站切入，但仍需查看 SERP。</p><h3>CPC 区间</h3><p>0.01–0.49、0.50–0.99、1.00–2.99、3.00 以上。CPC 越高通常商业价值越明确。</p></div></div>'
page += '<h2>四、主题聚类与建站方案</h2><table><tr><th>主题</th><th>用户任务</th><th>MVP</th><th>变现</th><th>复杂度</th></tr><tr><td>计算器和分析工具</td><td>输入参数得到计算、比较或评分</td><td>表单、结果、解释、分享、FAQ</td><td>广告、订阅、付费导出</td><td>低</td></tr><tr><td>游戏辅助和数据工具</td><td>查询角色、装备、交易、进度</td><td>单游戏单场景数据库查询</td><td>广告、会员、赞助</td><td>中</td></tr><tr><td>图片音频视频处理</td><td>转换、压缩、裁剪或下载文件</td><td>上传、处理、结果下载</td><td>广告、订阅</td><td>中</td></tr><tr><td>字体模板和素材</td><td>预览、筛选、下载资源</td><td>分类、预览、授权、下载</td><td>付费资源、联盟、广告</td><td>低</td></tr><tr><td>内容解释和资料查询</td><td>了解含义、背景、用法、列表</td><td>解释页、FAQ、专题集群</td><td>广告、赞助、线索</td><td>低</td></tr></table>'
page += '<h2>五、优先级建议</h2><div class="box"><b>优先验证：</b>搜索量高、KD 低、需求动作明确、单页可承接且有变现路径。<br><b>次优先验证：</b>模板、素材和内容专题，需要持续内容或差异化。<br><b>暂缓：</b>品牌导航、版权下载、敏感词、SERP 被强品牌占据或无明确变现方式。</div><h2>六、变现机会分析</h2><p>工具适合广告、订阅、一次性付费和联盟；游戏适合游戏内广告、会员和赞助；素材适合付费资源和联盟；内容适合广告、赞助和线索获客；B2B 需求适合订阅和线索获客。</p><h2>七、风险与限制</h2><ul><li>Similarweb 与 Semrush 的搜索量和 KD 定义不同。</li><li>搜索量不能跨平台简单相加，CPC 也不等于实际收入。</li><li>必须人工复核 Google SERP、品牌、版权、地区和转化。</li><li>下载器、字体、图片素材和游戏数据可能受版权或平台政策限制。</li><li>AI 判断只是辅助，适合建站不等于保证流量或收入。</li></ul><h2>八、下一步执行计划</h2><ol><li>从高优先级方向选 5–10 个项目。</li><li>查看 SERP、弱站、域名和品牌风险。</li><li>确定页面类型并制作 MVP。</li><li>部署分析、广告和转化追踪。</li><li>根据真实访问、留存和收入决定是否扩展。</li></ol></main></body></html>'
(out/'keyword_site_analysis_v2.html').write_text(page); print(len(page))
