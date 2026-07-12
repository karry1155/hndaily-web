#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scripts.radar_scoring import WEIGHTS
from scripts.radar_select import (
    FINAL_SCORE_THRESHOLD, FOCUS_DAY_PENALTY, FOCUS_DAYS,
    HAINAN_RELEVANCE_THRESHOLD,
)

LABELS = {
    "hainan_relevance": "海南相关性", "actionability": "可行动性",
    "impact_scope": "影响范围", "timeliness": "时效性",
    "information_density": "信息密度",
}


def build_scoring_audit(content_root: Path) -> str:
    items = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((content_root / "items").glob("*/*.json"))]
    scores = Counter(item["final_score"] for item in items)
    vectors = Counter(tuple(item["semantic_scores"][key] for key in WEIGHTS) for item in items)
    by_date = defaultdict(Counter)
    for item in items: by_date[item["published_date"]][item["final_score"]] += 1
    score_rows = "".join(
        f"<tr><td>{score:g} 分</td><td>{count} 条</td><td>{count/len(items)*100:.1f}%</td></tr>"
        for score, count in sorted(scores.items(), reverse=True)
    )
    date_rows = "".join(
        f"<tr><td>{date}</td><td>{sum(values.values())}</td><td>{html.escape(', '.join(f'{score:g}分 × {count}' for score,count in sorted(values.items(), reverse=True)))}</td></tr>"
        for date, values in sorted(by_date.items(), reverse=True)
    )
    vector_rows = "".join(
        f"<tr><td>{' / '.join(map(str, vector))}</td><td>{count}</td><td>{sum(float(WEIGHTS[key])*value*10 for key,value in zip(WEIGHTS,vector)):.1f}</td></tr>"
        for vector, count in vectors.most_common()
    )
    weights = "".join(f"<li><b>{LABELS[key]} {float(value)*100:g}%</b><span>{key}</span></li>" for key,value in WEIGHTS.items())
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HN·HOT 当前评分机制审计</title>
<style>:root{{--bg:#0b1016;--panel:#121a24;--line:#27313d;--text:#edf3fa;--muted:#91a0b4;--accent:#39a9bd}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:15px/1.65 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1050px;margin:auto;padding:40px 22px 80px}}h1{{font-size:32px;margin:0}}h2{{margin-top:38px;font-size:21px}}.lead,.muted{{color:var(--muted)}}.notice{{margin:20px 0;padding:14px 16px;border-left:3px solid var(--accent);background:var(--panel)}}.flow{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}}.flow div,.card{{border:1px solid var(--line);border-radius:10px;background:var(--panel);padding:15px}}.flow b{{display:block;color:var(--accent)}}ul.weights{{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;padding:0;list-style:none}}.weights li{{padding:12px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}}.weights span{{display:block;color:var(--muted);font-size:11px}}table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line)}}th,td{{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left}}th{{color:var(--muted)}}code{{color:#72d2df}}@media(max-width:720px){{main{{padding:24px 16px 60px}}.flow,ul.weights{{grid-template-columns:1fr}}table{{font-size:13px}}}}</style></head><body><main>
<h1>当前评分机制审计</h1><p class="lead">基于现有源码和 {len(items)} 条已入选新闻生成。生成时未重新评分。</p><div class="notice"><b>结论：</b>当前分数没有计算故障，但模型输出高度模板化：全部条目只有两种五维向量，因此最终分也只有 80 和 78.5 两档。<b>本报告未修改评分机制。</b></div>
<h2>一条新闻怎样得到最终分</h2><div class="flow"><div><b>1 原文</b>脚本采集标题与正文</div><div><b>2 模型判断</b>输出五个 0–10 整数及理由</div><div><b>3 脚本计算</b><code>score_semantic()</code> 加权并四舍五入到 0.1</div><div><b>4 脚本筛选</b>相关性 ≥ {HAINAN_RELEVANCE_THRESHOLD} 且最终分 ≥ {FINAL_SCORE_THRESHOLD}</div><div><b>5 首页焦点</b>最近 {FOCUS_DAYS} 个内容日，旧一日减 {FOCUS_DAY_PENALTY} 分</div></div>
<h2>当前公式</h2><p><code>final_score = 10 × Σ(模型维度分 × 权重)</code>。当前没有加减分调整项，<code>base_score == final_score</code>。</p><ul class="weights">{weights}</ul><p class="muted">实现：<code>scripts/radar_scoring.py / score_semantic</code>。同分排序依次比较信息密度和 item_id；实现：<code>scripts/radar_select.py / _rank_key</code>。</p>
<h2>真实最终分分布</h2><table><thead><tr><th>分值</th><th>数量</th><th>占比</th></tr></thead><tbody>{score_rows}</tbody></table>
<h2>为什么大家看起来都是 80</h2><div class="card"><p>80 分：{scores.get(80,0)} 条，占 {scores.get(80,0)/len(items)*100:.1f}%。78.5 分：{scores.get(78.5,0)} 条。模型在现有数据里只生成了 {len(vectors)} 种五维组合，而脚本只是忠实执行固定加权，所以无法主动拉开差距。</p><p>直接原因不是前端显示，也不是舍入丢失：44 条的五维分全部为 <code>8/8/8/8/8</code>；37 条全部为 <code>9/7/7/8/8</code>。这说明主要瓶颈在模型评分提示、标尺锚点和批次回填的一致化，而非当前公式代码。</p></div>
<h2>模型向量与计算结果</h2><table><thead><tr><th>相关/行动/影响/时效/密度</th><th>条数</th><th>脚本结果</th></tr></thead><tbody>{vector_rows}</tbody></table>
<h2>按日期检查</h2><table><thead><tr><th>日期</th><th>条数</th><th>分布</th></tr></thead><tbody>{date_rows}</tbody></table>
<h2>下一步重建前需要决定</h2><ol><li>模型是做绝对评分，还是在同一天候选之间做相对排序？</li><li>每个整数档应提供哪些正反例锚点，避免默认集中在 7–9 分？</li><li>是否增加稀缺性、公共影响强度或事件进展等更能拉开差距的维度？</li><li>是否允许脚本基于来源、事件重复度或地域覆盖做透明调整？</li><li>页面展示原始绝对分，还是展示日内百分位或等级？</li></ol>
</main></body></html>'''


def main(argv):
    if len(argv) != 3:
        print("Usage: build_scoring_audit.py CONTENT_ROOT OUTPUT_HTML", file=sys.stderr); return 1
    output = Path(argv[2]); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_scoring_audit(Path(argv[1])), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
