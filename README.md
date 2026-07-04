# AI 行业情报日报

自动生成的静态站点,内容来自 Miniflux + DeepSeek 摘要评分管道。

- 生成脚本: `generator/generate_site.py`
- 模板: `generator/template.py`
- 输出: `docs/`(GitHub Pages 从这里发布)

不要手动编辑 `docs/` 下的文件,会被自动生成覆盖。

## 前端输出结构

生产链路仍由 Python 生成静态 HTML,但页面结构已按 `chatweb` 的信息应用思路重做:

- 左侧: 视图导航和专题导航。
- 中间: 今日情报流、专题页、信息源页。
- 右侧: 公开条目数、最高评分、专题数、来源数和近期来源。

生成器会输出:

```text
docs/index.html
docs/topics/index.html
docs/topics/<topic>.html
docs/sources/index.html
```

公开页面只读取 `starred_for_daily`、`processed`、`published` 状态。`industry-crawler` 回流的 `candidate` 候选项必须先经过人工/规则确认,不会直接进入公开页面。

## 与 industry-crawler 的情报交换

本站可以通过文件/对象存储与独立部署的 `industry-crawler` 交换 JSON batch:

- 导出 RSS/Miniflux/人工筛选信号:
  ```bash
  python3 scripts/export_source_feedback.py \
    --db /opt/miniflux-rsshub/intel/intel.db \
    --out /tmp/intel_source_feedback.json \
    --batch-id rss-ai-api-$(date +%Y%m%d%H%M) \
    --topic ai-tools-api
  ```
- 导入 crawler 回流事实为候选项:
  ```bash
  python3 scripts/import_crawler_intel.py \
    --db /opt/miniflux-rsshub/intel/intel.db \
    --batch /tmp/crawler_to_intel.json
  ```

导入只写 `crawler_intel_candidates` 表,初始状态恒为 `candidate`;不会自动发布到 `docs/`,不会进入邮件或公开页面。对象存储同步由外层 cron/rclone/wrangler 处理,脚本本身不保存任何云端密钥。
