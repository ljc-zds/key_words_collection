from pathlib import Path
p=Path(__file__).resolve().parents[1]/'outputs/keyword_site_analysis_20260911/keyword_site_analysis.html'
s=p.read_text()
block='''<h2>主题级建站决策</h2><table><tr><th>方向</th><th>用户任务</th><th>MVP</th><th>变现</th><th>复杂度</th></tr><tr><td>计算器和分析工具</td><td>输入参数并得到计算、比较或评分结果</td><td>表单、结果卡片、解释、复制分享、FAQ</td><td>广告、订阅、付费导出</td><td>低</td></tr><tr><td>游戏辅助和数据工具</td><td>查询角色、装备、交易或进度数据</td><td>一个游戏、一个场景、数据库查询</td><td>广告、会员、赞助</td><td>中</td></tr><tr><td>媒体文件处理</td><td>转换、压缩、裁剪或下载文件</td><td>上传、处理、结果下载</td><td>广告、订阅</td><td>中</td></tr><tr><td>字体模板素材</td><td>预览、筛选和下载可用资源</td><td>分类、预览、授权说明、下载</td><td>付费资源、联盟、广告</td><td>低</td></tr><tr><td>内容解释资料</td><td>了解含义、背景、用法或完整列表</td><td>解释页、FAQ、专题集群</td><td>广告、赞助、线索</td><td>低</td></tr></table><h2>建站优先级判断</h2><p><b>优先验证：</b>需求动作明确、单页可交付结果、搜索量较高、KD 较低且有 CPC 的工具或游戏方向。<br><b>次优先：</b>模板、素材和内容专题，需要持续内容和差异化。<br><b>暂缓：</b>品牌导航、成人敏感、版权下载、SERP 被强品牌占据或缺乏变现路径的方向。</p><h2>变现与验证计划</h2><p>先从高优先级方向选 5–10 个，逐一复核 Google SERP、域名和版权风险；制作 1–2 个 MVP，接入分析和转化追踪，依据真实访问、留存、点击和收入决定扩展。</p>'''
if '主题级建站决策' not in s:s=s.replace('</main>',block+'</main>')
p.write_text(s)
print(p.stat().st_size)
