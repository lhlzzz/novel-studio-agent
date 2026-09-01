"""Execute one workflow node. Generation goes through the provider resolver."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from creative.errors import BudgetExceeded, JudgeBlocked, ProviderBlocked, TechnicalMediaError, UnsupportedCapability
from creative.idempotency import IdempotencyKey
from creative.judges import ContentPolicyGate, TechnicalQA, bind_judges, rank_assets
from creative.prompts import render_scene_prompt
from creative.schemas import (
    CROP_ASPECTS,
    NODE_REGISTRY,
    NODE_STATUS_BLOCKED,
    NODES,
    canonicalize_node_type,
    CameraPlan,
    CreativeTask,
    CreativeWorkflow,
    GenerationUsage,
    MediaAsset,
    MotionPlan,
    PromptAsset,
    ProviderQuote,
    Shot,
    Storyboard,
    map_task_status,
    to_plain,
    utcnow,
)

GENERATE_TYPES = {
    "image_generate": "generate_image",
    "image.generate": "generate_image",
    "image_edit": "edit_image",
    "image.transform": "edit_image",
    "video_generate": "generate_video",
    "video.generate": "generate_video",
    "video.from_image": "generate_video",
    "video_extend": "extend_video",
    "video_edit": "edit_video",
    "multi_angle": "generate_image",
}

# Mock cost only. Production quotes come from provider.estimate().
MOCK_NODE_COST = {
    "image_generate": 1.0,
    "image.generate": 1.0,
    "image_edit": 1.0,
    "image.transform": 1.0,
    "image_resize": 0.1,
    "multi_angle": 1.0,
    "video_generate": 8.0,
    "video.generate": 8.0,
    "video.from_image": 8.0,
    "video_extend": 6.0,
    "video_edit": 4.0,
}

KIND_CAPABILITY = {
    "generate_image": "text_to_image",
    "edit_image": "image_to_image",
    "generate_video": "text_to_video",
    "extend_video": "video_extend",
    "edit_video": "video_edit",
}

ASPECT_PAIRS = {
    "1:1": (1, 1),
    "4:5": (4, 5),
    "3:4": (3, 4),
    "16:9": (16, 9),
    "9:16": (9, 16),
}


def estimate_workflow_cost(workflow: CreativeWorkflow, inputs: dict[str, Any], *, resolver=None) -> float:
    variants = int(inputs.get("variant_count") or workflow.quality_policy.get("variants") or 1)
    total = 0.0
    for node in workflow.nodes:
        kind = GENERATE_TYPES.get(node.type)
        if kind and resolver is not None:
            try:
                provider, _ = resolver.resolve(node.provider or "lechuang")
                quote = quote_task(provider, kind, {"variant_count": variants, **inputs})
                total += float(quote.credits) * variants
                continue
            except Exception:
                pass
        total += MOCK_NODE_COST.get(node.type, 0.0) * (variants if node.type in GENERATE_TYPES else 1)
    return total


def quote_task(provider, kind: str, payload: dict[str, Any]) -> ProviderQuote:
    estimate = getattr(provider, "estimate", None)
    quote = getattr(provider, "quote", None)
    mock = str(getattr(provider, "name", "")) in {"mock", "mock-vision"}
    if callable(quote):
        result = quote(kind, payload)
        if isinstance(result, ProviderQuote):
            return result
        return ProviderQuote(credits=float(result), mock=mock, provider=getattr(provider, "name", ""))
    if callable(estimate):
        return ProviderQuote(credits=float(estimate(kind, payload)), mock=mock, provider=getattr(provider, "name", ""), parameters={"source": "estimate"})
    return ProviderQuote(credits=float(MOCK_NODE_COST.get(kind, 1.0)), mock=True, provider=getattr(provider, "name", ""), parameters={"source": "mock_cost_only"})


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
        return store.assets.get(value.get("asset_id")) or store.assets.get(value.get("sha256")) or store.get_asset(value.get("asset_id") or value.get("sha256"))
    if isinstance(value, list):
        return [_as_asset(item, store) for item in value]
    if isinstance(value, str) and store.assets.get(value):
        return store.assets.get(value)
    return value


def execute_node(node, *, workflow, run, context, store, resolver, judge_provider=None) -> dict[str, Any]:
    node_type = canonicalize_node_type(node.type)
    spec = NODES.get(node.type)
    if spec.get("status") == NODE_STATUS_BLOCKED:
        raise ProviderBlocked(node.type, spec.get("reason") or "node blocked")
    data = gather_inputs(node, workflow, context, run.inputs)
    for key in ("asset", "output", "reference", "clip"):
        if key in data:
            data[key] = _as_asset(data[key], store)
    if node_type in {"input", "text", "reference"}:
        return {"output": data.get("output", run.inputs), **{k: v for k, v in data.items() if k != "output"}, "brief": data.get("brief") or run.inputs.get("brief")}
    if node_type == "character":
        return _character(data, run, store)
    if node_type == "prompt":
        return _prompt(data, workflow, run, store)
    if node_type == "storyboard":
        return _storyboard(data, run)
    if node_type == "motion_annotation":
        return _motion_annotation(data, run, store)
    if node_type in GENERATE_TYPES:
        return _generate(node, workflow=workflow, run=run, data=data, store=store, resolver=resolver)
    if node_type == "judge":
        return _judge(node, run=run, data=data, context=context, store=store, judge_provider=judge_provider)
    if node_type == "render":
        return _render(data, workflow, run, store)
    if node_type == "output":
        asset = data.get("asset") or data.get("output")
        return {"output": asset, "asset": asset}
    if node_type == "image_crop":
        return _image_crop(data, run, store)
    if node_type == "image_split":
        return _image_split(data, run, store)
    if node_type == "image_resize":
        return _image_resize(data, run, store)
    if node_type == "image_annotate":
        return _image_annotate(data, run, store)
    if node_type == "subtitle":
        return _subtitle(data, run, store)
    if node_type == "image_analyze":
        return _image_analyze(data, run, judge_provider)
    if node_type == "audio":
        raise ProviderBlocked("audio", "no verified audio provider")
    if node_type == "image_upscale":
        raise ProviderBlocked("image_upscale", "super-resolution requires a verified provider capability")
    raise UnsupportedCapability(node_type, provider=node.provider or "workflow")


def _character(data, run, store) -> dict[str, Any]:
    character = None
    character_id = data.get("character_id") or run.inputs.get("character_id")
    if character_id:
        character = store.assets.get_character(str(character_id)) or store.get_character(str(character_id))
    references = []
    if character:
        for item in character.reference_assets:
            asset = store.assets.get(str(item)) or store.get_asset(str(item))
            if asset is not None:
                references.append(asset)
    return {
        "output": character,
        "character": character,
        "character_id": character_id,
        "references": references or list(character.reference_assets) if character else [],
    }


def _prompt(data, workflow, run, store) -> dict[str, Any]:
    payload = {**run.inputs, **data, "brief": data.get("brief") or run.inputs.get("brief")}
    if run.inputs.get("variation_seed") == "change_prompt" or run.inputs.get("regen_action") == "change_prompt":
        payload["brief"] = f"{payload.get('brief') or ''} regenerated variation, shift composition slightly.".strip()
    prompt = render_scene_prompt(payload)
    asset = PromptAsset(
        prompt_id=uuid4().hex,
        prompt=prompt,
        negative_prompt=str(data.get("negative_prompt") or ""),
        references=tuple(filter(None, [getattr(data.get("reference"), "asset_id", None)])),
        model=str(data.get("model") or run.inputs.get("model") or ""),
        provider=str(data.get("provider") or ""),
        workflow_id=workflow.workflow_id,
        workflow_version=workflow.version,
        parameters={"aspect_ratio": data.get("aspect_ratio"), "duration_seconds": data.get("duration_seconds"), "camera": data.get("camera")},
        family_id=str(data.get("prompt_family") or workflow.workflow_id),
    )
    store.save_prompt(asset)
    return {"output": prompt, "prompt": prompt, "prompt_asset": asset}


def _storyboard(data, run) -> dict[str, Any]:
    brief = str(data.get("script") or data.get("brief") or run.inputs.get("brief") or "")
    chunks = [item.strip() for item in re.split(r"[\n]+|[。．.！？!?；;]", brief) if item.strip()]
    if not chunks:
        chunks = ["shot"]
    duration = float(run.inputs.get("duration_seconds") or 15)
    each = duration / len(chunks)
    shots = []
    for index, scene in enumerate(chunks, start=1):
        shots.append(Shot(
            shot_id=f"shot-{index}",
            duration=each,
            scene=scene,
            prompt=scene,
            character_id=run.inputs.get("character_id"),
            camera=CameraPlan(movement=str(run.inputs.get("camera") or "static")),
            motion=MotionPlan(camera=CameraPlan(movement=str(run.inputs.get("camera") or "static")), character_motion=str(run.inputs.get("motion") or ""), instructions=scene),
            audio="",
        ))
    board = Storyboard(storyboard_id=f"{run.run_id}:board", shots=tuple(shots))
    return {"output": shots[0].prompt, "storyboard": board, "shots": list(shots)}


def _motion_annotation(data, run, store) -> dict[str, Any]:
    plan = MotionPlan(
        camera=CameraPlan(movement=str(run.inputs.get("camera") or "static")),
        character_motion=str(run.inputs.get("motion") or ""),
        paths=tuple(data.get("paths") or ()),
        labels=tuple(data.get("labels") or ("camera", "motion")),
        instructions=str(data.get("instructions") or run.inputs.get("brief") or ""),
    )
    source = data.get("asset") or data.get("reference") or data.get("output")
    source = _as_asset(source, store)
    annotated = None
    if isinstance(source, MediaAsset) and source.type in {"image", "reference", "final"}:
        annotated = _draw_overlay(source, store, run, label="motion", instruction=plan.instructions, arrow=True)
    return {"output": annotated or plan, "motion": plan, "asset": annotated, "reference": annotated}


def _generate(node, *, workflow, run, data, store, resolver) -> dict[str, Any]:
    kind = GENERATE_TYPES[canonicalize_node_type(node.type) if node.type not in GENERATE_TYPES else node.type]
    if canonicalize_node_type(node.type) in {"video_generate"} and (node.type == "video.from_image" or str(data.get("mode") or node.config.get("mode") or "") == "image_to_video"):
        capability = "image_to_video"
    else:
        capability = KIND_CAPABILITY.get(kind, kind)
    variants = int(data.get("variant_count") or workflow.quality_policy.get("variants") or 1)
    variants = max(1, min(variants, int(workflow.quality_policy.get("max_variants") or variants)))
    provider_name = str(run.inputs.get("provider_override") or node.provider or "lechuang")
    if run.inputs.get("regen_action") == "change_model":
        provider_name = str(run.inputs.get("model_override") or provider_name)
    provider, resolved_name = resolver.resolve(provider_name)
    _assert_capability(provider, capability, resolved_name, kind)
    assets: list[MediaAsset] = []
    pending: list[CreativeTask] = []
    prompt = data.get("prompt") or data.get("output") or data.get("brief")
    if run.inputs.get("regen_action") == "change_prompt":
        prompt = f"{prompt} [regenerated composition]"
    reference = data.get("reference")
    if run.inputs.get("regen_action") == "change_reference" and run.inputs.get("reference_override"):
        reference = _as_asset(run.inputs.get("reference_override"), store)
    if isinstance(reference, MediaAsset):
        reference_value = reference.path
    elif isinstance(reference, list) and reference:
        first = reference[0]
        reference_value = first.path if isinstance(first, MediaAsset) else first
    else:
        reference_value = reference
    camera = data.get("camera")
    if run.inputs.get("regen_action") == "change_camera":
        camera = run.inputs.get("camera") or "handheld"
    for index in range(variants):
        attempt = int(run.outputs.get("regen_attempt") or 0)
        execution_key = IdempotencyKey.provider(run.run_id, node.node_id, f"{index}:{attempt}")
        existing = store.get_task_by_execution_key(execution_key)
        if existing is not None:
            if existing.status in {"QUEUED", "RUNNING"}:
                pending.append(existing)
                continue
            if existing.status == "SUCCEEDED":
                restored = _asset_from_result(existing.result, store)
                if restored:
                    assets.append(restored)
                continue
            raise RuntimeError(existing.error or existing.status)
        payload = {
            "prompt": prompt,
            "negative_prompt": data.get("negative_prompt") or "",
            "reference": reference_value,
            "character_id": data.get("character_id") or run.inputs.get("character_id"),
            "aspect_ratio": data.get("aspect_ratio") or "9:16",
            "duration_seconds": data.get("duration_seconds") or 15,
            "width": 720 if str(data.get("aspect_ratio") or "9:16") == "9:16" else 1280,
            "height": 1280 if str(data.get("aspect_ratio") or "9:16") == "9:16" else 720,
            "run_id": run.run_id,
            "workflow_id": workflow.workflow_id,
            "workflow_version": workflow.version,
            "variant_index": index,
            "mode": data.get("mode") or ("multi_angle" if node.type == "multi_angle" else None),
            "camera": camera,
            "motion": data.get("motion"),
            "seed": run.inputs.get("seed") or (index + 1 if run.inputs.get("regen_action") == "change_variation" else index),
            "model": node.model or run.inputs.get("model"),
            "angle": data.get("angle") or ("three-quarter" if node.type == "multi_angle" else None),
        }
        quote = quote_task(provider, kind, payload)
        estimate = float(quote.credits)
        if run.budget is not None and (run.actual_cost + estimate) > float(run.budget):
            raise BudgetExceeded(run.actual_cost + estimate, float(run.budget))
        from datetime import datetime, timedelta, timezone
        timeout_at = (datetime.now(timezone.utc) + timedelta(seconds=int(data.get("timeout_seconds") or 180))).isoformat()
        create = getattr(provider, "create", None)
        if callable(create):
            handle = create(kind, payload, idempotency_key=execution_key)
        else:
            handle = provider.create_task(kind, {**payload, "idempotency_key": execution_key})
        task = CreativeTask(
            task_id=f"{run.run_id}:{node.node_id}:{index}:{attempt}",
            run_id=run.run_id,
            node_id=node.node_id,
            provider=resolved_name,
            provider_task_id=handle.provider_task_id,
            status=map_task_status(handle.status),
            kind=kind,
            payload=payload,
            result=dict(handle.result or {}),
            started_at=utcnow(),
            attempt=attempt,
            timeout_at=timeout_at,
            execution_key=execution_key,
        )
        store.save_task(task)
        store.record_event(run.run_id, "provider_submitted", {"task_id": task.task_id, "provider": resolved_name, "kind": kind})
        run.task_ids.append(task.task_id)
        if task.status in {"QUEUED", "RUNNING"}:
            pending.append(task)
            continue
        if task.status != "SUCCEEDED":
            task.error = handle.error or handle.status
            store.save_task(task)
            if handle.result.get("credits_actual") is not None:
                _record_usage(store, run, task, resolved_name, node, kind, prompt, payload, reference_value, estimate, float(handle.result.get("credits_actual") or 0), workflow)
            raise RuntimeError(task.error)
        asset = handle.result.get("asset")
        credits = float(handle.result.get("credits_actual") or estimate)
        run.actual_cost += credits
        _record_usage(store, run, task, resolved_name, node, kind, prompt, payload, reference_value, estimate, credits, workflow)
        if isinstance(asset, MediaAsset):
            stored = store.assets.put(asset)
            run.asset_ids.append(stored.asset_id)
            store.record_event(run.run_id, "asset_created", {"asset_id": stored.asset_id, "sha256": stored.sha256})
            assets.append(stored)
    if pending:
        return {"_pending": pending, "assets": assets, "output": assets[0] if assets else None}
    ranked = assets
    return {"output": ranked[0], "asset": ranked[0], "variants": ranked, "assets": ranked}


def _assert_capability(provider, capability: str, resolved_name: str, kind: str) -> None:
    verified = getattr(provider, "verified_capabilities", None)
    supported = set(getattr(provider, "supported", ()) or ())
    if callable(getattr(provider, "has_verified", None)):
        if not provider.has_verified(capability):
            raise ProviderBlocked(resolved_name, f"{capability} unverified")
        return
    if verified is not None:
        if capability not in set(verified) and kind not in set(verified):
            raise ProviderBlocked(resolved_name, f"{capability} unverified")
        return
    if supported and capability not in supported and kind not in supported and "generate_image" not in supported:
        raise ProviderBlocked(resolved_name, f"{capability} unverified")


def _record_usage(store, run, task, provider, node, kind, prompt, payload, reference, estimate, credits, workflow) -> None:
    store.save_usage(GenerationUsage(
        usage_id=task.task_id,
        provider=provider,
        model=str(node.model or payload.get("model") or provider),
        task=kind,
        input={"prompt": prompt, "parameters": payload, "references": [reference] if reference else [], "workflow_version": workflow.version, "workflow_id": workflow.workflow_id},
        output={"asset_id": getattr((task.result or {}).get("asset"), "asset_id", None) if isinstance((task.result or {}).get("asset"), MediaAsset) else ((task.result or {}).get("asset") or {}).get("asset_id") if isinstance((task.result or {}).get("asset"), dict) else None},
        credits_estimated=estimate,
        credits_actual=credits,
        status=task.status,
        timestamp=utcnow(),
        run_id=run.run_id,
        node_id=node.node_id,
        input_units=1.0,
        output_units=1.0 if task.status == "SUCCEEDED" else 0.0,
        duration_ms=0.0,
        estimated_cost=estimate,
        actual_cost=credits,
    ))


def _asset_from_result(result: dict[str, Any], store) -> MediaAsset | None:
    asset = (result or {}).get("asset")
    if isinstance(asset, MediaAsset):
        return store.assets.put(asset)
    if isinstance(asset, dict) and (asset.get("asset_id") or asset.get("sha256")):
        found = store.assets.get(asset.get("asset_id")) or store.assets.get(asset.get("sha256")) or store.get_asset(asset.get("asset_id") or asset.get("sha256"))
        return found
    return None


def _judge(node, *, run, data, context, store, judge_provider) -> dict[str, Any]:
    judge_name = str(data.get("judge") or node.config.get("judge") or "image")
    judges = bind_judges(judge_provider)
    if judge_name not in judges:
        raise UnsupportedCapability(judge_name, provider="judge")
    judge = judges[judge_name]
    asset = data.get("asset") or data.get("output")
    assets = asset if isinstance(asset, list) else ([asset] if isinstance(asset, MediaAsset) else [])
    character = None
    character_id = run.inputs.get("character_id")
    if character_id:
        character = store.assets.get_character(str(character_id))
    if judge_name in {"consistency", "continuity", "identity"}:
        collected = []
        for value in context.values():
            item = value.get("asset") if isinstance(value, dict) else None
            if isinstance(item, MediaAsset):
                collected.append(item)
            for extra in (value.get("assets") or []) if isinstance(value, dict) else []:
                if isinstance(extra, MediaAsset):
                    collected.append(extra)
        result = judge.judge(collected or assets, context=run.inputs, character=character)
        chosen = (collected or assets or [None])[0]
        payload = to_plain(result)
        run.judge_results.append(payload)
        store.save_judge_result(payload, run_id=run.run_id)
        store.record_event(run.run_id, "judge_completed", {"judge": judge_name, "decision": result.decision, "score": result.score})
        return {"output": chosen, "asset": chosen, "judge": result, "decision": result.decision}
    if not assets:
        result = judge.judge(None, context=run.inputs, character=character)
        payload = to_plain(result)
        run.judge_results.append(payload)
        store.save_judge_result(payload, run_id=run.run_id)
        return {"output": None, "judge": result, "decision": result.decision}
    pairs = [(item, judge.judge(item, context=run.inputs, character=character)) for item in assets]
    ranked = rank_assets(pairs)
    best_asset, best = ranked[0]
    payload = to_plain(best)
    run.judge_results.append(payload)
    store.save_judge_result(payload, run_id=run.run_id)
    store.record_event(run.run_id, "judge_completed", {"judge": judge_name, "decision": best.decision, "score": best.score, "asset_id": best_asset.asset_id if best_asset else None})
    run.selected_asset_id = best_asset.asset_id if best_asset else run.selected_asset_id
    run.selection_reason = f"{judge_name} top score"
    run.selection_score = best.score
    return {"output": best_asset, "asset": best_asset, "judge": best, "decision": best.decision, "ranked": ranked}


def _render(data, workflow, run, store) -> dict[str, Any]:
    clip = data.get("clip") or data.get("asset") or data.get("output")
    if isinstance(clip, list):
        clip = clip[0] if clip else None
    clip = _as_asset(clip, store)
    if not isinstance(clip, MediaAsset):
        raise TechnicalMediaError("render requires a MediaAsset")
    from creative.render import render_asset
    final = render_asset(
        clip,
        store=store,
        extra={"workflow_id": workflow.workflow_id, "workflow_version": workflow.version, "creative_run_id": run.run_id, "character_id": clip.character_id},
    )
    run.asset_ids.append(final.asset_id)
    store.record_event(run.run_id, "asset_created", {"asset_id": final.asset_id, "kind": "render"})
    return {"output": final, "asset": final}


def _require_image(data, store) -> MediaAsset:
    asset = _as_asset(data.get("asset") or data.get("output") or data.get("reference"), store)
    if not isinstance(asset, MediaAsset):
        raise TechnicalMediaError("image node requires a MediaAsset")
    return asset


def _image_crop(data, run, store) -> dict[str, Any]:
    from PIL import Image
    asset = _require_image(data, store)
    ratio = str(data.get("aspect_ratio") or data.get("ratio") or "1:1")
    if ratio not in CROP_ASPECTS:
        raise TechnicalMediaError(f"unsupported crop ratio: {ratio}")
    with Image.open(asset.path) as image:
        image = image.convert("RGB")
        width, height = image.size
        if ratio == "custom":
            box = tuple(data.get("box") or (0, 0, width, height))
        else:
            aw, ah = ASPECT_PAIRS[ratio]
            target = aw / ah
            current = width / max(height, 1)
            if current > target:
                new_w = int(height * target)
                left = (width - new_w) // 2
                box = (left, 0, left + new_w, height)
            else:
                new_h = int(width / target)
                top = (height - new_h) // 2
                box = (0, top, width, top + new_h)
        cropped = image.crop(box)
        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        saved = store.assets.save_generated(
            buf.getvalue(),
            asset_type="image",
            suffix=".png",
            mime_type="image/png",
            width=cropped.size[0],
            height=cropped.size[1],
            creative_run_id=run.run_id,
            metadata={"op": "crop", "ratio": ratio, "source": asset.asset_id},
        )
    return {"output": saved, "asset": saved}


def _image_split(data, run, store) -> dict[str, Any]:
    from PIL import Image
    asset = _require_image(data, store)
    rows = max(1, int(data.get("rows") or 1))
    columns = max(1, int(data.get("columns") or 2))
    pieces = []
    with Image.open(asset.path) as image:
        image = image.convert("RGB")
        width, height = image.size
        tile_w = width // columns
        tile_h = height // rows
        for row in range(rows):
            for col in range(columns):
                box = (col * tile_w, row * tile_h, width if col == columns - 1 else (col + 1) * tile_w, height if row == rows - 1 else (row + 1) * tile_h)
                tile = image.crop(box)
                buf = io.BytesIO()
                tile.save(buf, format="PNG")
                pieces.append(store.assets.save_generated(
                    buf.getvalue(),
                    asset_type="image",
                    suffix=".png",
                    mime_type="image/png",
                    width=tile.size[0],
                    height=tile.size[1],
                    creative_run_id=run.run_id,
                    metadata={"op": "split", "row": row, "column": col, "source": asset.asset_id},
                ))
    return {"output": pieces[0], "asset": pieces[0], "assets": pieces, "tiles": pieces}


def _image_resize(data, run, store) -> dict[str, Any]:
    from PIL import Image
    asset = _require_image(data, store)
    width = int(data.get("width") or asset.width or 720)
    height = int(data.get("height") or asset.height or 1280)
    with Image.open(asset.path) as image:
        resized = image.convert("RGB").resize((width, height))
        buf = io.BytesIO()
        resized.save(buf, format="PNG")
        saved = store.assets.save_generated(
            buf.getvalue(),
            asset_type="image",
            suffix=".png",
            mime_type="image/png",
            width=width,
            height=height,
            creative_run_id=run.run_id,
            metadata={"op": "resize", "source": asset.asset_id},
        )
    return {"output": saved, "asset": saved}


def _image_annotate(data, run, store) -> dict[str, Any]:
    asset = _require_image(data, store)
    saved = _draw_overlay(
        asset,
        store,
        run,
        label=str(data.get("label") or "note"),
        instruction=str(data.get("instruction") or data.get("brief") or ""),
        arrow=bool(data.get("arrow", True)),
        path_points=data.get("path"),
    )
    return {"output": saved, "asset": saved}


def _draw_overlay(asset: MediaAsset, store, run, *, label: str, instruction: str, arrow: bool = True, path_points=None) -> MediaAsset:
    from PIL import Image, ImageDraw
    with Image.open(asset.path) as image:
        canvas = image.convert("RGB").copy()
        draw = ImageDraw.Draw(canvas)
        w, h = canvas.size
        points = path_points or [(int(w * 0.2), int(h * 0.8)), (int(w * 0.8), int(h * 0.2))]
        pts = [(int(item[0]), int(item[1])) for item in points]
        if len(pts) >= 2:
            draw.line(pts, fill=(255, 214, 0), width=max(4, w // 180))
            if arrow:
                end = pts[-1]
                draw.polygon([end, (end[0] - 18, end[1] + 10), (end[0] - 10, end[1] + 18)], fill=(255, 214, 0))
        draw.rectangle((12, 12, min(w - 12, 12 + 8 * max(len(label), 8)), 48), fill=(0, 0, 0))
        draw.text((18, 18), label[:48], fill=(255, 255, 255))
        if instruction:
            draw.text((18, h - 36), instruction[:60], fill=(255, 255, 255))
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return store.assets.save_generated(
            buf.getvalue(),
            asset_type="image",
            suffix=".png",
            mime_type="image/png",
            width=w,
            height=h,
            creative_run_id=run.run_id,
            metadata={"op": "annotate", "source": asset.asset_id, "label": label, "instruction": instruction},
        )


def _subtitle(data, run, store) -> dict[str, Any]:
    from creative.render.ffmpeg import write_ass, write_srt
    text = str(data.get("text") or data.get("instruction") or data.get("brief") or run.inputs.get("brief") or "")
    duration = float(data.get("duration") or run.inputs.get("duration_seconds") or 3)
    fmt = str(data.get("format") or "srt")
    root = Path(store.assets.root)
    tmp = root / "subtitles"
    tmp.mkdir(parents=True, exist_ok=True)
    if fmt == "ass":
        path = write_ass(tmp / f"{run.run_id}.ass", text, duration)
        mime = "text/x-ssa"
    else:
        path = write_srt(tmp / f"{run.run_id}.srt", text, duration)
        mime = "application/x-subrip"
    saved = store.assets.save_generated(
        path.read_bytes(),
        asset_type="subtitle",
        suffix=path.suffix,
        mime_type=mime,
        creative_run_id=run.run_id,
        metadata={"format": fmt, "text": text},
    )
    clip = _as_asset(data.get("asset") or data.get("clip") or data.get("output"), store)
    burned = None
    if fmt == "burn-in" and isinstance(clip, MediaAsset):
        from creative.render import RenderOp, render_asset
        burned = render_asset(clip, store=store, ops=[RenderOp("subtitle", {"text": text, "duration": duration, "format": "burn-in"})], extra={"creative_run_id": run.run_id})
    return {"output": burned or saved, "asset": burned or saved, "subtitle": saved}


def _image_analyze(data, run, judge_provider) -> dict[str, Any]:
    if judge_provider is None:
        raise JudgeBlocked("vision provider unavailable")
    asset = data.get("asset") or data.get("output")
    if not isinstance(asset, MediaAsset):
        raise JudgeBlocked("image_analyze requires a MediaAsset")
    result = judge_provider.judge_image(asset, brief=run.inputs)
    return {"output": asset, "asset": asset, "analysis": to_plain(result), "judge": result}


def quality_gate(run, assets: list[MediaAsset]) -> dict[str, Any]:
    qa = TechnicalQA()
    policy_gate = ContentPolicyGate().evaluate(run.inputs, asset=(assets[-1] if assets else None))
    visual = "blocked"
    identity = "pass"
    technical = "pass"
    policy = "pass" if policy_gate.decision == "PASS" else "fail"
    platform = "pass"
    reasons = list(policy_gate.reasons)
    scores = {}
    visual_seen = False
    for result in run.judge_results:
        if result.get("judge_type") in {"image", "video"}:
            visual_seen = True
            if result.get("decision") == "PASS":
                visual = "pass"
            elif result.get("decision") == "FAIL":
                visual = "fail"
                reasons.extend(result.get("reasons") or [])
            if result.get("score") is not None:
                scores["visual_score"] = float(result["score"])
        if result.get("judge_type") in {"consistency", "continuity", "identity"} and result.get("decision") == "FAIL":
            identity = "fail"
            reasons.extend(result.get("reasons") or [])
        if result.get("judge_type") == "content_fit":
            scores["content_score"] = float(result.get("score") or 0)
            if result.get("decision") == "FAIL":
                reasons.extend(result.get("reasons") or [])
        if result.get("judge_type") == "policy" and result.get("decision") in {"FAIL", "BLOCK"}:
            policy = "fail"
            reasons.extend(result.get("reasons") or [])
    if not visual_seen:
        visual = "blocked"
        reasons.append("vision judge unavailable")
    for asset in assets:
        inspect = qa.inspect_video(asset) if asset.type in {"video", "final"} else qa.inspect_image(asset)
        if inspect["decision"] != "pass":
            technical = "fail"
            reasons.extend(inspect["failures"])
        else:
            scores["technical_score"] = float(inspect.get("width") or 0) and 70.0 or 70.0
            wanted = str(run.inputs.get("aspect_ratio") or "")
            if wanted == "9:16" and inspect.get("width") and inspect.get("height") and inspect["width"] > inspect["height"]:
                technical = "fail"
                platform = "fail"
                reasons.append("aspect_ratio")
    if "technical_score" not in scores:
        scores["technical_score"] = 0.0 if technical != "pass" else 70.0
    if "visual_score" not in scores:
        scores["visual_score"] = 0.0
    if "content_score" not in scores:
        scores["content_score"] = 0.0
    scores["platform_score"] = 70.0 if platform == "pass" else 0.0
    scores["overall_score"] = round(sum(scores[k] for k in ("technical_score", "visual_score", "content_score", "platform_score")) / 4, 2)
    return {
        "visual_quality": visual,
        "identity_quality": identity,
        "technical_quality": technical,
        "policy_quality": policy,
        "platform_quality": platform,
        "reasons": reasons,
        **scores,
    }
