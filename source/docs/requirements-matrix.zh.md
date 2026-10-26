# 需求拆解矩阵

由 `docs/requirements.json` 经 `python -m c2m_craft requirements render` 生成。

- 条目 54 · 已覆盖 39 · 部分 1 · 计划 9 · 排除 5
- M1 条目已落地：21/21

| 编号 | 模块 | 里程碑 | 状态 | 需求 | 契约 | 产物 | 验证组 | 验收 | 报价 |
|---|---|---|---|---|---|---|---|---|---|
| A1.1 | A | M1 | 已覆盖 | 文本/参考图生成形态与纹样概念候选 | design_concept | c2m_craft/creative/workstation.py, static/app.js, config/creative/lexicon.json | C | J1 |  |
| A1.2 | A | M3 | 已覆盖 | 风格迁移 | design_concept | c2m_craft/creative/workstation.py, config/creative/styles.json, static/app.js, verify/records/model_calls.md | C | J1 |  |
| A1.3 | A | M1 | 已覆盖 | 色板与系列扩展 | design_concept | c2m_craft/creative/series.py, config/creative/series.json, config/creative/palettes.json | C | J1 |  |
| A1.4 | A | M1 | 已覆盖 | 纹样与材质效果预览 | design_concept | static/app.js, c2m_craft/creative/workstation.py | C | J1 |  |
| A2.1 | A | M1 | 已覆盖 | 授权来源与使用范围强制字段（正负样例） | pattern_asset | c2m_craft/library/assets.py, contracts/pattern-asset.schema.json, samples/library/rejected.json | B | J2 |  |
| A2.2 | A | M2 | 部分 | 资源库多模态检索 | pattern_asset | c2m_craft/library/assets.py, out/library_snapshot.json, static/app.js | B | J2 |  |
| A3.1 | A | M1 | 已覆盖 | 设计师原创预售交易 | c2m_order | c2m_craft/commerce/orders.py, samples/contracts/positive/order-ORD-0001.json | D | J4 |  |
| A3.2 | A | M2 | 已覆盖 | 消费者参与式定制 | c2m_order, customization_choice | contracts/customization-choice.schema.json, config/commerce/customization.json, c2m_craft/commerce/customization.py, out/customization_report.json | I | J4 |  |
| A3.3 | A | M2 | 已覆盖 | 艺术家与制造企业联名（限量编号与收藏档案） | c2m_order, ip_license, edition, collector_record | contracts/edition.schema.json, contracts/collector-record.schema.json, c2m_craft/commerce/editions.py, out/edition_archive.json | I | J4 |  |
| A4.1 | A | M1 | 已覆盖 | 订单到工艺单、派工、品控、发货、分成结算 | c2m_order, craft_work_order, settlement | c2m_craft/commerce/orders.py, c2m_craft/commerce/dispatch.py, c2m_craft/commerce/settlement.py | D | J4 |  |
| A4.2 | A | M2 | 已覆盖 | 定制件交期承诺 | craft_work_order, production_schedule, c2m_order | config/commerce/capacity.json, c2m_craft/commerce/capacity.py, out/capacity_plan.json | I | J4 |  |
| A4.3 | A | M2 | 已覆盖 | 退款与争议处理 | c2m_order, settlement | c2m_craft/commerce/orders.py, config/commerce/pricing.json, out/quality_report.json | D | J4 |  |
| A4.4 | A | M2 | 已覆盖 | 质量标准 | qc_record, craft_work_order | config/commerce/quality.json, contracts/qc-record.schema.json, c2m_craft/commerce/quality.py, out/quality_report.json | I | J4 |  |
| A5.1 | A | M1 | 已覆盖 | 珠宝工艺规则（镶嵌/铸造/錾刻） | manufacturability_assessment | config/craft_rules/jewelry.json, c2m_craft/craft/rules.py | C | J3 |  |
| A5.2 | A | M1 | 已覆盖 | 硬木规则（榫卯/雕刻/表面）与企业设备能力 | manufacturability_assessment | config/craft_rules/hardwood.json, config/equipment/WS-HW-A.json, config/equipment/WS-HW-B.json | C | J3 |  |
| A5.3 | A | M1 | 已覆盖 | 判定：能不能做、哪里不能做、怎么改 | manufacturability_assessment | c2m_craft/craft/assessment.py, samples/concepts/expected.json | C | J3 |  |
| A5.4 | A | M1 | 已覆盖 | AI 初判与匠人复核两段式 | artisan_review, manufacturability_assessment | c2m_craft/craft/review.py, contracts/artisan-review.schema.json, static/app.js | C | J3 |  |
| A5.5 | A | M1 | 已覆盖 | 规则非程序员可维护 | - | c2m_craft/craft/lint.py, config/craft_rules/rule_file.schema.json, docs/rule-authoring-form.md | A | J3, J9 |  |
| B1 | B | M3 | 已覆盖 | 组件化企业 AI 服务层 | service_component, enterprise_profile | c2m_craft/enterprise/registry.py, c2m_craft/enterprise/runtime.py, config/enterprise/components.json, out/enterprise_report.json | J | J5 |  |
| B2 | B | M1 | 已覆盖 | 行业切换靠配置而非复制代码 | enterprise_profile, service_component | config/enterprise/profiles/EP-0001.json, config/enterprise/profiles/EP-0002.json, c2m_craft/enterprise/runtime.py, out/enterprise_report.json | J | J5 |  |
| B3 | B | M3 | 已覆盖 | 多语独立站、SEO、内容、外贸获客、CRM、询盘跟进 | growth_site, inquiry_lead, enterprise_profile | config/growth/site.json, config/growth/copy.json, config/growth/crm.json, c2m_craft/enterprise/growth/, out/growth_report.json, out/site/en/index.html | J | J6 |  |
| B4 | B | M3 | 已覆盖 | FDE 驻场交付手册 | enterprise_profile | docs/fde-handbook.md, config/enterprise/fde-checklist.json, out/enterprise_report.json | J | J5 |  |
| B5 | B | M1 | 已覆盖 | 一企一档样例 | enterprise_profile | samples/contracts/positive/enterprise-profile-EP-0001.json, config/enterprise/profiles/EP-0001.json | J | J5 |  |
| C5 | C | M1 | 已覆盖 | 授权合同模板 | ip_license, content_review | config/ip/licensing.json, c2m_craft/ip/licensing.py, out/licensing_pack.json, docs/licensing-templates.md | K | J7 |  |
| C6 | C | M4 | 已覆盖 | 衍生授权与质量标准 | merch_spec, ip_license | config/ip/licensing.json, c2m_craft/ip/licensing.py, out/licensing_pack.json, docs/licensing-templates.md | K | J7 |  |
| C7 | C | M1 | 已覆盖 | 不得主张传统原型与宗教场所名称独占 | ip_license, pattern_asset | c2m_craft/core/invariants.py, samples/library/assets.json | B | J10 |  |
| C1 | C | M4 | 已覆盖 | 双守护角色原创设定 | character_bible, content_review | config/ip/characters.json, c2m_craft/ip/bible.py, out/character_bible.json, docs/character-bible.md | K | J7 |  |
| C2 | C | M4 | 已覆盖 | 角色设定手册与视觉资产库 | character_bible, visual_asset | config/ip/visuals.json, c2m_craft/ip/visuals.py, out/ip_asset_library.json | K | J7 |  |
| C3 | C | M4 | 已覆盖 | 短剧工作流（脚本到成片） | short_drama, content_review | config/ip/drama.json, c2m_craft/ip/drama.py, out/short_drama_package.json, docs/short-drama-workflow.md | K | J7 |  |
| C4 | C | M4 | 已覆盖 | 一条样片 | short_drama, content_review | out/sample_reel.html, out/content_review.json, verify/records/ui_smoke.log | K | J7 |  |
| D1 | D | M4 | 已覆盖 | 可选的全球设计共创大赛运营包 | - | docs/competition-ops-pack.md | K | - |  |
| E1 | E | M1 | 已覆盖 | 可运行仓库与一键启动 | - | README.md, start.ps1, start.sh, c2m_craft/__main__.py | F | J0, J1 |  |
| E2 | E | M1 | 已覆盖 | 工艺规则、设备能力、授权字段以数据文件表达 | pattern_asset | config/craft_rules/jewelry.json, config/equipment/WS-JW-A.json, contracts/pattern-asset.schema.json | A | J2, J3 |  |
| E3 | E | M1 | 已覆盖 | 每模块验证记录：命令、输入、期望输出 | - | verify/run_verification.py, verify/records/tests_output.txt, verify/records/verification_output.txt, out/hash_manifest.json | F | J0, J9 |  |
| E4 | E | M1 | 已覆盖 | 资产须授权或自产，并做内容审核与真实性标注 | pattern_asset, ip_license, visual_asset, content_review | samples/library/assets.json, contracts/ip-license.schema.json, c2m_craft/ip/reviews.py, out/content_review.json | K | J10 |  |
| E5 | E | M1 | 已覆盖 | 合成样本，接口按真实字段 schema 定义 | common | samples/concepts/DC-0001.json, config/site.json | G | J10 |  |
| F1 | F | M1 | 排除 | 政策申报材料 | - | - | H | - |  |
| F2 | F | M1 | 排除 | 财政资金测算 | - | - | H | - |  |
| F3 | F | M1 | 排除 | 真实医疗诊疗功能 | - | - | H | - |  |
| F4 | F | M1 | 排除 | 线下空间建设 | - | - | H | - |  |
| F5 | F | M1 | 排除 | 需本地资质主体承接的授权类业务 | - | - | H | - |  |
| G1 | G | M2 | 计划 | 六行业业务流程访谈材料 | - | - | H | - |  |
| G2 | G | M2 | 计划 | 口头工艺规则与校对 | - | - | H | - |  |
| G3 | G | M2 | 计划 | 纹样资产授权清单 | pattern_asset | - | H | - |  |
| G4 | G | M2 | 计划 | 1 家珠宝与 1 家木工的工艺约束样例 | - | - | H | - |  |
| G5 | G | M2 | 计划 | 客户侧验收评审人 | - | - | H | - |  |
| H1 | H | M2 | 计划 | 按 A/B/C/D 模块拆分报价 | - | - | H | - |  |
| H2 | H | M2 | 计划 | 按里程碑拆分报价 | - | - | H | - |  |
| H3 | H | M2 | 计划 | 技术栈、开源复用与交付周期 | - | - | H | - |  |
| H4 | H | M2 | 计划 | 模型与算力成本口径 | - | - | H | - |  |
| I1 | I | M1 | 已覆盖 | M1：架构与数据契约、规则建模方案、可点击工作台原型 | common, design_concept, manufacturability_assessment | ARCHITECTURE.md, docs/data-contracts.md, docs/rule-modeling-plan.md, static/index.html | H | J0, J1, J2, J3, J4, J8, J9, J10 |  |
| I2 | I | M2 | 已覆盖 | M2：C2M 预售与制造协同链路、纹样授权资源库 | c2m_order, pattern_asset, customization_choice, edition, collector_record, qc_record, production_schedule, settlement | out/capacity_plan.json, out/customization_report.json, out/edition_archive.json, out/quality_report.json, out/settlement_report.md | I | J4, J2 |  |
| I3 | I | M3 | 已覆盖 | M3：两个行业组件的企业 AI 服务层与增长栈 | enterprise_profile, service_component, growth_site, inquiry_lead | out/enterprise_report.json, out/growth_report.json, docs/fde-handbook.md, docs/growth-playbook.md | J | J5, J6 |  |
| I4 | I | M4 | 已覆盖 | M4：IP 管线与一条样片、完整验证记录与交付文档 | character_bible, visual_asset, short_drama, content_review, ip_license, merch_spec | out/character_bible.json, out/ip_asset_library.json, out/short_drama_package.json, out/sample_reel.html, out/licensing_pack.json, out/content_review.json | K | J7 |  |

