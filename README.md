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

公开页面只读取 `publish_ready`、`processed`、`published` 状态。Miniflux/NetNewsWire star 只会进入 `starred_pending_ai`，必须经过 AI 双语加工和结构校验后才会变成 `publish_ready`。`industry-crawler` 回流的 `candidate` 候选项必须先经过人工/规则确认,不会直接进入公开页面。

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

## 当前定位

这个仓库的 `docs/index.html` 属于历史兼容发布链路，只展示生成时选中的条目。
新的正式信息站以 `dia-for/chatweb` 为发布端，RSS 情报进入该站的 **远山** 栏目。

累计式导出脚本：

```bash
python3 generator/export_yuan_shan_markdown.py \
  --db /opt/miniflux-rsshub/intel/intel.db \
  --out-dir /path/to/chatweb/content/yuan-shan
```

正式 cron 不应直接调用裸导出器，而应调用带校验的桥接脚本：

```bash
python3 scripts/publish_to_chatweb.py \
  --db /opt/miniflux-rsshub/intel/intel.db \
  --chatweb-repo /path/to/chatweb \
  --sync-miniflux \
  --enrich-pending \
  --obsidian-raw-dir /opt/miniflux-rsshub/intel/obsidian/raw/rss \
  --min-publishable 1 \
  --build \
  --deploy \
  --qa-live
```

该脚本会按顺序执行：

```text
Miniflux starred entries
  -> intelligence_items(status = starred_pending_ai)
  -> AI enrichment(status = publish_ready)
  -> intelligence_items(status in publish_ready / processed / published)
  -> chatweb/content/yuan-shan/*.md
  -> obsidian/raw/rss/**/*.md
  -> chatweb npm run content:manifest
  -> 校验每条可发布 DB 行都进入远山 Markdown 和 manifest
  -> 可选 build/deploy/qa:live
```

`--sync-miniflux` 会先调用 Miniflux API 拉取 `starred=true` 的条目。同步脚本会把
starred 条目写成 `starred_pending_ai`，避免 RSS 原文绕过 AI 加工直接发布。

如果可发布行数低于 `--min-publishable`，或者有 DB 行没有进入 `content-manifest.json`，脚本会非零退出，cron 日志会直接暴露链路断点。

导出规则：

- 只导出 `status in ('publish_ready', 'processed', 'published')` 的情报。
- 每条情报生成一个稳定 Markdown 文件，不清空、不覆盖整个站点页面。
- Markdown frontmatter 写入 `section: yuan-shan`、`language: bilingual`、中英双语标题/摘要/tags，由 `chatweb` 统一生成列表页、分类页和详情页。
- 远山分类规范为 `AI`、`数据`、`新能源`、`传统AI+`、`教育AI+`。

本地验证：

```bash
python3 -m unittest discover -s tests -v
```
