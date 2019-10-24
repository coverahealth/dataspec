import re
import sys
import threading
import uuid
from datetime import date, datetime, time
from typing import (
    Any,
    Callable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

import attr

from dataspec.base import (
    Conformer,
    ErrorDetails,
    ObjectSpec,
    OptionalKey,
    PredicateSpec,
    Spec,
    SpecPredicate,
    Tag,
    ValidatorFn,
    ValidatorSpec,
    compose_conformers,
    make_spec,
    pred_to_validator,
)

T = TypeVar("T")


def _tag_maybe(
    maybe_tag: Union[Tag, T], *args: T
) -> Tuple[Optional[str], Tuple[T, ...]]:
    """Return the Spec tag and the remaining arguments if a tag is given, else return
    the arguments."""
    tag = maybe_tag if isinstance(maybe_tag, str) else None
    return tag, (cast("Tuple[T, ...]", (maybe_tag, *args)) if tag is None else args)


def any_spec(*preds: SpecPredicate, conformer: Optional[Conformer] = None) -> Spec:
    """Return a Spec which may be satisfied if the input value satisfies at least one
    input Spec."""
    tag, preds = _tag_maybe(*preds)  # pylint: disable=no-value-for-parameter
    specs = [make_spec(pred) for pred in preds]

    def _any_pred(e) -> bool:
        for spec in specs:
            if spec.is_valid(e):
                return True

        return False

    return PredicateSpec(tag or "any", pred=_any_pred, conformer=conformer)


def all_spec(*preds: SpecPredicate, conformer: Optional[Conformer] = None) -> Spec:
    """Return a Spec which requires all of the input Specs to be satisfied to validate
    input data."""
    tag, preds = _tag_maybe(*preds)  # pylint: disable=no-value-for-parameter
    specs = [make_spec(pred) for pred in preds]

    def _all_preds(e) -> bool:
        """Validate e against successive conformations to spec in specs."""

        for spec in specs:
            if not spec.is_valid(e):
                return False
            e = spec.conform_valid(e)

        return True

    return PredicateSpec(
        tag or "all",
        pred=_all_preds,
        conformer=compose_conformers(*specs, conform_final=conformer),
    )


def bool_spec(
    tag: Optional[Tag] = None,
    allowed_values: Optional[Set[bool]] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """Return a Spec which returns True for boolean values."""

    assert allowed_values is None or all(isinstance(e, bool) for e in allowed_values)

    @pred_to_validator("Value '{value}' is not boolean", complement=True)
    def is_bool(v) -> bool:
        return isinstance(v, bool)

    validators = [is_bool]

    if allowed_values is not None:

        @pred_to_validator(
            f"Value '{{value}}' not in {allowed_values}", complement=True
        )
        def is_allowed_bool_type(v) -> bool:
            return v in allowed_values  # type: ignore

        validators.append(is_allowed_bool_type)

    return ValidatorSpec.from_validators(
        tag or "bool", *validators, conformer=conformer
    )


def bytes_spec(  # noqa: MC0001  # pylint: disable=too-many-arguments
    tag: Optional[Tag] = None,
    type_: Tuple[Union[Type[bytes], Type[bytearray]], ...] = (bytes, bytearray),
    minlength: Optional[int] = None,
    maxlength: Optional[int] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """Return a spec that can validate bytes and bytearrays against common rules."""

    @pred_to_validator(f"Value '{{value}}' is not a {type_}", complement=True)
    def is_bytes(s: Any) -> bool:
        return isinstance(s, type_)

    validators: List[Union[ValidatorFn, ValidatorSpec]] = [is_bytes]

    if minlength is not None:

        if not isinstance(minlength, int):
            raise TypeError("Byte minlength spec must be an integer length")

        if minlength < 0:
            raise ValueError("Byte minlength spec cannot be less than 0")

        @pred_to_validator(
            f"Bytes '{{value}}' does not meet minimum length {minlength}"
        )
        def bytestr_has_min_length(s: str) -> bool:
            return len(s) < minlength  # type: ignore

        validators.append(bytestr_has_min_length)

    if maxlength is not None:

        if not isinstance(maxlength, int):
            raise TypeError("Byte maxlength spec must be an integer length")

        if maxlength < 0:
            raise ValueError("Byte maxlength spec cannot be less than 0")

        @pred_to_validator(f"Bytes '{{value}}' exceeds maximum length {maxlength}")
        def bytestr_has_max_length(s: str) -> bool:
            return len(s) > maxlength  # type: ignore

        validators.append(bytestr_has_max_length)

    if minlength is not None and maxlength is not None:
        if minlength > maxlength:
            raise ValueError(
                "Cannot define a spec with minlength greater than maxlength"
            )

    return ValidatorSpec.from_validators(
        tag or "bytes", *validators, conformer=conformer
    )


def every_spec(
    tag: Optional[Tag] = None, conformer: Optional[Conformer] = None
) -> Spec:
    """Return a Spec which returns True for every possible value."""

    def always_true(_) -> bool:
        return True

    return PredicateSpec(tag or "every", always_true, conformer=conformer)


def _make_datetime_spec_factory(
    type_: Union[Type[datetime], Type[date], Type[time]]
) -> Callable[..., Spec]:
    """
    Factory function for generating datetime type spec factories.

    Yep.
    """

    def _datetime_spec_factory(
        tag: Optional[Tag] = None,
        before: Optional[type_] = None,  # type: ignore
        after: Optional[type_] = None,  # type: ignore
        is_aware: Optional[bool] = None,
        conformer: Optional[Conformer] = None,
    ) -> Spec:
        """Return a Spec which validates datetime types with common rules."""

        @pred_to_validator(f"Value '{{value}}' is not {type_}", complement=True)
        def is_datetime_type(v) -> bool:
            return isinstance(v, type_)

        validators = [is_datetime_type]

        if before is not None:

            @pred_to_validator(f"Value '{{value}}' is not before {before}")
            def is_before(dt) -> bool:
                return before < dt

            validators.append(is_before)

        if after is not None:

            @pred_to_validator(f"Value '{{value}}' is not after {after}")
            def is_after(dt) -> bool:
                return after > dt

            validators.append(is_after)

        if is_aware is not None:
            if type_ is datetime:

                @pred_to_validator(
                    f"Datetime '{{value}}' is not aware", complement=is_aware
                )
                def datetime_is_aware(d: datetime) -> bool:
                    return d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None

                validators.append(datetime_is_aware)

            elif type_ is time:

                @pred_to_validator(
                    f"Time '{{value}}' is not aware", complement=is_aware
                )
                def time_is_aware(t: time) -> bool:
                    return t.tzinfo is not None and t.tzinfo.utcoffset(None) is not None

                validators.append(time_is_aware)

            elif is_aware is True:
                raise TypeError(f"Type {type_} cannot be timezone aware")

        return ValidatorSpec.from_validators(
            tag or type_.__name__, *validators, conformer=conformer
        )

    return _datetime_spec_factory


datetime_spec = _make_datetime_spec_factory(datetime)
date_spec = _make_datetime_spec_factory(date)
time_spec = _make_datetime_spec_factory(time)


def nilable_spec(
    *args: Union[Tag, SpecPredicate], conformer: Optional[Conformer] = None
) -> Spec:
    """Return a Spec which either satisfies a single Spec predicate or which is None."""
    tag, preds = _tag_maybe(*args)  # pylint: disable=no-value-for-parameter
    assert len(preds) == 1, "Only one predicate allowed"
    spec = make_spec(cast("SpecPredicate", preds[0]))

    def nil_or_pred(e) -> bool:
        if e is None:
            return True

        return spec.is_valid(e)

    return PredicateSpec(tag or "nilable", pred=nil_or_pred, conformer=conformer)


def num_spec(
    tag: Optional[Tag] = None,
    type_: Union[Type, Tuple[Type, ...]] = (float, int),
    min_: Union[complex, float, int, None] = None,
    max_: Union[complex, float, int, None] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """Return a spec that can validate numeric values against common rules."""

    @pred_to_validator(f"Value '{{value}}' is not type {type_}", complement=True)
    def is_numeric_type(x: Any) -> bool:
        return isinstance(x, type_)

    validators = [is_numeric_type]

    if min_ is not None:

        @pred_to_validator(f"Number '{{value}}' is smaller than minimum {min_}")
        def num_meets_min(x: Union[complex, float, int]) -> bool:
            return x < min_  # type: ignore

        validators.append(num_meets_min)

    if max_ is not None:

        @pred_to_validator(f"String '{{value}}' exceeds maximum length {max_}")
        def num_under_max(x: Union[complex, float, int]) -> bool:
            return x > max_  # type: ignore

        validators.append(num_under_max)

    if min_ is not None and max_ is not None:
        if min_ > max_:  # type: ignore
            raise ValueError("Cannot define a spec with min greater than max")

    return ValidatorSpec.from_validators(tag or "num", *validators, conformer=conformer)


def obj_spec(
    *args: Union[Tag, SpecPredicate], conformer: Optional[Conformer] = None
) -> Spec:
    """Return a Spec for an Object."""
    tag, preds = _tag_maybe(*args)  # pylint: disable=no-value-for-parameter
    assert len(preds) == 1, "Only one predicate allowed"
    return ObjectSpec.from_val(
        tag or "object",
        cast(Mapping[str, SpecPredicate], preds[0]),
        conformer=conformer,
    )


def opt_key(k: T) -> OptionalKey:
    """Return `k` wrapped in a marker object indicating that the key is optional in
    associative specs."""
    return OptionalKey(k)


@attr.s(auto_attribs=True, frozen=True, slots=True)
class StrFormat:
    validator: ValidatorSpec
    conformer: Optional[Conformer] = None

    @property
    def conforming_validator(self) -> ValidatorSpec:
        if self.conformer is not None:
            return cast(ValidatorSpec, self.validator.with_conformer(self.conformer))
        else:
            return self.validator


_STR_FORMATS: MutableMapping[str, StrFormat] = {}
_STR_FORMAT_LOCK = threading.Lock()


def register_str_format_spec(
    name: str, validate: ValidatorSpec, conformer: Optional[Conformer] = None
) -> None:  # pragma: no cover
    """Register a new String format, which will be checked by the ValidatorSpec
    `validate`. A conformer can be supplied for the string format which will
    be applied if desired, but may otherwise be ignored."""
    with _STR_FORMAT_LOCK:
        _STR_FORMATS[name] = StrFormat(validate, conformer=conformer)


def register_str_format(
    tag: Tag, conformer: Optional[Conformer] = None
) -> Callable[[Callable], ValidatorFn]:
    """Decorator to register a Validator function as a string format."""

    def create_str_format(f) -> ValidatorFn:
        register_str_format_spec(tag, ValidatorSpec(tag, f), conformer=conformer)
        return f

    return create_str_format


@register_str_format("uuid", conformer=uuid.UUID)
def _str_is_uuid(s: str) -> Iterator[ErrorDetails]:
    try:
        uuid.UUID(s)
    except ValueError:
        yield ErrorDetails(
            message=f"String does not contain UUID", pred=_str_is_uuid, value=s
        )


if sys.version_info >= (3, 7):

    @register_str_format("iso-date", conformer=date.fromisoformat)
    def _str_is_iso_date(s: str) -> Iterator[ErrorDetails]:
        try:
            date.fromisoformat(s)
        except ValueError:
            yield ErrorDetails(
                message=f"String does not contain ISO formatted date",
                pred=_str_is_iso_date,
                value=s,
            )

    @register_str_format("iso-datetime", conformer=datetime.fromisoformat)
    def _str_is_iso_datetime(s: str) -> Iterator[ErrorDetails]:
        try:
            datetime.fromisoformat(s)
        except ValueError:
            yield ErrorDetails(
                message=f"String does not contain ISO formatted datetime",
                pred=_str_is_iso_datetime,
                value=s,
            )

    @register_str_format("iso-time", conformer=time.fromisoformat)
    def _str_is_iso_time(s: str) -> Iterator[ErrorDetails]:
        try:
            time.fromisoformat(s)
        except ValueError:
            yield ErrorDetails(
                message=f"String does not contain ISO formatted time",
                pred=_str_is_iso_time,
                value=s,
            )


else:

    _ISO_DATE_REGEX = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

    def _str_to_iso_date(s: str) -> Optional[date]:
        match = re.fullmatch(_ISO_DATE_REGEX, s)
        if match is not None:
            year, month, day = tuple(int(match.group(x)) for x in (1, 2, 3))
            return date(year, month, day)
        else:
            return None

    @register_str_format("iso-date", conformer=_str_to_iso_date)
    def _str_is_iso_date(s: str) -> Iterator[ErrorDetails]:
        d = _str_to_iso_date(s)
        if d is None:
            yield ErrorDetails(
                message=f"String does not contain ISO formatted date",
                pred=_str_is_iso_date,
                value=s,
            )


def str_spec(  # noqa: MC0001  # pylint: disable=too-many-arguments
    tag: Optional[Tag] = None,
    length: Optional[int] = None,
    minlength: Optional[int] = None,
    maxlength: Optional[int] = None,
    regex: Optional[str] = None,
    format_: Optional[str] = None,
    conform_format: Optional[str] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """Return a spec that can validate strings against common rules."""

    @pred_to_validator(f"Value '{{value}}' is not a string", complement=True)
    def is_str(s: Any) -> bool:
        return isinstance(s, str)

    validators: List[Union[ValidatorFn, ValidatorSpec]] = [is_str]

    if length is not None:

        if not isinstance(length, int):
            raise TypeError("String length spec must be an integer length")

        if length < 0:
            raise ValueError("String length spec cannot be less than 0")

        if minlength is not None or maxlength is not None:
            raise ValueError(
                "Cannot define a string spec with exact length "
                "and minlength or maxlength"
            )

        @pred_to_validator(f"String length does not equal {length}", convert_value=len)
        def str_is_exactly_len(v) -> bool:
            return len(v) != length

        validators.append(str_is_exactly_len)

    if minlength is not None:

        if not isinstance(minlength, int):
            raise TypeError("String minlength spec must be an integer length")

        if minlength < 0:
            raise ValueError("String minlength spec cannot be less than 0")

        @pred_to_validator(
            f"String '{{value}}' does not meet minimum length {minlength}"
        )
        def str_has_min_length(s: str) -> bool:
            return len(s) < minlength  # type: ignore

        validators.append(str_has_min_length)

    if maxlength is not None:

        if not isinstance(maxlength, int):
            raise TypeError("String maxlength spec must be an integer length")

        if maxlength < 0:
            raise ValueError("String maxlength spec cannot be less than 0")

        @pred_to_validator(f"String '{{value}}' exceeds maximum length {maxlength}")
        def str_has_max_length(s: str) -> bool:
            return len(s) > maxlength  # type: ignore

        validators.append(str_has_max_length)

    if minlength is not None and maxlength is not None:
        if minlength > maxlength:
            raise ValueError(
                "Cannot define a spec with minlength greater than maxlength"
            )

    if regex is not None and format_ is None and conform_format is None:
        _pattern = re.compile(regex)

        @pred_to_validator(
            f"String '{{value}}' does match regex '{regex}'", complement=True
        )
        def str_matches_regex(s: str) -> bool:
            return bool(_pattern.fullmatch(s))

        validators.append(str_matches_regex)
    elif regex is None and format_ is not None and conform_format is None:
        with _STR_FORMAT_LOCK:
            validators.append(_STR_FORMATS[format_].validator)
    elif regex is None and format_ is None and conform_format is not None:
        with _STR_FORMAT_LOCK:
            validators.append(_STR_FORMATS[conform_format].conforming_validator)
    elif sum(int(v is not None) for v in [regex, format_, conform_format]) > 1:
        raise ValueError(
            "Cannot define a spec with more than one of: regex, format, conforming format"
        )

    return ValidatorSpec.from_validators(tag or "str", *validators, conformer=conformer)


def uuid_spec(
    tag: Optional[Tag] = None,
    versions: Optional[Set[int]] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """Return a spec that can validate UUIDs against common rules."""

    @pred_to_validator(f"Value '{{value}}' is not a UUID", complement=True)
    def is_uuid(v: Any) -> bool:
        return isinstance(v, uuid.UUID)

    validators: List[Union[ValidatorFn, ValidatorSpec]] = [is_uuid]

    if versions is not None:

        if not {1, 3, 4, 5}.issuperset(set(versions)):
            raise ValueError("UUID versions must be specified as a set of integers")

        @pred_to_validator(f"UUID '{{value}}' is not RFC 4122 variant", complement=True)
        def uuid_is_rfc_4122(v: uuid.UUID) -> bool:
            return v.variant is uuid.RFC_4122

        validators.append(uuid_is_rfc_4122)

        @pred_to_validator(
            f"UUID '{{value}}' is not in versions {versions}", complement=True
        )
        def uuid_is_version(v: uuid.UUID) -> bool:
            return v.version in versions  # type: ignore

        validators.append(uuid_is_version)

    return ValidatorSpec.from_validators(
        tag or "uuid", *validators, conformer=conformer
    )
