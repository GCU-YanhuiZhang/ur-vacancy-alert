# PRD — UR 空房通知 (UR Vacancy Alert) · MVP

Status: ready-for-human

<!-- ready-for-human(非纯 AFK):需你提供 Gmail App Password,且 watchlist 那步含人工查站。大部分编码可交给 agent。 -->


## 一句话

一个**自用**的定时脚本:自动抓取神奈川 UR 賃貸住宅空房,按一组固定条件匹配,出现**新**空房时邮件通知本人。术语见根目录 `CONTEXT.md`。

## 范围

**做:** 爬取 → 按固定条件筛 → 与上轮快照对比找出新空房 → 发邮件。
**不做(非目标):** 网站前端、用户账号、多租户、运行时可调的筛选 UI。理由见 `docs/adr/0002-self-use-script-not-website.md`。

## 命中条件(全部固定,写进配置)

一个空房**部屋**满足以下**全部**条件才发邮件:

1. 所属**団地**在**通勤候选団地(watchlist)**内 —— 即到勝どき**门到门 ≤ 55 分**的神奈川団地。注:原定 ≤40 分,但实测勝どき仅都営大江戸線一线、神奈川方向普遍偏远,≤40 分仅剩 1 个団地(小杉御殿),遂放宽到 ≤55(2026-06-22,见 `docs/adr/0003-commute-threshold-55min.md` 与 `data/commute_to_katsudoki.md`)。
2. **家賃 + 共益費** 合计 ≤ **80,000 円**。
3. **間取り** 为 **1K 以上**(排除 1R / 单间;1K、1DK、1LDK、2K、2DK… 均要)。
4. **面积** ≥ **20 ㎡**。
5. 其余(築年数 / 楼层 / 朝向等)不限制。

通勤精度为団地级(同団地下所有部屋共享同一通勤时间),理由见 `docs/adr/0001-commute-granularity-danchi-level.md`。

## 数据流

```
[GitHub Actions cron 每 15–20 分钟]
   → 遍历 watchlist 内的団地,调 UR JSON API 取各団地当前空房部屋
   → 按家賃/間取り/面积过滤  → 得到本轮"命中部屋 ID 集合" A
   → 读 state/seen.json 得上轮集合 B
   → 新空房 = A − B
   → 若 A−B 非空:发邮件(列出新命中部屋)
   → 用 A 覆盖 state/seen.json 并 commit 回仓库
```

## 组件

### 1. Watchlist 生成(一次性 / 偶尔重算,半手动)— 输入已备好(2026-06-19)

- 神奈川 UR 団地全量 = **166 个**(已抓取,见 `data/kanagawa_danchi.json`,含団地名/地址/traffic/最寄り駅)。当前有空房的只 79 个,但 watchlist 要覆盖全部 166(现在没空房将来也可能有)。
- **不要对 166 个站全查**(去重纯站名约 155 个,且大量在秦野/平塚/藤沢等铁定超 40 分)。改为**先地理预筛**:川崎市东部 + 横浜东北部(川崎/幸/中原/高津区、鶴見/神奈川/港北/都筑区)→ 候选 **43 団地 / 46 个去重站**(见 `data/candidates.txt`)。
- 对这 ~46 个候选站,人工查"该站 → 勝どき"换乘时间(免费乗換工具,零信用卡);団地通勤 ≈ 徒歩到站(UR `traffic` 自带分钟) + 站到勝どき。
- 保留 ≤ 40 分者 → `watchlist.json`(団地三元组 `shisya/danchi/shikibetu` 列表)。电车时刻表少变,偶尔重算即可。
- 注:地理网可调宽窄;明显近的(川崎/武蔵小杉/鶴見/日吉/横浜/元住吉)优先,都筑区(港北 NT)多为 borderline ~40–50 分。

### 2. Crawler(Python)— ✅ 已实测确认(2026-06-19,纯 curl/urllib 跑通,无需浏览器)

- **API 主机:`https://chintai.r6.ur-net.go.jp`**(旧资料里的 `chintai.sumai` 已废弃)。
- 全部 `POST`,`Content-Type: application/x-www-form-urlencoded`;**必须带请求头** `Referer: https://www.ur-net.go.jp/`、`Origin: https://www.ur-net.go.jp`、普通 `User-Agent`。
- 三个接口:
  1. `/chintai/api/bukken/search/result_main/` → 概要,`count` = 当前**有空房**的団地数。
  2. `/chintai/api/bukken/result/bukken_result/` → **団地列表**(分页)。每项含 `shisya`/`danchi`/`shikibetu`(団地三元组)、`danchiNm`、`place`(地址)、`traffic`(交通 HTML,最寄り駅在 `「…」駅` 内)。
  3. `/chintai/api/bukken/result/bukken_result_room/` → 某団地**空房部屋**数组(传 `shisya`/`danchi`/`shikibetu`)。
