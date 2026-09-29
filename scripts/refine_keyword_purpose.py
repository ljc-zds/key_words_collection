from openpyxl import load_workbook
from pathlib import Path
import re
p=Path(__file__).resolve().parents[1]/'outputs/keyword_site_analysis_20260911/keyword_site_candidates.xlsx'
w=load_workbook(p); s=w.active
for r in range(2,s.max_row+1):
 k=str(s.cell(r,2).value or '').strip(); q=k.lower()
 if 'one piece filler list' in q: d='用户想查询《海贼王》动画中的原创 filler 集数，判断哪些集数可以跳过。页面应按集数列出 filler 类型、标题、是否建议跳过，并提供主线/原创筛选和观看进度标记；适合动漫观看指南站，主要通过广告和专题流量变现，需注意影视版权。'
 elif 'calculator' in q: d=f'用户想在线计算或比较“{k.replace(" calculator","")}”，通常会输入数字、对象或选项，立即得到结果、差值或公平度评分。页面应提供参数表单、结果解释、复制/分享和 FAQ；适合单页计算器，变现可用广告、订阅和付费导出。'
 elif 'generator' in q: d=f'用户想生成“{k.replace(" generator","")}”相关内容。页面应提供选项、数量和风格设置，一键生成可复制、下载或分享的结果；适合生成器工具站，变现可用广告、会员高级模板和联盟。'
 elif 'analyzer' in q: d=f'用户想分析“{k.replace(" analyzer","")}”，需要输入对象或数据，获得指标、评分、比较结果和行动建议。页面应保留计算过程和结果解释；适合分析工具，变现可用订阅、付费报告和广告。'
 elif 'tracker' in q: d=f'用户想追踪“{k.replace(" tracker","")}”的实时状态、进度或历史记录。页面应提供搜索、时间线、状态筛选和数据更新时间；适合数据查询站，变现可用广告、会员和赞助。'
 elif 'converter' in q or 'convert' in q: d=f'用户想把文件或内容转换为“{k}”要求的格式。页面应支持上传、格式设置、转换进度和结果下载，最好提供批量处理；适合文件处理工具，变现可用广告和订阅，但需核查版权与平台条款。'
 elif 'download' in q: d=f'用户想从指定平台下载“{k.replace(" download","")}”相关的媒体或文件。页面应说明支持的链接、处理步骤和下载结果；变现可用广告，但必须优先核查版权、平台政策和商标风险。'
 elif any(x in q for x in ['font','template','wallpaper','icon','logo','png']): d=f'用户正在寻找“{k}”对应的字体、模板、图片或可直接使用的素材。页面应提供分类、预览、尺寸/格式、授权说明和下载入口；适合素材目录站，变现可用付费资源、联盟和广告。'
 elif any(x in q for x in ['meaning','what is','wiki','list','guide']): d=f'用户想了解“{k}”的含义、背景、用法或完整资料列表。页面应提供直接答案、结构化列表、FAQ 和相关长尾入口；适合内容专题站，主要通过广告、赞助和联盟变现。'
 else: d=f'用户正在搜索“{k}”相关的具体解决方案、信息或可用资源。建站前应先确认搜索意图、可交付页面结果和变现路径，再决定做工具页、资料页或内容专题。'
 s.cell(r,3).value=d
w.save(p)
print('updated',s.max_row-1)
