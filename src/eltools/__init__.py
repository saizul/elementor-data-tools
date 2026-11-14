"""eltools: utilities for Elementor ``_elementor_data`` JSON."""

from eltools.diff import DiffResult, diff_documents
from eltools.document import Document, ElementorDataError, dumps, load, loads
from eltools.extract import extract_fields, insert_fields
from eltools.fields import TEXT_FIELDS
from eltools.images import ImageRef, find_images
from eltools.links import LinkRef, find_links
from eltools.reid import IdChange, reassign_ids
from eltools.replace import Change, replace_text
from eltools.tree import Node, element_counts, find_by_id, walk, widget_counts
from eltools.validate import Issue, validate
from eltools.wpmeta import command_template, to_wp_meta

__version__ = "1.0.0"

__all__ = [
    "TEXT_FIELDS",
    "Change",
    "DiffResult",
    "Document",
    "ElementorDataError",
    "IdChange",
    "ImageRef",
    "Issue",
    "LinkRef",
    "Node",
    "command_template",
    "diff_documents",
    "dumps",
    "element_counts",
    "extract_fields",
    "find_by_id",
    "find_images",
    "find_links",
    "insert_fields",
    "load",
    "loads",
    "reassign_ids",
    "replace_text",
    "to_wp_meta",
    "validate",
    "walk",
    "widget_counts",
]