- 关键参数:`block=kanto`、`tdfk=14`(=神奈川)、`pageSize`、`pageIndex`;可选服务端过滤 `rent_low`/`rent_high`/`floorspace_low`/`floorspace_high`/`walk`。
- 部屋级字段(room 接口):`id`(JKSS 唯一房号,如 `000121407`)、`roomNmMain`(**棟**,如 "1-21号棟")、`roomNmSub`(房号)、`rent_normal`(家賃 "43,000円")、`commonfee`(共益費 "2,900円")、`type`(間取り "2DK")、`floorspace`(面积,**HTML 实体 `&#13217;`=㎡**,需 `html.unescape`)、`floor`(楼层 "4階")。
- **dedup 主键 = `id`(JKSS)**,全局唯一,即快照差集的 key。
- ⚠️ 解析容错:家賃/共益費是 "43,000円" 这类(逗号千分位+円);面积是 HTML 实体;`traffic` 是 HTML,站名取 `「…」駅`,注意同站会带不同线路前缀(去重看括号内站名)。

### 3. Filter

- 在 watchlist 内 + 家賃含共益費 ≤ 8万 + 間取り≥1K + 面积≥20㎡。

### 4. Diff & State

- 状态文件 `state/seen.json` = 上一轮的命中部屋 ID 集合。
- 每轮:`新 = 本轮 − seen`;跑完用本轮覆盖 `seen` 并 `git commit` 回仓库。
- 语义:部屋持续空着 → 不重复发;被租走后再放出 → 重新发(自用场景需要)。

### 5. Notify

- Gmail SMTP + App Password(需先开两步验证);凭据存 **GitHub Actions Secrets**,绝不入库。
- 收件:本人外部邮箱(只放 Actions Secrets `MAIL_TO`,**不入库**);**同时抄送发信 Gmail 自己**作兜底。
- 邮件正文列出每个新命中部屋:団地名、棟/房号、家賃(含共益費)、間取り、面积、楼层、UR 详情页链接。

## 运行环境

- GitHub Actions 定时工作流;**公开仓**(免费无限分钟,无机密入库);每 15–20 分钟一次。
- Actions 定时可能晚几分钟 —— 可接受(UR 空房非秒抢)。

## 已知风险

| 风险 | 对策 |
|---|---|
| Gmail → 外部邮箱被拦/进垃圾箱,静默漏报 | 收件箱白名单 + 抄送 Gmail 兜底;实测不行则换 Resend |
| UR 为非官方 API,可能改结构/字段 | 解析做容错;失败时邮件告警(脚本报错也通知自己) |
| watchlist 静态,换乘时间变化不自动反映 | 偶尔手动重算;阈值附近团地留意 |
| 大団地团内步行差异未体现在通勤数值 | 已知取舍,见 ADR-0001 |

## 需你提供(建表时)

- 发信 Gmail 地址 + 为其生成的 **App Password**(填入 Actions Secrets,**勿贴聊天**)。
- (可选)勝どき 的精确站点口径——默认都営大江戸線「勝どき駅」。

## 实施计划(建议拆成的 issue)

1. ~~`01` 摸清 UR API~~ ✅ **完成(2026-06-19)**:接口/参数/字段/dedup 主键全部实测确认,纯 curl 跑通;見上「Crawler」节。
2. ~~`02` 半手动生成 watchlist~~ ✅ **完成(2026-06-22)**:46 站到勝どき换乘时间用乗換案内查实(`data/commute_to_katsudoki.md`),门到门 ≤55 分筛出 **18 団地** → `watchlist.json`(每項带 `commute_min`)。阈值由 ≤40 放宽到 ≤55(理由见命中条件 #1)。
3. ~~`03` Crawler + Filter~~ ✅ **完成(2026-06-19)**:`ur_alert/` 包,实跑通过(14/14 单测 + 43 団地实抓)。
4. ~~`04` Diff + State~~ ✅ **完成(2026-06-19)**:`state/seen.json` 快照差集,实测"新→0新"去重正确。
5. ~~`05` Notify~~ ✅ **完成(2026-06-19)**:Gmail SMTP 发信,163 收信 + Gmail 抄送,邮件模板;未配凭据退化为打印。
6. ~~`06` GitHub Actions 工作流~~ ✅ **完成(2026-06-22)**:`.github/workflows/check.yml`,每 20 分 cron + `workflow_dispatch`,`contents: write` 权限 commit `state/seen.json` 回仓库,Secrets 注入凭据。
7. ~~`07` 错误告警~~ ✅ **完成(2026-06-22)**:`notify.notify_error()` 异常邮件(含 traceback)给本人,`main` 捕获后再非零退出让 CI 显式失败。
