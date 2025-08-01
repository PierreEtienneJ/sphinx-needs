from __future__ import annotations

import os
from collections.abc import Iterable, Sequence

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.builders import Builder

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.logging import get_logger
from sphinx_needs.needsfile import NeedsList

LOGGER = get_logger(__name__)


class NeedsBuilder(Builder):
    """Output the needs data as a JSON file,
    filtering by the ``needs_builder_filter`` config option if set,
    and writing to ``needs.json`` (or the ``needs_file`` config option if set)
    in the output folder.

    Note this builder normally completely skips the write phase,
    where all documents are post-transformed, to improve performance.
    It is assumed all need data is already read in the read phase,
    and the post-processing of the data is done in the finish phase.
    """

    name = "needs"
    format = "needs"
    file_suffix = ".txt"
    links_suffix = None

    def get_outdated_docs(self) -> Iterable[str]:
        return []

    def write(
        self,
        build_docnames: Iterable[str] | None,
        updated_docnames: Sequence[str],
        method: str = "update",
    ) -> None:
        # we override this method, to stop any document output files from being written,
        # however, from this method triggers the `write-started` event,
        # which we still want for triggering schema validation.
        # TODO since sphinx 8.1 `Builder.write` is typed as `final` and a new `Builder.write_documents` method is added,
        # see https://github.com/sphinx-doc/sphinx/commit/d135d2eba39136941da101e7933a958362dfa999
        # once sphinx 7 is not supported, we should remove this `write` method and override `write_documents` to "do nothing"
        self.events.emit("write-started", self)

    def finish(self) -> None:
        from sphinx_needs.filter_common import filter_needs_view

        data = SphinxNeedsData(self.env)
        needs = data.get_needs_view()
        needs_config = NeedsSphinxConfig(self.env.config)
        version = getattr(self.env.config, "version", "unset")
        needs_list = NeedsList(self.env.config, self.outdir, self.srcdir)

        if needs_config.file:
            needs_file = needs_config.file
            needs_list.load_json(needs_file)
        else:
            # check if needs.json file exists in conf.py directory
            needs_json = os.path.join(self.srcdir, "needs.json")
            if os.path.exists(needs_json):
                LOGGER.info(
                    "needs.json found, but will not be used because needs_file not configured."
                )

        # Clean needs_list from already stored needs of the current version.
        # This is needed as needs could have been removed from documentation and if this is the case,
        # removed needs would stay in needs_list, if list gets not cleaned.
        needs_list.wipe_version(version)

        filter_string = needs_config.builder_filter
        filtered_needs = filter_needs_view(
            needs,
            needs_config,
            filter_string,
            append_warning="(from need_builder_filter)",
        )

        for need in filtered_needs:
            needs_list.add_need(version, need)

        try:
            needs_list.write_json()
        except Exception as e:
            LOGGER.error(f"Error during writing json file: {e}")
        else:
            LOGGER.info("Needs successfully exported")

    def get_target_uri(self, _docname: str, _typ: str | None = None) -> str:
        # only needed if the write phase is run
        return ""

    def prepare_writing(self, _docnames: set[str]) -> None:
        # only needed if the write phase is run
        pass

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        # only needed if the write phase is run
        pass

    def write_doc_serialized(self, _docname: str, _doctree: nodes.document) -> None:
        # only needed if the write phase is run
        pass

    def cleanup(self) -> None:
        # only needed if the write phase is run
        pass


def build_needs_json(app: Sphinx, _exception: Exception) -> None:
    env = app.env

    if not NeedsSphinxConfig(env.config).build_json:
        return

    # Do not create an additional needs.json, if builder is already "needs".
    if isinstance(app.builder, NeedsBuilder):
        return

    needs_builder = NeedsBuilder(app, env)
    needs_builder.finish()


