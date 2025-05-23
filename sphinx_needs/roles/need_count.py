"""
Provide the role ``need_count``, which output is the amount of needs found by a given filter-string.

Based on https://github.com/useblocks/sphinxcontrib-needs/issues/37
"""

from __future__ import annotations

from docutils import nodes
from sphinx.application import Sphinx

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.exceptions import NeedsInvalidFilter
from sphinx_needs.filter_common import filter_needs_parts
from sphinx_needs.logging import get_logger

log = get_logger(__name__)


class NeedCount(nodes.Inline, nodes.Element):
    pass


def process_need_count(
    app: Sphinx,
    doctree: nodes.document,
    _fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    needs_config = NeedsSphinxConfig(app.config)
    for node_need_count in found_nodes:
        needs_view = SphinxNeedsData(app.env).get_needs_view()
        filter = node_need_count["reftarget"]

        if filter:
            filters = filter.split(" ? ")
            if len(filters) == 1:
                need_list = needs_view.to_list_with_parts()
                amount = str(
                    len(
                        filter_needs_parts(
                            need_list,
                            needs_config,
                            filters[0],
                            location=node_need_count,
                        )
                    )
                )
            elif len(filters) == 2:
                need_list = needs_view.to_list_with_parts()
                amount_1 = len(
                    filter_needs_parts(
                        need_list, needs_config, filters[0], location=node_need_count
                    )
                )
                amount_2 = len(
                    filter_needs_parts(
                        need_list, needs_config, filters[1], location=node_need_count
                    )
                )
                amount = "inf" if amount_2 == 0 else f"{amount_1 / amount_2 * 100:2.1f}"
            elif len(filters) > 2:
                raise NeedsInvalidFilter(
                    "Filter not valid. Got too many filter elements. Allowed are 1 or 2. "
                    'Use " ? " only once to separate filters.'
                )
        else:
            amount = str(len(needs_view))

        new_node_count = nodes.Text(amount)
        node_need_count.replace_self(new_node_count)
