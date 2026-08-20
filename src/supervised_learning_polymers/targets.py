"""Typed target configuration for the polymer benchmark."""

from collections.abc import Iterable
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TargetName = Literal["Tg", "FFV", "Tc", "Density", "Rg"]
TargetModeName = Literal["single", "group", "all", "sequential"]
MissingValuePolicy = Literal["preserve"]

OPEN_POLYMER_TARGET_ORDER: tuple[TargetName, ...] = ("Tg", "FFV", "Tc", "Density", "Rg")
SEQUENTIAL_POC_ORDER: tuple[TargetName, ...] = ("FFV", "Density", "Tc", "Tg", "Rg")


class ContractModel(BaseModel):
    """Base settings for strict benchmark contract models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ValidRange(ContractModel):
    """Optional permissive numeric range metadata for a target."""

    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def validate_order(self) -> "ValidRange":
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("valid range minimum cannot be greater than maximum")
        return self


class TargetMetadata(ContractModel):
    """Metadata needed to validate, transform, and report one target."""

    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    valid_range: ValidRange = Field(default_factory=ValidRange)
    missing_value_policy: MissingValuePolicy = "preserve"
    transform: str | None = Field(default=None, min_length=1)


class SingleTargetMode(ContractModel):
    mode: Literal["single"] = "single"
    target: str = Field(min_length=1)


class GroupTargetMode(ContractModel):
    mode: Literal["group"] = "group"
    group: str = Field(min_length=1)


class AllTargetMode(ContractModel):
    mode: Literal["all"] = "all"


class SequentialTargetMode(ContractModel):
    mode: Literal["sequential"] = "sequential"
    order: tuple[str, ...] = Field(min_length=1)


TargetMode = Annotated[
    SingleTargetMode | GroupTargetMode | AllTargetMode | SequentialTargetMode,
    Field(discriminator="mode"),
]


class TargetConfig(ContractModel):
    """Top-level target contract for known targets, groups, and selected mode."""

    targets: tuple[TargetMetadata, ...] = Field(min_length=1)
    mode: TargetMode
    groups: dict[str, tuple[str, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "TargetConfig":
        known_targets = self.target_names()
        duplicate_targets = _duplicates(metadata.name for metadata in self.targets)
        if duplicate_targets:
            raise ValueError(f"duplicate target definitions: {', '.join(duplicate_targets)}")

        for group_name, group_targets in self.groups.items():
            if not group_targets:
                raise ValueError(f"group '{group_name}' must contain at least one target")
            duplicate_group_targets = _duplicates(group_targets)
            if duplicate_group_targets:
                raise ValueError(
                    f"group '{group_name}' contains duplicate targets: "
                    f"{', '.join(duplicate_group_targets)}"
                )
            self._validate_known_targets(group_targets, known_targets, f"group '{group_name}'")

        if isinstance(self.mode, SingleTargetMode):
            self._validate_known_targets((self.mode.target,), known_targets, "single target mode")
        elif isinstance(self.mode, GroupTargetMode):
            if self.mode.group not in self.groups:
                raise ValueError(f"unknown target group: {self.mode.group}")
        elif isinstance(self.mode, SequentialTargetMode):
            duplicate_order_targets = _duplicates(self.mode.order)
            if duplicate_order_targets:
                raise ValueError(
                    f"sequential mode contains duplicate targets: "
                    f"{', '.join(duplicate_order_targets)}"
                )
            self._validate_known_targets(self.mode.order, known_targets, "sequential mode")

        return self

    def target_names(self) -> tuple[str, ...]:
        return tuple(metadata.name for metadata in self.targets)

    def metadata_by_name(self) -> dict[str, TargetMetadata]:
        return {metadata.name: metadata for metadata in self.targets}

    def resolve_targets(self) -> tuple[str, ...]:
        if isinstance(self.mode, SingleTargetMode):
            return (self.mode.target,)
        if isinstance(self.mode, GroupTargetMode):
            return self.groups[self.mode.group]
        if isinstance(self.mode, SequentialTargetMode):
            return self.mode.order
        return self.target_names()

    @staticmethod
    def _validate_known_targets(
        target_names: tuple[str, ...], known_targets: tuple[str, ...], context: str
    ) -> None:
        unknown_targets = [name for name in target_names if name not in known_targets]
        if unknown_targets:
            raise ValueError(f"{context} references unknown targets: {', '.join(unknown_targets)}")


def open_polymer_target_config(mode: TargetMode | None = None) -> TargetConfig:
    """Return the default target config for the Open Polymer benchmark."""

    return TargetConfig(
        targets=(
            TargetMetadata(name="Tg", unit="deg C"),
            TargetMetadata(
                name="FFV",
                unit="dimensionless",
                valid_range=ValidRange(minimum=0.0, maximum=1.0),
            ),
            TargetMetadata(name="Tc", unit="W/(m*K)"),
            TargetMetadata(name="Density", unit="g/cm^3"),
            TargetMetadata(name="Rg", unit="Angstrom"),
        ),
        groups={
            "all": OPEN_POLYMER_TARGET_ORDER,
            "sequential_poc": SEQUENTIAL_POC_ORDER,
        },
        mode=mode or AllTargetMode(),
    )


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates
