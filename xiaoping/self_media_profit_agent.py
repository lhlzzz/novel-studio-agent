#!/usr/bin/env python3
"""
Local self-media profit agent runtime for xiaoping.

This agent does not log in, publish, message users, quote prices, collect
payments, or operate real platform accounts. It turns a topic + offer type into
platform-specific internal work items, risk gates, and evidence requirements.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Literal


Region = Literal["cn", "global"]
AccountMode = Literal["internal", "owned"]
OfferType = Literal[
    "digital_product",
    "leadgen",
    "affiliate",
    "service",
    "content_asset",
]


@dataclass(frozen=True)
class Platform:
    key: str
    name: str
    region: Region
    surfaces: tuple[str, ...]
    fit_tags: tuple[str, ...]
    monetization_paths: tuple[str, ...]
    evidence_required: tuple[str, ...]
    gates: tuple[str, ...]
    production_effort: int
    external_risk: int


@dataclass(frozen=True)
class AgentInput:
    topic: str
    audience: str
    offer: OfferType
    region: Literal["cn", "global", "both"]
    max_platforms: int
    account_mode: AccountMode


@dataclass(frozen=True)
class WorkItem:
    platform_key: str
    platform_name: str
    score: int
    content_angle: str
    content_formats: tuple[str, ...]
    internal_asset_recipe: tuple[str, ...]
    monetization_hypothesis: str
    evidence_to_collect: tuple[str, ...]
    required_gates: tuple[str, ...]
    next_internal_action: str
    account_mode: AccountMode
    owned_account_path_allowed: bool
    launch_scope: str


@dataclass(frozen=True)
class ContentPackage:
    platform_key: str
    platform_name: str
    score: int
    account_mode: AccountMode
    topic: str
    audience: str
    offer: OfferType
    titles: tuple[str, ...]
    body_type: str
    body_steps: tuple[str, ...]
    safe_closing: str
    evidence_checklist: tuple[str, ...]
    gate_checklist: tuple[str, ...]
    launch_checklist: tuple[str, ...]
    output_boundary: str


@dataclass(frozen=True)
class LaunchPlan:
    platform_key: str
    platform_name: str
    account_mode: AccountMode
    owned_account_path_allowed: bool
    topic: str
    audience: str
    offer: OfferType
    account_requirements: tuple[str, ...]
    publish_steps: tuple[str, ...]
    monetization_steps: tuple[str, ...]
    evidence_to_collect: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    runtime_boundary: str


@dataclass(frozen=True)
class ReproductionPlan:
    platform_key: str
    platform_name: str
    account_mode: AccountMode
    asset_cny: float
    reward_threshold_cny: float
    reward_unlocked: bool
    reward: str
    allowed_child_node: str
    reproduction_steps: tuple[str, ...]
    child_node_rules: tuple[str, ...]
    prohibited_downline_rules: tuple[str, ...]
    evidence_to_collect: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    runtime_boundary: str


PLATFORMS: tuple[Platform, ...] = (
    Platform(
        key="wechat_channels",
        name="微信视频号",
        region="cn",
        surfaces=("short_video", "live", "shop", "service_account_link"),
        fit_tags=("trust", "wechat_ecosystem", "local_service", "digital_product", "leadgen"),
        monetization_paths=("微信小店/资料包", "服务号/小程序承接", "蓝 V 信任获客"),
        evidence_required=("后台只读权限", "视频数据", "带货/小店权限", "收入与服务状态"),
        gates=("登录/后台只读需老板批准", "发布需老板批准", "交易/私信/商品操作需老板批准"),
        production_effort=3,
        external_risk=7,
    ),
    Platform(
        key="douyin",
        name="抖音",
        region="cn",
        surfaces=("short_video", "live", "shop", "local_life"),
        fit_tags=("high_distribution", "local_service", "affiliate", "leadgen", "service"),
        monetization_paths=("本地生活线索", "小店/橱窗", "直播/短视频带货"),
        evidence_required=("类目资质", "商品/团购权限", "账号历史数据", "平台规则核验"),
        gates=("登录/发布/投流/直播/交易均需单独批准",),
        production_effort=4,
        external_risk=8,
    ),
    Platform(
        key="xiaohongshu",
        name="小红书",
        region="cn",
        surfaces=("note", "short_video", "search"),
        fit_tags=("search", "decision", "template", "digital_product", "service"),
        monetization_paths=("搜索种草", "资料/模板说明", "服务咨询候选"),
        evidence_required=("公开笔记结构", "评论痛点", "违规词/导流规则核验"),
        gates=("真实账号发布/评论/私信/导流需批准",),
        production_effort=3,
        external_risk=7,
    ),
    Platform(
        key="kuaishou",
        name="快手",
        region="cn",
        surfaces=("short_video", "live", "shop"),
        fit_tags=("trust", "local_service", "shop", "affiliate"),
        monetization_paths=("直播/短视频带货", "本地服务信任获客"),
        evidence_required=("账号类目", "小店/直播权限", "直播能力评估"),
        gates=("直播/商品/交易/私信动作需批准",),
        production_effort=4,
        external_risk=8,
    ),
    Platform(
        key="bilibili",
        name="B站",
        region="cn",
        surfaces=("video", "column", "search"),
        fit_tags=("education", "tutorial", "long_tail", "digital_product", "content_asset"),
        monetization_paths=("课程/资料包候选", "长尾搜索流量", "品牌/广告候选"),
        evidence_required=("同类视频结构", "搜索关键词", "评论问题", "版权边界"),
        gates=("发布/商业合作/引流需批准",),
        production_effort=4,
        external_risk=5,
    ),
    Platform(
        key="zhihu",
        name="知乎",
        region="cn",
        surfaces=("answer", "article", "video"),
        fit_tags=("search", "authority", "service", "digital_product", "leadgen"),
        monetization_paths=("专业内容获客", "盐选/付费咨询候选", "资料说明"),
        evidence_required=("问题热度", "回答结构", "专业资质边界"),
        gates=("专业建议/引流/咨询/收费需批准",),
        production_effort=3,
        external_risk=6,
    ),
    Platform(
        key="weibo",
        name="微博",
        region="cn",
        surfaces=("post", "topic", "video"),
        fit_tags=("trend", "distribution", "brand", "content_asset"),
        monetization_paths=("热点分发", "品牌曝光候选"),
        evidence_required=("话题趋势", "评论反馈", "品牌安全核验"),
        gates=("发布/转发/评论运营需批准",),
        production_effort=2,
        external_risk=6,
    ),
    Platform(
        key="tiktok",
        name="TikTok",
        region="global",
        surfaces=("short_video", "shop", "live"),
        fit_tags=("high_distribution", "affiliate", "shop", "digital_product", "leadgen"),
        monetization_paths=("TikTok Shop/affiliate 候选", "短视频流量", "直播候选"),
        evidence_required=("地区可用性", "账号/小店权限", "内容政策核验", "素材授权"),
        gates=("跨境发布/带货/收款/素材版权需批准",),
        production_effort=4,
        external_risk=8,
    ),
    Platform(
        key="youtube_shorts",
        name="YouTube Shorts",
        region="global",
        surfaces=("short_video", "long_video", "community"),
        fit_tags=("education", "search", "content_asset", "digital_product", "affiliate"),
        monetization_paths=("广告分成候选", "affiliate", "数字产品说明"),
        evidence_required=("频道资格", "关键词", "观众留存", "版权核验"),
        gates=("发布/外链/affiliate/版权素材需批准",),
        production_effort=4,
        external_risk=6,
    ),
    Platform(
        key="instagram_reels",
        name="Instagram Reels",
        region="global",
        surfaces=("reels", "carousel", "stories"),
        fit_tags=("visual", "brand", "affiliate", "digital_product", "leadgen"),
        monetization_paths=("affiliate", "资料页/链接候选", "品牌合作候选"),
        evidence_required=("账号地区能力", "链接/商店权限", "素材版权"),
        gates=("发布/私信/链接/商业合作需批准",),
        production_effort=4,
        external_risk=7,
    ),
    Platform(
        key="facebook_reels",
        name="Facebook Reels",
        region="global",
        surfaces=("reels", "page", "group"),
        fit_tags=("community", "local_service", "affiliate", "leadgen"),
        monetization_paths=("主页/社群线索", "affiliate", "广告分成候选"),
        evidence_required=("主页资格", "社群规则", "链接政策", "素材版权"),
        gates=("主页/社群发布、私信、外链需批准",),
        production_effort=3,
        external_risk=7,
    ),
    Platform(
        key="x_twitter",
        name="X/Twitter",
        region="global",
        surfaces=("post", "thread", "video"),
        fit_tags=("trend", "thread", "content_asset", "leadgen", "affiliate"),
        monetization_paths=("线程引流候选", "affiliate", "订阅/广告分成候选"),
        evidence_required=("账号资格", "话题趋势", "链接政策", "评论风险"),
        gates=("发布/私信/外链/付费订阅需批准",),
        production_effort=2,
        external_risk=6,
    ),
    Platform(
        key="linkedin",
        name="LinkedIn",
        region="global",
        surfaces=("post", "article", "newsletter", "video"),
        fit_tags=("b2b", "authority", "service", "leadgen", "digital_product"),
        monetization_paths=("B2B 线索", "newsletter", "服务/模板候选"),
        evidence_required=("目标行业", "案例边界", "专业资质", "链接政策"),
        gates=("发布/私信/销售触达/报价需批准",),
        production_effort=3,
        external_risk=6,
    ),
    Platform(
        key="reddit",
        name="Reddit",
        region="global",
        surfaces=("subreddit_post", "comment"),
        fit_tags=("community", "research", "feedback", "content_asset"),
        monetization_paths=("痛点研究", "内容验证", "低直接变现"),
        evidence_required=("subreddit 规则", "公开讨论", "反推广风险"),
        gates=("发帖/评论/链接/私信需批准，优先只读研究",),
        production_effort=2,
        external_risk=8,
    ),
    Platform(
        key="pinterest",
        name="Pinterest",
        region="global",
        surfaces=("pin", "board", "search"),
        fit_tags=("search", "visual", "template", "digital_product", "affiliate"),
        monetization_paths=("模板/资料视觉入口", "affiliate", "长尾搜索"),
        evidence_required=("关键词", "素材版权", "外链/商店权限"),
        gates=("发布/外链/affiliate 需批准",),
        production_effort=3,
        external_risk=5,
    ),
)


OFFER_TAGS: dict[OfferType, tuple[str, ...]] = {
    "digital_product": ("digital_product", "template", "education", "search", "content_asset"),
    "leadgen": ("leadgen", "trust", "authority", "local_service", "b2b"),
    "affiliate": ("affiliate", "shop", "visual", "high_distribution"),
    "service": ("service", "trust", "authority", "local_service", "b2b"),
    "content_asset": ("content_asset", "search", "education", "thread", "community"),
}


OWNED_ACCOUNT_ALLOWED_NOTE = (
    "用户已允许自创账号发布并获利；该授权允许 runtime 生成自有账号发布/变现路径。"
    "CLI 仍只做本地计划、内容包和检查清单，不执行注册、登录、发布、私信、评论、收款或订单动作。"
)

REPRODUCTION_SAFE_BOUNDARY = (
    "繁衍机制只允许复制自有/授权的内容节点、账号节点或合作节点；"
    "不得设计多级返佣、拉人头收益、入门费、按招募人数分成或非授权账号控制。"
)


@dataclass(frozen=True)
class PlatformEvidence:
    evidence_collected: tuple[str, ...]
    additional_gates: tuple[str, ...]
    additional_stop_conditions: tuple[str, ...]
    score_adjustment: int
    notes: str


def load_evidence(path: str | None) -> dict[str, PlatformEvidence]:
    if path is None:
        return {}
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    result: dict[str, PlatformEvidence] = {}
    for key, entry in raw.get("platforms", {}).items():
        result[key] = PlatformEvidence(
            evidence_collected=tuple(entry.get("evidence_collected", [])),
            additional_gates=tuple(entry.get("additional_gates", [])),
            additional_stop_conditions=tuple(entry.get("additional_stop_conditions", [])),
            score_adjustment=int(entry.get("score_adjustment", 0)),
            notes=entry.get("notes", ""),
        )
    return result


def merge_evidence(
    base: tuple[str, ...], evidence: dict[str, PlatformEvidence], platform_key: str
) -> tuple[str, ...]:
    if platform_key not in evidence:
        return base
    extra = evidence[platform_key].evidence_collected
    return base + extra if extra else base


def merge_gates(
    base: tuple[str, ...], evidence: dict[str, PlatformEvidence], platform_key: str
) -> tuple[str, ...]:
    if platform_key not in evidence:
        return base
    extra = evidence[platform_key].additional_gates
    return base + extra if extra else base


def merge_stops(
    base: tuple[str, ...], evidence: dict[str, PlatformEvidence], platform_key: str
) -> tuple[str, ...]:
    if platform_key not in evidence:
        return base
    extra = evidence[platform_key].additional_stop_conditions
    return base + extra if extra else base


def platform_scope(region: str) -> Iterable[Platform]:
    if region == "both":
        return PLATFORMS
    return (platform for platform in PLATFORMS if platform.region == region)


def platform_primary_goal(platform: Platform, agent_input: AgentInput) -> str:
    if platform.key == "wechat_channels":
        return "monetization"
    if platform.region == "global":
        return "growth"
    if agent_input.offer in ("leadgen", "service"):
        return "balanced"
    return "growth"


def score_platform(
    platform: Platform,
    agent_input: AgentInput,
    evidence: dict[str, PlatformEvidence] | None = None,
) -> int:
    tags = set(platform.fit_tags)
    offer_tags = set(OFFER_TAGS[agent_input.offer])
    tag_score = len(tags & offer_tags) * 8
    risk_penalty = platform.external_risk * 3
    effort_penalty = platform.production_effort * 2
    base = 55 + tag_score - risk_penalty - effort_penalty

    topic = f"{agent_input.topic} {agent_input.audience}".lower()
    if any(word in topic for word in ("商家", "老板", "门店", "local", "business", "b2b")):
        if {"local_service", "b2b", "trust"} & tags:
            base += 8
    if any(word in topic for word in ("模板", "prompt", "提示词", "notion", "excel", "表格")):
        if {"template", "digital_product"} & tags:
            base += 10
    if any(word in topic for word in ("教程", "工具", "ai", "自动化", "automation")):
        if {"education", "digital_product", "content_asset"} & tags:
            base += 6

    if evidence and platform.key in evidence:
        base += evidence[platform.key].score_adjustment

    return max(0, min(100, base))


def content_angle(platform: Platform, agent_input: AgentInput) -> str:
    goal = platform_primary_goal(platform, agent_input)
    base = agent_input.topic
    if platform.key == "wechat_channels":
        if agent_input.offer in ("leadgen", "service"):
            return f"围绕 `{base}` 做蓝 V 信任成交：先展示问题、资格和交付边界，再引导至私域或服务入口。"
        if agent_input.offer == "digital_product":
            return f"围绕 `{base}` 做高转化资料包/模板演示，优先验证价格、交付和复购，不做纯涨粉。"
        return f"围绕 `{base}` 做可核验获利内容，优先服务橱窗、小店、资料包和私域承接，不只看播放。"
    if agent_input.offer in ("leadgen", "service"):
        return f"把 `{base}` 拆成一个可验证的问题清单，先涨粉、收藏和信任，再判断是否值得进入人工承接。"
    if agent_input.offer == "affiliate":
        return f"围绕 `{base}` 做场景判断和避坑，先涨粉和互动，不承诺效果，不放未核验商品链接。"
    if agent_input.offer == "digital_product":
        return f"把 `{base}` 包装成可保存/可复制的模板或清单，先涨粉和收藏，验证需求后再考虑转化。"
    if goal == "growth":
        return f"围绕 `{base}` 做短视频涨粉资产，优先关注、完播、收藏和粉丝沉淀。"
    return f"围绕 `{base}` 做内容资产沉淀，优先验证搜索、收藏、评论和复用价值。"


def monetization_hypothesis(platform: Platform, agent_input: AgentInput) -> str:
    paths = " / ".join(platform.monetization_paths)
    if agent_input.account_mode == "owned":
        return f"自创账号候选获利路径：{paths}。允许进入自有账号发布获利设计，但执行前仍需核验平台规则、账号权限、素材版权和收款主体。"
    return f"候选获利路径：{paths}。当前只作为内部假设，真实变现动作必须单独 gate。"


def required_gates_for(
    platform: Platform,
    agent_input: AgentInput,
    evidence: dict[str, PlatformEvidence] | None = None,
) -> tuple[str, ...]:
    base = platform.gates
    if agent_input.account_mode == "owned":
        base = base + (
            "自创账号路径已允许：执行前记录平台、账号名、账号归属、发布范围和获利方式",
            "CLI 只生成本地计划，不执行注册/登录/发布/收款/订单动作",
        )
    return merge_gates(base, evidence or {}, platform.key)


def launch_scope_for(agent_input: AgentInput) -> str:
    if agent_input.account_mode == "owned":
        return "自创账号可发布获利；当前输出是启动清单和内容包，外部动作由人工或另行授权执行。"
    return "内部研究/内容包模式；不进入真实发布或获利动作。"


def build_work_items(
    agent_input: AgentInput,
    evidence: dict[str, PlatformEvidence] | None = None,
) -> list[WorkItem]:
    ranked = sorted(
        platform_scope(agent_input.region),
        key=lambda platform: score_platform(platform, agent_input, evidence),
        reverse=True,
    )[: agent_input.max_platforms]

    items: list[WorkItem] = []
    for platform in ranked:
        items.append(
            WorkItem(
                platform_key=platform.key,
                platform_name=platform.name,
                score=score_platform(platform, agent_input, evidence),
                content_angle=content_angle(platform, agent_input),
                content_formats=platform.surfaces,
                internal_asset_recipe=(
                    "1 个平台适配标题",
                    "1 条 30-60 秒短内容脚本或图文结构",
                    "1 个不含真实引流/报价/收款的安全结尾",
                    "1 张平台证据清单",
                ),
                monetization_hypothesis=monetization_hypothesis(platform, agent_input),
                evidence_to_collect=merge_evidence(
                    platform.evidence_required, evidence or {}, platform.key
                ),
                required_gates=required_gates_for(platform, agent_input),
                next_internal_action=f"生成 `{platform.name}` 内部稿，不发布；补齐证据后再判断是否申请 gate。",
                account_mode=agent_input.account_mode,
                owned_account_path_allowed=agent_input.account_mode == "owned",
                launch_scope=launch_scope_for(agent_input),
            )
        )
    return items


def build_report(
    agent_input: AgentInput,
    evidence: dict[str, PlatformEvidence] | None = None,
) -> dict:
    items = build_work_items(agent_input, evidence)
    return {
        "agent": "xiaoping-self-media-profit-agent",
        "version": "0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": asdict(agent_input),
        "external_action_allowed": False,
        "owned_account_publishing_allowed": agent_input.account_mode == "owned",
        "owned_account_policy": OWNED_ACCOUNT_ALLOWED_NOTE if agent_input.account_mode == "owned" else "",
        "hard_boundary": (
            "This CLI does not execute login, publish, private message, comment operation, "
            "quote, payment, shop/order action, ad spend, scraping beyond public/authorized "
            "scope, or real account automation. In owned account mode it only generates the "
            "human-executable launch plan for self-created accounts."
        ),
        "platform_count": len(PLATFORMS),
        "work_items": [asdict(item) for item in items],
    }


def select_work_item(
    agent_input: AgentInput,
    platform_key: str | None,
    evidence: dict[str, PlatformEvidence] | None = None,
) -> WorkItem:
    full_input = AgentInput(
        topic=agent_input.topic,
        audience=agent_input.audience,
        offer=agent_input.offer,
        region=agent_input.region,
        max_platforms=len(PLATFORMS),
        account_mode=agent_input.account_mode,
    )
    items = build_work_items(full_input, evidence)
    if platform_key is None:
        return items[0]
    for item in items:
        if item.platform_key == platform_key:
            return item
    valid = ", ".join(item.platform_key for item in items)
    raise ValueError(f"Unknown platform `{platform_key}` for region `{agent_input.region}`. Valid: {valid}")


def body_type_for(item: WorkItem) -> str:
    formats = set(item.content_formats)
    if formats & {"short_video", "reels", "video", "pin"}:
        return "30-60 秒短内容脚本"
    if formats & {"answer", "article", "column", "thread", "post"}:
        return "图文/长尾搜索结构"
    return "平台适配内容结构"


def build_content_package(
    agent_input: AgentInput,
    platform_key: str | None = None,
    evidence: dict[str, PlatformEvidence] | None = None,
) -> ContentPackage:
    item = select_work_item(agent_input, platform_key, evidence)
    titles = (
        f"{agent_input.audience} 做 `{agent_input.topic}` 前，先问这 5 个问题",
        f"别急着卖 `{agent_input.topic}`，先做一张内部检查表",
        f"用 60 秒把 `{agent_input.topic}` 变成可复制模板",
    )
    body_steps = (
        f"开头：{agent_input.audience} 做 `{agent_input.topic}` 时，先别急着发链接、报价或承诺结果。",
        "问题：把重复动作拆成 3 个可观察步骤，说明为什么现在容易浪费时间或踩坑。",
        "方法：给出一个可复制模板框架，只展示字段和流程，不填真实客户、价格、库存或收款信息。",
        f"平台适配：按 `{item.platform_name}` 的内容形式重写为 {body_type_for(item)}，保留人工复核节点。",
        "证据：列出下一轮需要核验的平台规则、账号权限、公开案例或评论问题。",
    )
    evidence_checklist = item.evidence_to_collect + (
        "平台当前规则/账号权限需浏览器资料或后台只读证据",
        "不得把内部评分、样例脚本或候选路径写成真实数据",
    )
    gate_checklist = item.required_gates + (
        "未确认账号归属、平台规则、素材版权和收款主体前不得执行外部动作",
    )
    launch_checklist = (
        "确认该账号为自创/自有/授权账号",
        f"确认 `{item.platform_name}` 当前注册、发布和获利资格",
        "确认素材为原创、授权或可商用",
        "确认不使用虚假身份、搬运内容、违规导流或收益承诺",
        "确认发布后只记录公开数据和平台允许的数据",
    )
    if agent_input.account_mode == "internal":
        launch_checklist = ("当前为内部模式，不执行真实发布",) + launch_checklist
    return ContentPackage(
        platform_key=item.platform_key,
        platform_name=item.platform_name,
        score=item.score,
        account_mode=agent_input.account_mode,
        topic=agent_input.topic,
        audience=agent_input.audience,
        offer=agent_input.offer,
        titles=titles,
        body_type=body_type_for(item),
        body_steps=body_steps,
        safe_closing="安全结尾：本内容仅为内部模板演示；不放链接、不报价、不承诺收益、不引导私信或交易。",
        evidence_checklist=evidence_checklist,
        gate_checklist=gate_checklist,
        launch_checklist=launch_checklist,
        output_boundary="Local content package only. The CLI does not register, log in, publish, message, comment, quote, collect payment, operate shop/order actions, run ads, or automate real accounts.",
    )


def build_launch_plan(
    agent_input: AgentInput,
    platform_key: str | None = None,
    evidence: dict[str, PlatformEvidence] | None = None,
) -> LaunchPlan:
    item = select_work_item(agent_input, platform_key, evidence)
    owned = agent_input.account_mode == "owned"
    base_stops = (
        "需要绕过验证码、短信、人脸、风控或平台访问控制",
        "需要使用他人素材、搬运视频、未授权音乐或第三方水印内容",
        "需要承诺收益、保证成交、虚假资质、虚假评价或误导性身份",
        "涉及报价、收款、订单、客服或私信且口径未人工确认",
    )
    return LaunchPlan(
        platform_key=item.platform_key,
        platform_name=item.platform_name,
        account_mode=agent_input.account_mode,
        owned_account_path_allowed=owned,
        topic=agent_input.topic,
        audience=agent_input.audience,
        offer=agent_input.offer,
        account_requirements=(
            "账号必须是自创、自有或明确授权账号",
            "记录平台、账号名、注册主体、登录保管人和可执行动作范围",
            "确认平台当前注册/创作者/商业化/收款资格，不用假设替代证据",
            "确认素材、头像、昵称、简介、链接和收款主体不侵权、不误导",
        ),
        publish_steps=(
            "生成本地内容包并完成 5 项风险自查",
            "人工注册/登录账号，遇到验证码、短信、人脸或协议确认时停止自动化",
            "人工确认标题、正文、封面、标签、链接和可见范围",
            "发布后只记录平台允许查看的数据，不批量刷量、不诱导互动",
        ),
        monetization_steps=(
            "优先从低风险数字产品、模板、affiliate 或平台内合规工具开始",
            "开通商业化、橱窗、店铺、联盟或收款能力前核验平台资格和主体要求",
            "所有价格、库存、交付、退款和客服口径先人工确认",
            "记录内容成本、发布时间、曝光、互动、点击、线索和收入，不用未核验数据下结论",
        ),
        evidence_to_collect=item.evidence_to_collect
        + (
            "账号归属与授权记录",
            "发布内容截图/链接",
            "平台允许范围内的数据截图或导出",
            "获利路径的收款/结算/联盟/店铺资格证据",
        ),
        stop_conditions=merge_stops(base_stops, evidence or {}, item.platform_key),
        runtime_boundary="This command generates a launch plan only. It does not perform external platform actions.",
    )


def build_reproduction_plan(
    agent_input: AgentInput,
    platform_key: str | None,
    asset_cny: float,
    reward_threshold_cny: float,
    evidence: dict[str, PlatformEvidence] | None = None,
) -> ReproductionPlan:
    item = select_work_item(agent_input, platform_key, evidence)
    reward_unlocked = asset_cny >= reward_threshold_cny
    reward = (
        "解锁 1 个合规子节点复制名额：可复制一个自创/自有/明确授权账号、栏目或内容资产包。"
        if reward_unlocked
        else "未解锁：继续积累可核验资产，达到阈值后才允许复制子节点。"
    )
    allowed_child_node = (
        f"{item.platform_name} 同主题子账号/栏目/内容包，必须归属自有或明确授权主体。"
        if reward_unlocked
        else "None"
    )
    return ReproductionPlan(
        platform_key=item.platform_key,
        platform_name=item.platform_name,
        account_mode=agent_input.account_mode,
        asset_cny=asset_cny,
        reward_threshold_cny=reward_threshold_cny,
        reward_unlocked=reward_unlocked,
        reward=reward,
        allowed_child_node=allowed_child_node,
        reproduction_steps=(
            "核验资产来源：收入、结算、余额、应收或库存价值必须有截图/导出/人工记录。",
            f"确认资产达到 {reward_threshold_cny:.2f} CNY 后，只解锁 1 个子节点，不无限扩张。",
            "复制前先复盘父节点：内容成本、素材来源、获利路径、风险词、平台规则、停止条件。",
            "子节点只复制可验证的内容结构和资产包，不复制违规导流、刷量、虚假承诺或他人素材。",
            "子节点上线后独立记录资产、成本、数据和风险，不把父节点收益重复计入。",
        ),
        child_node_rules=(
            "子节点必须是自创、自有或明确授权账号/栏目/内容资产。",
            "子节点必须有独立平台、账号、负责人、素材来源和收款主体记录。",
            "每个子节点先跑低风险内容包，再申请商业化、联盟、店铺或收款能力。",
            "子节点奖励只来自真实资产增长或内容资产复用价值，不来自招募人数。",
        ),
        prohibited_downline_rules=(
            "不得向下线收取入门费、代理费、保证金或培训费来获得资格。",
            "不得按拉人数量、层级人数或下线再发展人数发放奖励。",
            "不得承诺收益、保本、包赚、保证成交或虚构成功案例。",
            "不得控制、租借、购买、盗用、批量注册非授权账号。",
            "不得把多级返佣包装成内容矩阵或自媒体联盟。",
        ),
        evidence_to_collect=item.evidence_to_collect
        + (
            "父节点资产达到阈值的证据",
            "奖励解锁记录",
            "子节点账号/栏目/内容包归属记录",
            "子节点独立成本、收入、风险和停止条件记录",
        ),
        stop_conditions=merge_stops(
            (
                "资产金额无法核验或重复计算",
                "扩张依赖拉人头、入门费、代理费、层级返佣或保证收益",
                "子节点需要非授权账号、批量注册、绕风控或侵权素材",
                "无法说明子节点独立内容价值和真实获利路径",
            ),
            evidence or {},
            item.platform_key,
        ),
        runtime_boundary=f"{REPRODUCTION_SAFE_BOUNDARY} This command only generates a local reproduction plan.",
    )


def render_markdown(report: dict) -> str:
    lines = [
        "# Xiaoping Self-Media Profit Agent v0.1",
        "",
        f"- Topic: `{report['input']['topic']}`",
        f"- Audience: `{report['input']['audience']}`",
        f"- Offer: `{report['input']['offer']}`",
        f"- Region: `{report['input']['region']}`",
        f"- Account mode: `{report['input']['account_mode']}`",
        f"- External action allowed: `{report['external_action_allowed']}`",
        f"- Owned account publishing allowed: `{report['owned_account_publishing_allowed']}`",
        "",
        "## Hard Boundary",
        "",
        report["hard_boundary"],
        "",
        "## Ranked Work Items",
        "",
    ]

    topic = report['input']['topic']
    audience = report['input']['audience']
    offer = report['input']['offer']
    for index, item in enumerate(report["work_items"], start=1):
        platform = next(p for p in PLATFORMS if p.key == item['platform_key'])
        primary_goal = platform_primary_goal(platform, AgentInput(topic=topic, audience=audience, offer=offer, region=report['input']['region'], max_platforms=1, account_mode=report['input']['account_mode']))
        if primary_goal == "growth":
            primary_focus = "涨粉优先"
        elif primary_goal == "monetization":
            primary_focus = "视频号蓝 V 获利优先"
        else:
            primary_focus = "涨粉与变现平衡"
        lines.extend(
            [
                f"### {index}. {item['platform_name']} (`{item['platform_key']}`) - score {item['score']}/100",
                "",
                f"- Primary focus: {primary_focus}",
                f"- Content angle: {item['content_angle']}",
                f"- Formats: {', '.join(item['content_formats'])}",
                f"- Monetization hypothesis: {item['monetization_hypothesis']}",
                f"- Internal asset recipe: {', '.join(item['internal_asset_recipe'])}",
                f"- Evidence to collect: {', '.join(item['evidence_to_collect'])}",
                f"- Required gates: {', '.join(item['required_gates'])}",
                f"- Launch scope: {item['launch_scope']}",
                f"- Next internal action: {item['next_internal_action']}",
                "",
            ]
        )

    return "\n".join(lines)


def render_package_markdown(package: ContentPackage) -> str:
    lines = [
        "# Xiaoping Self-Media Content Package v0.1",
        "",
        f"- Platform: `{package.platform_name}` (`{package.platform_key}`)",
        f"- Score: `{package.score}/100`",
        f"- Topic: `{package.topic}`",
        f"- Audience: `{package.audience}`",
        f"- Offer: `{package.offer}`",
        f"- Account mode: `{package.account_mode}`",
        f"- Body type: `{package.body_type}`",
        "",
        "## Title Options",
        "",
    ]
    lines.extend(f"- {title}" for title in package.titles)
    lines.extend(["", "## Body Steps", ""])
    lines.extend(f"{index}. {step}" for index, step in enumerate(package.body_steps, start=1))
    lines.extend(["", "## Safe Closing", "", package.safe_closing, "", "## Evidence Checklist", ""])
    lines.extend(f"- {item}" for item in package.evidence_checklist)
    lines.extend(["", "## Gate Checklist", ""])
    lines.extend(f"- {item}" for item in package.gate_checklist)
    lines.extend(["", "## Launch Checklist", ""])
    lines.extend(f"- {item}" for item in package.launch_checklist)
    lines.extend(["", "## Output Boundary", "", package.output_boundary, ""])
    return "\n".join(lines)


def render_launch_plan_markdown(plan: LaunchPlan) -> str:
    lines = [
        "# Xiaoping Owned Account Launch Plan v0.1",
        "",
        f"- Platform: `{plan.platform_name}` (`{plan.platform_key}`)",
        f"- Account mode: `{plan.account_mode}`",
        f"- Owned account path allowed: `{plan.owned_account_path_allowed}`",
        f"- Topic: `{plan.topic}`",
        f"- Audience: `{plan.audience}`",
        f"- Offer: `{plan.offer}`",
        "",
        "## Account Requirements",
        "",
    ]
    lines.extend(f"- {item}" for item in plan.account_requirements)
    lines.extend(["", "## Publish Steps", ""])
    lines.extend(f"{index}. {item}" for index, item in enumerate(plan.publish_steps, start=1))
    lines.extend(["", "## Monetization Steps", ""])
    lines.extend(f"{index}. {item}" for index, item in enumerate(plan.monetization_steps, start=1))
    lines.extend(["", "## Evidence To Collect", ""])
    lines.extend(f"- {item}" for item in plan.evidence_to_collect)
    lines.extend(["", "## Stop Conditions", ""])
    lines.extend(f"- {item}" for item in plan.stop_conditions)
    lines.extend(["", "## Runtime Boundary", "", plan.runtime_boundary, ""])
    return "\n".join(lines)


def render_reproduction_plan_markdown(plan: ReproductionPlan) -> str:
    lines = [
        "# Xiaoping Reproduction Reward Plan v0.1",
        "",
        f"- Platform: `{plan.platform_name}` (`{plan.platform_key}`)",
        f"- Account mode: `{plan.account_mode}`",
        f"- Asset CNY: `{plan.asset_cny:.2f}`",
        f"- Reward threshold CNY: `{plan.reward_threshold_cny:.2f}`",
        f"- Reward unlocked: `{plan.reward_unlocked}`",
        f"- Reward: {plan.reward}",
        f"- Allowed child node: {plan.allowed_child_node}",
        "",
        "## Reproduction Steps",
        "",
    ]
    lines.extend(f"{index}. {item}" for index, item in enumerate(plan.reproduction_steps, start=1))
    lines.extend(["", "## Child Node Rules", ""])
    lines.extend(f"- {item}" for item in plan.child_node_rules)
    lines.extend(["", "## Prohibited Downline Rules", ""])
    lines.extend(f"- {item}" for item in plan.prohibited_downline_rules)
    lines.extend(["", "## Evidence To Collect", ""])
    lines.extend(f"- {item}" for item in plan.evidence_to_collect)
    lines.extend(["", "## Stop Conditions", ""])
    lines.extend(f"- {item}" for item in plan.stop_conditions)
    lines.extend(["", "## Runtime Boundary", "", plan.runtime_boundary, ""])
    return "\n".join(lines)


def render_batch_packages_markdown(packages: list[ContentPackage]) -> str:
    sections = [f"# Xiaoping Batch Content Packages ({len(packages)} platforms)\n"]
    for pkg in packages:
        sections.append(render_package_markdown(pkg))
    return "\n---\n\n".join(sections)


def render_batch_launch_plans_markdown(plans: list[LaunchPlan]) -> str:
    sections = [f"# Xiaoping Batch Launch Plans ({len(plans)} platforms)\n"]
    for plan in plans:
        sections.append(render_launch_plan_markdown(plan))
    return "\n---\n\n".join(sections)


def render_batch_reproduction_plans_markdown(plans: list[ReproductionPlan]) -> str:
    sections = [f"# Xiaoping Batch Reproduction Plans ({len(plans)} platforms)\n"]
    for plan in plans:
        sections.append(render_reproduction_plan_markdown(plan))
    return "\n---\n\n".join(sections)


def emit_output(content: str, output: str | None) -> None:
    if output is None:
        print(content)
        return
    path = Path(output)
    if not path.parent.exists():
        raise FileNotFoundError(f"Output directory does not exist: {path.parent}")
    path.write_text(content, encoding="utf-8")
    print(f"wrote {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the xiaoping self-media profit agent locally.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="List covered platforms.")
    inventory.add_argument("--region", choices=("cn", "global", "both"), default="both")
    inventory.add_argument("--json", action="store_true", help="Print JSON instead of a table.")

    run = subparsers.add_parser("run", help="Generate internal platform work items.")
    run.add_argument("--topic", required=True)
    run.add_argument("--audience", default="小商家/内容创业者")
    run.add_argument("--offer", choices=tuple(OFFER_TAGS.keys()), default="digital_product")
    run.add_argument("--region", choices=("cn", "global", "both"), default="both")
    run.add_argument("--max-platforms", type=int, default=6)
    run.add_argument("--account-mode", choices=("internal", "owned"), default="internal")
    run.add_argument("--format", choices=("markdown", "json"), default="markdown")
    run.add_argument("--output", help="Optional local output path. Parent directory must already exist.")
    run.add_argument("--evidence-file", help="Optional JSON evidence file path.")

    package = subparsers.add_parser("package", help="Generate one internal platform content package.")
    package.add_argument("--topic", required=True)
    package.add_argument("--audience", default="小商家/内容创业者")
    package.add_argument("--offer", choices=tuple(OFFER_TAGS.keys()), default="digital_product")
    package.add_argument("--region", choices=("cn", "global", "both"), default="both")
    package.add_argument("--platform", choices=tuple(platform.key for platform in PLATFORMS))
    package.add_argument("--account-mode", choices=("internal", "owned"), default="internal")
    package.add_argument("--format", choices=("markdown", "json"), default="markdown")
    package.add_argument("--output", help="Optional local output path. Parent directory must already exist.")
    package.add_argument("--top-n", type=int, help="Generate packages for top N ranked platforms.")
    package.add_argument("--evidence-file", help="Optional JSON evidence file path.")

    launch = subparsers.add_parser("launch-plan", help="Generate a self-created account launch plan.")
    launch.add_argument("--topic", required=True)
    launch.add_argument("--audience", default="小商家/内容创业者")
    launch.add_argument("--offer", choices=tuple(OFFER_TAGS.keys()), default="digital_product")
    launch.add_argument("--region", choices=("cn", "global", "both"), default="both")
    launch.add_argument("--platform", choices=tuple(platform.key for platform in PLATFORMS))
    launch.add_argument("--account-mode", choices=("internal", "owned"), default="owned")
    launch.add_argument("--format", choices=("markdown", "json"), default="markdown")
    launch.add_argument("--output", help="Optional local output path. Parent directory must already exist.")
    launch.add_argument("--top-n", type=int, help="Generate launch plans for top N ranked platforms.")
    launch.add_argument("--evidence-file", help="Optional JSON evidence file path.")

    reproduction = subparsers.add_parser("reproduction-plan", help="Generate a safe child-node reward plan.")
    reproduction.add_argument("--topic", required=True)
    reproduction.add_argument("--audience", default="小商家/内容创业者")
    reproduction.add_argument("--offer", choices=tuple(OFFER_TAGS.keys()), default="digital_product")
    reproduction.add_argument("--region", choices=("cn", "global", "both"), default="both")
    reproduction.add_argument("--platform", choices=tuple(platform.key for platform in PLATFORMS))
    reproduction.add_argument("--account-mode", choices=("internal", "owned"), default="owned")
    reproduction.add_argument("--asset-cny", type=float, required=True)
    reproduction.add_argument("--reward-threshold-cny", type=float, default=1000.0)
    reproduction.add_argument("--format", choices=("markdown", "json"), default="markdown")
    reproduction.add_argument("--output", help="Optional local output path. Parent directory must already exist.")
    reproduction.add_argument("--top-n", type=int, help="Generate reproduction plans for top N ranked platforms.")
    reproduction.add_argument("--evidence-file", help="Optional JSON evidence file path.")

    subparsers.add_parser("selftest", help="Run deterministic local checks.")
    return parser.parse_args()


def command_inventory(args: argparse.Namespace) -> int:
    platforms = list(platform_scope(args.region))
    if args.json:
        print(json.dumps([asdict(platform) for platform in platforms], ensure_ascii=False, indent=2))
        return 0
    for platform in platforms:
        surfaces = ", ".join(platform.surfaces)
        paths = " / ".join(platform.monetization_paths)
        print(f"{platform.key}\t{platform.name}\t{platform.region}\t{surfaces}\t{paths}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    agent_input = AgentInput(
        topic=args.topic,
        audience=args.audience,
        offer=args.offer,
        region=args.region,
        max_platforms=max(1, min(args.max_platforms, len(PLATFORMS))),
        account_mode=args.account_mode,
    )
    evidence = load_evidence(args.evidence_file)
    report = build_report(agent_input, evidence or None)
    if args.format == "json":
        emit_output(json.dumps(report, ensure_ascii=False, indent=2), args.output)
    else:
        emit_output(render_markdown(report), args.output)
    return 0


def command_package(args: argparse.Namespace) -> int:
    agent_input = AgentInput(
        topic=args.topic,
        audience=args.audience,
        offer=args.offer,
        region=args.region,
        max_platforms=len(PLATFORMS),
        account_mode=args.account_mode,
    )
    evidence = load_evidence(args.evidence_file) or None

    if args.top_n is not None:
        top_n = max(1, min(args.top_n, len(PLATFORMS)))
        full_input = AgentInput(
            topic=args.topic,
            audience=args.audience,
            offer=args.offer,
            region=args.region,
            max_platforms=top_n,
            account_mode=args.account_mode,
        )
        items = build_work_items(full_input, evidence)
        packages = [build_content_package(full_input, item.platform_key, evidence) for item in items]
        if args.format == "json":
            emit_output(json.dumps([asdict(pkg) for pkg in packages], ensure_ascii=False, indent=2), args.output)
        else:
            emit_output(render_batch_packages_markdown(packages), args.output)
        return 0

    package = build_content_package(agent_input, args.platform, evidence)
    if args.format == "json":
        emit_output(json.dumps(asdict(package), ensure_ascii=False, indent=2), args.output)
    else:
        emit_output(render_package_markdown(package), args.output)
    return 0


def command_launch_plan(args: argparse.Namespace) -> int:
    agent_input = AgentInput(
        topic=args.topic,
        audience=args.audience,
        offer=args.offer,
        region=args.region,
        max_platforms=len(PLATFORMS),
        account_mode=args.account_mode,
    )
    evidence = load_evidence(args.evidence_file) or None

    if args.top_n is not None:
        top_n = max(1, min(args.top_n, len(PLATFORMS)))
        full_input = AgentInput(
            topic=args.topic,
            audience=args.audience,
            offer=args.offer,
            region=args.region,
            max_platforms=top_n,
            account_mode=args.account_mode,
        )
        items = build_work_items(full_input, evidence)
        plans = [build_launch_plan(full_input, item.platform_key, evidence) for item in items]
        if args.format == "json":
            emit_output(json.dumps([asdict(plan) for plan in plans], ensure_ascii=False, indent=2), args.output)
        else:
            emit_output(render_batch_launch_plans_markdown(plans), args.output)
        return 0

    plan = build_launch_plan(agent_input, args.platform, evidence)
    if args.format == "json":
        emit_output(json.dumps(asdict(plan), ensure_ascii=False, indent=2), args.output)
    else:
        emit_output(render_launch_plan_markdown(plan), args.output)
    return 0


def command_reproduction_plan(args: argparse.Namespace) -> int:
    if args.asset_cny < 0:
        raise ValueError("--asset-cny must be >= 0")
    if args.reward_threshold_cny <= 0:
        raise ValueError("--reward-threshold-cny must be > 0")
    agent_input = AgentInput(
        topic=args.topic,
        audience=args.audience,
        offer=args.offer,
        region=args.region,
        max_platforms=len(PLATFORMS),
        account_mode=args.account_mode,
    )
    evidence = load_evidence(args.evidence_file) or None

    if args.top_n is not None:
        top_n = max(1, min(args.top_n, len(PLATFORMS)))
        full_input = AgentInput(
            topic=args.topic,
            audience=args.audience,
            offer=args.offer,
            region=args.region,
            max_platforms=top_n,
            account_mode=args.account_mode,
        )
        items = build_work_items(full_input, evidence)
        plans = [
            build_reproduction_plan(
                agent_input=full_input,
                platform_key=item.platform_key,
                asset_cny=args.asset_cny,
                reward_threshold_cny=args.reward_threshold_cny,
                evidence=evidence,
            )
            for item in items
        ]
        if args.format == "json":
            emit_output(json.dumps([asdict(plan) for plan in plans], ensure_ascii=False, indent=2), args.output)
        else:
            emit_output(render_batch_reproduction_plans_markdown(plans), args.output)
        return 0

    plan = build_reproduction_plan(
        agent_input=agent_input,
        platform_key=args.platform,
        asset_cny=args.asset_cny,
        reward_threshold_cny=args.reward_threshold_cny,
        evidence=evidence,
    )
    if args.format == "json":
        emit_output(json.dumps(asdict(plan), ensure_ascii=False, indent=2), args.output)
    else:
        emit_output(render_reproduction_plan_markdown(plan), args.output)
    return 0


def command_selftest() -> int:
    assert len(PLATFORMS) >= 12
    keys = [platform.key for platform in PLATFORMS]
    assert len(keys) == len(set(keys))
    sample = AgentInput(
        topic="AI 自动化提示词包",
        audience="小商家老板",
        offer="digital_product",
        region="both",
        max_platforms=5,
        account_mode="owned",
    )
    report = build_report(sample)
    assert report["external_action_allowed"] is False
    assert report["owned_account_publishing_allowed"] is True
    assert len(report["work_items"]) == 5
    assert all(item["required_gates"] for item in report["work_items"])
    package = build_content_package(sample, platform_key="youtube_shorts")
    assert package.platform_key == "youtube_shorts"
    assert package.titles
    assert package.body_steps
    assert package.gate_checklist
    assert package.launch_checklist
    assert "Account mode" in render_package_markdown(package)
    plan = build_launch_plan(sample, platform_key="youtube_shorts")
    assert plan.owned_account_path_allowed is True
    assert plan.publish_steps
    assert plan.stop_conditions
    locked = build_reproduction_plan(sample, platform_key="youtube_shorts", asset_cny=999.0, reward_threshold_cny=1000.0)
    assert locked.reward_unlocked is False
    unlocked = build_reproduction_plan(sample, platform_key="youtube_shorts", asset_cny=1000.0, reward_threshold_cny=1000.0)
    assert unlocked.reward_unlocked is True
    assert "不得按拉人数量" in " ".join(unlocked.prohibited_downline_rules)
    assert "Reward unlocked" in render_reproduction_plan_markdown(unlocked)

    batch_input = AgentInput(
        topic="AI 自动化提示词包",
        audience="小商家老板",
        offer="digital_product",
        region="both",
        max_platforms=3,
        account_mode="owned",
    )
    batch_items = build_work_items(batch_input)
    assert len(batch_items) == 3
    batch_packages = [build_content_package(batch_input, item.platform_key) for item in batch_items]
    assert len(batch_packages) == 3
    assert all(pkg.titles for pkg in batch_packages)
    batch_md = render_batch_packages_markdown(batch_packages)
    assert "Batch Content Packages" in batch_md
    batch_plans = [build_launch_plan(batch_input, item.platform_key) for item in batch_items]
    assert len(batch_plans) == 3
    batch_plans_md = render_batch_launch_plans_markdown(batch_plans)
    assert "Batch Launch Plans" in batch_plans_md
    batch_repro = [
        build_reproduction_plan(batch_input, item.platform_key, 1000.0, 1000.0)
        for item in batch_items
    ]
    assert len(batch_repro) == 3
    assert all(p.reward_unlocked for p in batch_repro)
    batch_repro_md = render_batch_reproduction_plans_markdown(batch_repro)
    assert "Batch Reproduction Plans" in batch_repro_md

    evvidence = load_evidence(None)
    assert evvidence == {}
    pkg_with_ev = build_content_package(sample, platform_key="youtube_shorts", evidence={})
    assert pkg_with_ev.evidence_checklist
    plan_with_ev = build_launch_plan(sample, platform_key="youtube_shorts", evidence={})
    assert plan_with_ev.stop_conditions

    print("selftest ok")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "inventory":
        return command_inventory(args)
    if args.command == "run":
        return command_run(args)
    if args.command == "package":
        return command_package(args)
    if args.command == "launch-plan":
        return command_launch_plan(args)
    if args.command == "reproduction-plan":
        return command_reproduction_plan(args)
    if args.command == "selftest":
        return command_selftest()
    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
