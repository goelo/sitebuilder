# Sitebuilder — 游戏站建站 SOP

一套完整的 8 步建站方法论，适用于 Roblox / IO / Web Meme Game 等游戏站。

## 流程总览

| Step | 阶段 | 输入 | 产出 | 预估耗时 |
|------|------|------|------|----------|
| 1 | 素材采集与游戏研究 | 游戏名 | `step1-research.json` | 15-25 min |
| 2 | 关键词发现与搜索量验证 | Step 1 报告 | `step2-keywords.json` | 25-35 min |
| 3 | 竞品分析与内容验证 | Step 2 关键词 | `step3-competitive.json` | 18-27 min |
| 4 | 内容规划与页面结构设计 | Step 2 + 3 | `step4-planning.json` | 16-24 min |
| 5 | 素材采集与数据生产 | Step 4 清单 | `step5-manifest.json` | 28-47 min |
| 6 | 站点构建（代码实现） | Step 4 + 5 | 可构建的站点 | 43-77 min |
| 7 | 质量验证 | Step 6 代码 | 审计报告 | 30-50 min |
| 8 | 部署上线 | Step 7 通过 | 线上站点 | 30-60 min |

## 目录结构

```
sitebuilder/
├── README.md
├── step1-research/          # Step 1: 素材采集与游戏研究
│   ├── SKILL.md             # 调度文件（总览）
│   ├── step1a-identity-sources.md   # 1a: 游戏身份确认 + 官方源锁定
│   ├── step1b-media-collection.md   # 1b: 截图/视频素材采集
│   └── step1c-mechanics-report.md   # 1c: 机制摸底 + 合并报告
├── step2-keywords/          # Step 2: 关键词发现
│   ├── SKILL.md
│   ├── step2a-seeds-serp.md         # 2a: 词根 + 词找站
│   ├── step2b-competitor-mining.md  # 2b: 站找词 + Google Trends
│   └── step2c-evaluate-finalize.md  # 2c: 评估入库 + 最终清单
├── step3-competitive/       # Step 3: 竞品分析
│   ├── SKILL.md
│   ├── step3a-serp-gaps.md          # 3a: SERP 深度分析
│   └── step3b-verdict.md            # 3b: 域名检查 + 最终判决
├── step4-planning/          # Step 4: 内容规划
│   ├── SKILL.md
│   ├── step4a-structure.md          # 4a: 页面结构设计
│   └── step4b-assets-plan.md        # 4b: 素材采购清单
├── step5-content/           # Step 5: 素材采集
│   ├── SKILL.md
│   ├── step5a-data.md               # 5a: 结构化数据采集
│   ├── step5b-media-videos.md       # 5b: 视觉素材 + YouTube 视频
│   └── step5c-references-manifest.md # 5c: 权威引用 + 汇总 Manifest
├── step6-build/             # Step 6: 站点构建
│   ├── SKILL.md
│   ├── step6a-init-homepage.md      # 6a: 项目初始化 + 首页
│   ├── step6b-core-pages.md         # 6b: 核心页面（Hub + 工具页）
│   ├── step6c-remaining-pages.md    # 6c: 剩余页面
│   └── step6d-seo-verify.md         # 6d: SEO 基础设施 + Build 验证
├── step7-qa/                # Step 7: 质量验证
│   ├── SKILL.md
│   ├── step7a-humanizer-seo.md      # 7a: 去 AI 味 + On-Page SEO
│   └── step7b-pillar-screenshots.md # 7b: 支柱模型 + 截图验收
└── step8-deploy/            # Step 8: 部署上线
    ├── SKILL.md
    ├── step8a-deploy-domain.md      # 8a: CF Pages 部署 + 域名
    └── step8b-gsc-verify.md         # 8b: GSC 提交 + 线上验收
```

## 核心策略

### 工具型页面优先

不做红海 codes / tier list（大站碾压），优先做交互工具页：

- **计算器**（伤害/收益/配装）— 有公式 + 玩家需要优化
- **数据库/图鉴**（大量可枚举实体）— 实体数 >20 + 多维属性
- **交互地图**（空间关系 + 位置标注需求）
- **价值追踪器**（价格波动 + 社区交易需求）

大站只能写静态长文，我们做工具 = 降维打击。

### 技术栈

- **框架**：Next.js
- **样式**：Tailwind CSS
- **组件**：shadcn/ui
- **部署**：Cloudflare Pages

### 关键词飞轮方法论

```
词根 → 词找站（SERP + YouTube + Suggest）
      → 站找词（竞品词库 + Google Trends Related Queries）
      → 评估入库（热度 + 竞争度 + KDROI）
      → A/B/C 分级
```

## 使用方式

每一步读取对应目录下的 `SKILL.md` 作为入口，按子阶段顺序执行。

每个子阶段都有：
- **输入**：依赖哪些前置产出
- **执行步骤**：具体怎么做
- **输出**：落盘到哪里、JSON schema
- **汇报模板**：完成后的汇报格式
- **耗时预期**：合理时间范围

## 关键门禁

- **Step 3 完成**：必须等 go/caution/abort 判决
- **Step 6d**：`npm run build` 零错误才能进 Step 7
- **Step 7**：四项全过才能进 Step 8
  - humanizer P0 清零
  - On-Page SEO 平均 ≥85
  - 支柱模型无蚕食无孤儿页
  - 截图验收通过

## 注意事项

- 每个步骤中的模型别名（如 `ikgpt54`、`ho`、`hg`）是 OpenClaw 内部配置，使用时需要替换为实际可用的模型
- `agent-reach` 和 `bb-browser` 是外部 CLI 工具，需要单独安装配置
- 文件中的 `~/workspace/` 路径需根据实际工作区位置调整
