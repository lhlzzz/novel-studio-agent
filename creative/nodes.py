"""Execute one workflow node. Generation goes through the provider resolver."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from creative.errors import BudgetExceeded, UnsupportedCapability
from creative.judge import JUDGES, rank_assets, RegenerationStrategy, TechnicalQA
from creative.prompts import render_scene_prompt
from creative.schemas import (
    CameraPlan,
    CreativeTask,
    CreativeWorkflow,
    GenerationUsage,
    MediaAsset,
    MotionPlan,
    PromptAsset,
    Shot,
    Storyboard,
    to_plain,
    utcnow,
)

GENERATE_TYPES = {
    "image_generate": "generate_image",
    "image_edit": "edit_image",
    "video_generate": "generate_video",
    "video_extend": "extend_video",
    "video_edit": "edit_video",
}

NODE_COST = {
    "image_generate": 1.0,
    "image_edit": 1.0,
    "image_upscale": 0.5,
    "video_generate": 8.0,
    "video_extend": 6.0,
    "video_edit": 4.0,
}


def estimate_workflow_cost(workflow: CreativeWorkflow, inputs: dict[str, Any]) -> float:
    variants = int(inputs.get("variant_count") or workflow.quality_policy.get("variants") or 1)
    total = 0.0
    for node in workflow.nodes:
        total += NODE_COST.get(node.type, 0.0) * (variants if node.type in GENERATE_TYPES else 1)
    return total


def gather_inputs(node, workflow: CreativeWorkflow, context: dict[str, Any], run_inputs: dict[str, Any]) -> dict[str, Any]:
    data = {**dict(node.config or {}), **dict(node.inputs or {})}
    inbound = [edge for edge in workflow.edges if edge.target_node == node.node_id]
    if not inbound:
        data.update(run_inputs)
        data["output"] = run_inputs.get("brief") or run_inputs
        return data
    for edge in inbound:
        source = context.get(edge.source_node) or {}
        value = source.get(edge.source_output)
        if value is None:
            value = source.get("asset") if edge.source_output == "output" else source.get("output")
        data[edge.target_input] = value
    for key in ("brief", "aspect_ratio", "duration_seconds", "face_visible", "character_id", "variant_count", "commerce_intent", "camera", "motion", "style"):
        data.setdefault(key, run_inputs.get(key))
    return data


def _as_asset(value, store):
    if isinstance(value, MediaAsset) or value is None:
        return value
    if isinstance(value, dict) and (value.get("asset_id") or value.get("sha256")):
        return store.assets.get(value.get("asset_id")) or store.assets.get(value.get("sha256"))
    if isinstance(value, list):
        return [_as_asset(item, store) for item in value]
    return value


def execute_node(node, *, workflow, run, context, store, resolver) -> dict[str, Any]:
    data = gather_inputs(node, workflow, context, run.inputs)
    for key in ("asset", "output", "reference", "clip"):
        if key in data:
            data[key] = _as_asset(data[key], store)
    if node.type in {"input", "text", "reference"}:
        return {"output": data.get("output", run.inputs), **{k: v for k, v in data.items() if k != "output"}, "brief": data.get("brief") or run.inputs.get("brief")}
    if node.type == "character":
        character = None
        character_id = data.get("character_id") or run.inputs.get("character_id")
        if character_id:
            character = store.assets.get_character(str(character_id))
        return {
            "output": character,
            "character": character,
            "character_id": character_id,
            "references": list(character.reference_assets) if character else [],
        }
    if node.type == "prompt":
        prompt = render_scene_prompt({**run.inputs, **data, "brief": data.get("brief") or run.inputs.get("brief")})
        asset = PromptAsset(
            prompt_id=uuid4().hex,
            prompt=prompt,
            workflow_version=workflow.version,
            parameters={"aspect_ratio": data.get("aspect_ratio"), "duration_seconds": data.get("duration_seconds")},
        )
        store.save_prompt(asset)
        return {"output": prompt, "prompt": prompt, "prompt_asset": asset}
    if node.type == "storyboard":
        brief = str(data.get("brief") or run.inputs.get("brief") or "")
        shot = Shot(shot_id="shot-1", duration=float(run.inputs.get("duration_seconds") or 15), scene=brief, prompt=brief)
        board = Storyboard(storyboard_id=f"{run.run_id}:board", shots=(shot,))
        return {"output": brief, "storyboard": board}
    if node.type == "motion_annotation":
        plan = MotionPlan(
            camera=CameraPlan(movement=str(run.inputs.get("camera") or "static")),
            character_motion=str(run.inputs.get("motion") or ""),
            instructions=str(data.get("instructions") or run.inputs.get("brief") or ""),
        )
        return {"output": plan, "motion": plan}
    if node.type in GENERATE_TYPES:
        return _generate(node, workflow=workflow, run=run, data=data, store=store, resolver=resolver)
    if node.type == "judge":
        return _judge(node, run=run, data=data, context=context)
    if node.type == "render":
        clip = data.get("clip") or data.get("asset") or data.get("output")
        if isinstance(clip, list):
            clip = clip[0] if clip else None
        clip = _as_asset(clip, store)
        if not isinstance(clip, MediaAsset):
            return {"output": clip}
        from dataclasses import replace
        final = replace(clip, type="final" if clip.type == "video" else clip.type, metadata={**dict(clip.metadata or {}), "rendered_from": clip.asset_id, "workflow_id": workflow.workflow_id})
        store.assets.put(final)
        return {"output": final, "asset": final}
    if node.type == "output":
        asset = data.get("asset") or data.get("output")
        return {"output": asset, "asset": asset}
    if node.type in {"image_analyze", "image_crop", "image_split", "image_upscale", "image_annotate", "multi_angle", "audio", "subtitle"}:
        asset = data.get("asset") or data.get("output")
        if node.provider:
            raise UnsupportedCapability(node.type, provider=node.provider)
        return {"output": asset, "asset": asset, "passthrough": True}
    raise UnsupportedCapability(node.type, provider=node.provider or "workflow")


def _generate(node, *, workflow, run, data, store, resolver) -> dict[str, Any]:
    kind = GENERATE_TYPES[node.type]
    variants = int(data.get("variant_count") or workflow.quality_policy.get("variants") or 1)
    variants = max(1, min(variants, int(workflow.quality_policy.get("max_variants") or variants)))
    provider, resolved_name = resolver.resolve(node.provider or "lechuang")
    assets: list[MediaAsset] = []
    pending: list[CreativeTask] = []
    prompt = data.get("prompt") or data.get("output") or data.get("brief")
    reference = data.get("reference")
    if isinstance(reference, MediaAsset):
        reference = reference.path
    elif isinstance(reference, list) and reference:
        first = reference[0]
        reference = first.path if isinstance(first, MediaAsset) else first
    for index in range(variants):
        payload = {
            "prompt": prompt,
            "negative_prompt": data.get("negative_prompt") or "",
            "reference": reference,
            "character_id": data.get("character_id") or run.inputs.get("character_id"),
            "aspect_ratio": data.get("aspect_ratio") or "9:16",
            "duration_seconds": data.get("duration_seconds") or 15,
            "width": 720 if str(data.get("aspect_ratio") or "9:16") == "9:16" else 1280,
            "height": 1280 if str(data.get("aspect_ratio") or "9:16") == "9:16" else 720,
            "run_id": run.run_id,
            "workflow_id": workflow.workflow_id,
            "workflow_version": workflow.version,
            "variant_index": index,
            "mode": data.get("mode"),
            "camera": data.get("camera"),
            "motion": data.get("motion"),
        }
        estimate = float(getattr(provider, "estimate", lambda k, p: NODE_COST.get(node.type, 1.0))(kind, payload))
        if run.budget is not None and (run.actual_cost + estimate) > float(run.budget):
            raise BudgetExceeded(run.actual_cost + estimate, float(run.budget))
        handle = provider.create_task(kind, payload)
        task = CreativeTask(
            task_id=f"{run.run_id}:{node.node_id}:{index}",
            run_id=run.run_id,
            node_id=node.node_id,
            provider=resolved_name,
            provider_task_id=handle.provider_task_id,
            status=handle.status,
            kind=kind,
            payload=payload,
            result=dict(handle.result or {}),
            started_at=utcnow(),
        )
        store.save_task(task)
        run.task_ids.append(task.task_id)
        if handle.status in {"queued", "running"}:
            pending.append(task)
            continue
        if handle.status != "succeeded":
            task.error = handle.error or handle.status
            store.save_task(task)
            raise RuntimeError(task.error)
        asset = handle.result.get("asset")
        credits = float(handle.result.get("credits_actual") or estimate)
        run.actual_cost += credits
        store.save_usage(GenerationUsage(
            usage_id=task.task_id,
            provider=resolved_name,
            model=str(node.model or resolved_name),
            task=kind,
            input={"prompt": prompt, "parameters": payload, "references": [reference] if reference else [], "workflow_version": workflow.version},
            output={"asset_id": getattr(asset, "asset_id", None)},
            credits_estimated=estimate,
            credits_actual=credits,
            status=handle.status,
            timestamp=utcnow(),
            run_id=run.run_id,
            node_id=node.node_id,
        ))
        if isinstance(asset, MediaAsset):
            store.assets.put(asset)
            run.asset_ids.append(asset.asset_id)
            assets.append(asset)
    if pending:
        return {"_pending": pending, "assets": assets, "output": assets[0] if assets else None}
    ranked = assets
    return {"output": ranked[0], "asset": ranked[0], "variants": ranked, "assets": ranked}


def _judge(node, *, run, data, context) -> dict[str, Any]:
    judge_name = str(data.get("judge") or node.config.get("judge") or "image")
    judge = JUDGES[judge_name]
    asset = data.get("asset") or data.get("output")
    assets = asset if isinstance(asset, list) else ([asset] if isinstance(asset, MediaAsset) else [])
    if judge_name in {"consistency", "continuity"}:
        collected = []
        for value in context.values():
            item = value.get("asset") if isinstance(value, dict) else None
            if isinstance(item, MediaAsset):
                collected.append(item)
            for extra in (value.get("assets") or []) if isinstance(value, dict) else []:
                if isinstance(extra, MediaAsset):
                    collected.append(extra)
        result = judge.judge(collected or assets, context=run.inputs)
        chosen = (collected or assets or [None])[0]
        run.judge_results.append(to_plain(result))
        return {"output": chosen, "asset": chosen, "judge": result, "decision": result.decision}
    if not assets:
        result = judge.judge(None, context=run.inputs)
        run.judge_results.append(to_plain(result))
        return {"output": None, "judge": result, "decision": result.decision}
    pairs = [(item, judge.judge(item, context=run.inputs)) for item in assets]
    ranked = rank_assets(pairs)
    best_asset, best = ranked[0]
    run.judge_results.append(to_plain(best))
    return {"output": best_asset, "asset": best_asset, "judge": best, "decision": best.decision, "ranked": ranked}


def quality_gate(run, assets: list[MediaAsset]) -> dict[str, str]:
    qa = TechnicalQA()
    visual = "pass"
    identity = "pass"
    technical = "pass"
    reasons = []
    for result in run.judge_results:
        if result.get("decision") == "FAIL":
            visual = "fail"
            reasons.extend(result.get("reasons") or [])
        if result.get("judge_type") in {"consistency", "continuity"} and result.get("decision") == "FAIL":
            identity = "fail"
    for asset in assets:
        inspect = qa.inspect_video(asset) if asset.type in {"video", "final"} else qa.inspect_image(asset)
        if inspect["decision"] != "pass":
            technical = "fail"
            reasons.extend(inspect["failures"])
    return {
        "visual_quality": visual,
        "identity_quality": identity,
        "technical_quality": technical,
        "reasons": reasons,
    }
