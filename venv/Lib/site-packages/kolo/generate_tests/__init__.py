from __future__ import annotations

import platform
from datetime import datetime, timezone

from ..config import load_config
from ..db import load_trace_from_db, setup_db
from ..serialize import load_msgpack
from ..utils import extract_main_frames_from_data, maybe_format
from ..version import __version__
from .format import format_intermediate
from .plan import Plan, build_steps, load_hooks, run_plan_hooks, run_step_hooks
from .processors import load_processors, run_processors


def load_traces(db_path, trace_ids):
    traces = {}
    for trace_id in trace_ids:
        raw_msgpack, _ = load_trace_from_db(db_path, trace_id)
        trace = load_msgpack(raw_msgpack)

        # TODO: We could do something fancier with other threads here..
        frames = extract_main_frames_from_data(trace)

        traces[trace_id] = {
            "frames": frames,
            "trace": trace,
        }
    return traces


def build_test_context(
    *trace_ids: str,
    test_class: str,
    test_name: str,
    config,
    include_generation_timestamp=True,
    use_saved_schemas=False,
):
    processors = load_processors(config)

    db_path = setup_db()
    traces = load_traces(db_path, trace_ids)

    context = {
        "_config": config,
        "_db_path": db_path,
        "_traces": traces,
        "_use_saved_schemas": use_saved_schemas,
        "kolo_version": __version__,
        "now": datetime.now(timezone.utc) if include_generation_timestamp else None,
        "test_class": test_class,
        "test_name": test_name,
    }
    run_processors(processors, context)
    return context


def create_test_plan(config, context, pytest=True) -> Plan:
    plan = Plan(build_steps(context, pytest=pytest), pytest, context)
    plan_hooks, step_hooks = load_hooks(config)
    plan = run_plan_hooks(plan, plan_hooks)
    return run_step_hooks(plan, step_hooks)


def generate_from_trace_ids(
    *trace_ids: str,
    test_class: str,
    test_name: str,
    config=None,
    include_generation_timestamp=True,
    use_saved_schemas=False,
    pytest=True,
) -> str:
    if config is None:
        config = load_config()
    context = build_test_context(
        *trace_ids,
        test_class=test_class,
        test_name=test_name,
        config=config,
        include_generation_timestamp=include_generation_timestamp,
        use_saved_schemas=use_saved_schemas,
    )
    plan = create_test_plan(config, context, pytest)
    rendered = plan.render()
    return maybe_format(rendered)


def generate_test_intermediate_format(
    *trace_ids: str,
    test_class: str,
    test_name: str,
    config=None,
    include_generation_timestamp=True,
    use_saved_schemas: bool = False,
):
    if config is None:  # pragma: no branch
        config = load_config()
    processors = load_processors(config)

    db_path = setup_db()
    traces = load_traces(db_path, trace_ids)

    context = {
        "_config": config,
        "_db_path": db_path,
        "_traces": traces,
        "_use_saved_schemas": use_saved_schemas,
        "kolo_version": __version__,
        "now": datetime.now(timezone.utc) if include_generation_timestamp else None,
        "test_class": test_class,
        "test_name": test_name,
    }

    for processor in processors:  # pragma: no branch
        output = processor(context)
        if output:
            context.update(output)
        if "sections" in context and "sql_fixtures" in context["sections"][0]:
            yield from format_intermediate(context)
            break
