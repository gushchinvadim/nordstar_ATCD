"""Render existing document layouts using the training location's timezone."""
from copy import copy
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone
from execution.local_time import group_timezone


def document_context(template_name, context):
    prepared = dict(context or {})
    group = prepared.get('group')
    if group and getattr(group, 'actual_completion_date', None) and any(
        kind in template_name for kind in ('/training_tasks/', '/journal/', '/certificate/', '/audit/')
    ):
        # These layouts already read group.end_date. Supply an effective date
        # for the final document without overwriting the planned date in the DB.
        document_group = copy(group)
        document_group.end_date = group.actual_completion_date
        prepared['group'] = document_group
    return prepared


def render_group_html(template_name, context, request=None):
    with timezone.override(group_timezone((context or {}).get('group'))):
        return render_to_string(template_name, document_context(template_name, context), request=request)


def render_group_document(request, template_name, context=None, **kwargs):
    with timezone.override(group_timezone((context or {}).get('group'))):
        return render(request, template_name, document_context(template_name, context), **kwargs)