## 验收条目

| 验收 | 条目 | 覆盖 | M1 条目 | 证据 |
|---|---|---|---|---|
| J0 | 投标与交付都必须有可运行仓库，纯文档不接受 | 已覆盖 | E1, E3, I1 | I1, E1, E3 |
| J1 | 一键启动后四大工作流可端到端导航 | 已覆盖 | A1.1, A1.4, A2.1, A4.1 | A1.1, A1.4, A2.1, A4.1 |
| J2 | 资产摄入拒绝缺失授权来源或使用范围，含正负样例 | 已覆盖 | A2.1 | A2.1, C7, E2 |
| J3 | 至少 10 条概念输入含 3 条反例，10/10 与仓库规则文档一致 | 已覆盖 | A5.1, A5.2, A5.3, A5.4, A5.5 | A5.1, A5.2, A5.3, A5.4 |
| J4 | 一条定制订单跑通下单、工艺单、派工、品控、发货、分成，金额可追溯且覆盖退款路径 | 已覆盖 | A3.1, A3.2, A3.3, A4.1, A4.2, A4.3, A4.4 | A3.1, A3.2, A3.3, A4.1, A4.2, A4.3, A4.4 |
| J5 | 至少两个行业可复用组件，行业切换靠配置，含 FDE 手册与完整一企一档 | 已覆盖 | B1, B2, B4, B5, I3 | B1, B2, B4, B5, I3 |
| J6 | 多语站点生成、SEO 元数据、询盘到 CRM 闭环，各有端到端测试 | 已覆盖 | B3, I3 | B3, I3 |
| J7 | 双角色手册、视觉资产库、完整短剧流程与一条样片、授权模板与衍生规格 | 已覆盖 | C1, C2, C3, C4, C5, C6, E4, I4 | C1, C2, C3, C4, C5, C6, E4, I4 |
| J8 | 授权字段、可制造性、订单状态机、分成计算四类单测一键通过 | 已覆盖 | E3, I1 | E3 |
| J9 | 文档中提到的每条命令与接口真实存在 | 已覆盖 | E3, A5.5 | E3, A5.5 |
| J10 | 仅用合成或脱敏样本，不含真实机密数据，不得主张传统或宗教遗产独占 | 已覆盖 | C7, E5 | C7, E4, E5 |

验证组：

- A: contracts and registry
- B: licensing ingestion gate
- C: manufacturability assessment
- D: C2M order pipeline
- E: four core unit-test areas
- F: documentation and implementation consistency
- G: compliance, determinism and offline guarantees
- H: requirement coverage
- I: milestone 2: customisation, capacity, editions, royalties, quality
- J: milestone 3: enterprise service layer, FDE handbook and growth stack
- K: milestone 4: cultural IP character bible, short drama, sample reel and licensing