class NeedsIdBuilder(Builder):
    """Output the needs data as multiple JSON files, one per need,
    filtering by the ``needs_builder_filter`` config option if set,
    and writing to the ``needs_id`` folder (or the ``build_json_per_id_path`` config option if set)
    in the output folder.

    Note this builder completely skips the write phase,
    where all documents are post-transformed, to improve performance.
    It is assumed all need data is already read in the read phase,
    and the post-processing of the data is done in the finish phase.
    """

    name = "needs_id"
    format = "needs"
    file_suffix = ".txt"
    links_suffix = None

    def get_outdated_docs(self) -> Iterable[str]:
        return []

    def write(
        self,
        build_docnames: Iterable[str] | None,
        updated_docnames: Sequence[str],
        method: str = "update",
    ) -> None:
        pass

    def finish(self) -> None:
        from sphinx_needs.filter_common import filter_needs_view

        data = SphinxNeedsData(self.env)
        version = getattr(self.env.config, "version", "unset")
        needs_config = NeedsSphinxConfig(self.env.config)
        filter_string = needs_config.builder_filter

        filtered_needs = filter_needs_view(
            data.get_needs_view(),
            needs_config,
            filter_string,
            append_warning="(from need_builder_filter)",
        )
        needs_build_json_per_id_path = needs_config.build_json_per_id_path
        needs_dir = os.path.join(self.outdir, needs_build_json_per_id_path)
        if not os.path.exists(needs_dir):
            os.makedirs(needs_dir, exist_ok=True)
        for need in filtered_needs:
            needs_list = NeedsList(
                self.env.config, self.outdir, self.srcdir, add_schema=False
            )
            needs_list.wipe_version(version)
            needs_list.add_need(version, need)
            id = need["id"]
            try:
                file_name = f"{id}.json"
                needs_list.write_json(file_name, needs_dir)
            except Exception as e:
                LOGGER.error(f"Needs-ID Builder {id} error: {e}")
        LOGGER.info("Needs_id successfully exported")


def build_needs_id_json(app: Sphinx, _exception: Exception) -> None:
    env = app.env

    if not NeedsSphinxConfig(env.config).build_json_per_id:
        return

    # Do not create an additional needs_json for every needs_id, if builder is already "needs_id".
    if isinstance(app.builder, NeedsIdBuilder):
        return

    needs_id_builder = NeedsIdBuilder(app, env)
    needs_id_builder.finish()


class NeedumlsBuilder(Builder):
    """Write generated PlantUML input files to the output dir,
    that were generated by need directives,
    if they have a ``save`` field set,
    denoting the path relative to the output folder.
    """

    name = "needumls"

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        pass

    def finish(self) -> None:
        env = self.env
        needumls = SphinxNeedsData(env).get_or_create_umls().values()

        for needuml in needumls:
            if needuml["save"]:
                puml_content = needuml["content_calculated"]
                # check if given save path dir exists
                save_path = os.path.join(self.outdir, needuml["save"])
                save_dir = os.path.dirname(save_path)
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir, exist_ok=True)

                LOGGER.info(f"Storing needuml data to file {save_path}.")
                with open(save_path, "w") as f:
                    f.write(puml_content)

    def get_outdated_docs(self) -> Iterable[str]:
        return []

    def prepare_writing(self, _docnames: set[str]) -> None:
        pass

    def write_doc_serialized(self, _docname: str, _doctree: nodes.document) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def get_target_uri(self, _docname: str, _typ: str | None = None) -> str:
        return ""


def build_needumls_pumls(app: Sphinx, _exception: Exception) -> None:
    env = app.env
    config = NeedsSphinxConfig(env.config)

    if not config.build_needumls:
        return

    # Do not create additional files for saved plantuml content, if builder is already "needumls".
    if isinstance(app.builder, NeedumlsBuilder):
        return

    # if other builder like html used together with config: needs_build_needumls
    needs_builder = NeedumlsBuilder(app, env)
    needs_builder.outdir = os.path.join(needs_builder.outdir, config.build_needumls)  # type: ignore[assignment]

    needs_builder.finish()


class SchemaBuilder(Builder):
    """Only validate needs schema, no output is generated."""

    name = "schema"

    def write(
        self,
        build_docnames: Iterable[str] | None,
        updated_docnames: Sequence[str],
        method: str = "update",
    ) -> None:
        # make sure schema validation is done
        self.events.emit("write-started", self)

    def write_doc(self, docname: str, doctree: nodes.document) -> None:
        pass

    def finish(self) -> None:
        pass

    def get_outdated_docs(self) -> Iterable[str]:
        return []

    def prepare_writing(self, _docnames: set[str]) -> None:
        pass

    def write_doc_serialized(self, _docname: str, _doctree: nodes.document) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def get_target_uri(self, _docname: str, _typ: str | None = None) -> str:
        return ""
