"""Notebook report generation for public interface discovery artifacts."""

from argparse import ArgumentParser
from collections.abc import Sequence
from json import dumps
from pathlib import Path
from typing import Any

from supervised_learning_polymers.interface_discovery import load_interface_discovery_artifact
from supervised_learning_polymers.interface_report import render_interface_discovery_report


def build_interface_discovery_notebook(artifact_path: str | Path) -> dict[str, Any]:
    """Build a minimal Jupyter notebook backed by one discovery artifact fixture."""

    artifact_source = Path(artifact_path)
    artifact = load_interface_discovery_artifact(artifact_source)
    report_markdown = render_interface_discovery_report(artifact)

    return {
        "cells": [
            _markdown_cell(
                [
                    "# Interface Discovery Notebook Report\n",
                    "\n",
                    "This notebook prototype reads an interface discovery artifact and renders the "
                    "same review workflow used by the CLI report path.\n",
                ]
            ),
            _code_cell(
                [
                    "from pathlib import Path\n",
                    "from IPython.display import Markdown, display\n",
                    "\n",
                    "from supervised_learning_polymers import (\n",
                    "    load_interface_discovery_artifact,\n",
                    "    render_interface_discovery_report,\n",
                    ")\n",
                    "\n",
                    f"ARTIFACT_PATH = Path({str(artifact_source)!r})\n",
                    "artifact = load_interface_discovery_artifact(ARTIFACT_PATH)\n",
                    "report = render_interface_discovery_report(artifact)\n",
                    "display(Markdown(report))\n",
                ]
            ),
            _markdown_cell(
                [
                    "## Fixture-Rendered Snapshot\n",
                    "\n",
                    "The snapshot below is generated from the artifact fixture so the notebook is "
                    "reviewable before execution.\n",
                    "\n",
                    report_markdown,
                ]
            ),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "pygments_lexer": "ipython3",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def write_interface_discovery_notebook(artifact_path: str | Path, output_path: str | Path) -> Path:
    """Write a reproducible notebook report for one interface discovery artifact."""

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        dumps(build_interface_discovery_notebook(artifact_path), indent=2) + "\n"
    )
    return destination


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for generating a notebook report from a fixture artifact."""

    parser = ArgumentParser(description="Generate a notebook report from an interface artifact.")
    parser.add_argument("artifact", type=Path, help="Path to interface discovery artifact JSON.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("notebooks/interface_discovery_report.ipynb"),
        help="Notebook output path.",
    )
    args = parser.parse_args(argv)

    write_interface_discovery_notebook(args.artifact, args.output)
    return 0


def _markdown_cell(source: list[str]) -> dict[str, Any]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source,
    }


def _code_cell(source: list[str]) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


if __name__ == "__main__":
    raise SystemExit(main())
