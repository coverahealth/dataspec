import functools
import inspect
import re
import sys
import threading
import uuid
from abc import ABC, abstractmethod
from collections import namedtuple
from datetime import date, datetime, time
from enum import EnumMeta
from itertools import chain
from typing import (
    Any,
    Callable,
    FrozenSet,
    Generic,
    Iterable,
    Iterator,
    List,
    Mapping,
    MutableMapping,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

import attr

T = TypeVar("T")
V = TypeVar("V")


class _Invalid:
    pass


INVALID = _Invalid()


Conformer = Callable[[T], Union[V, _Invalid]]
PredicateFn = Callable[[Any], bool]
ValidatorFn = Callable[[Any], Iterable["ErrorDetails"]]
Tag = str

SpecPredicate = Union[  # type: ignore
    Mapping[Any, "SpecPredicate"],  # type: ignore
    Tuple["SpecPredicate", ...],  # type: ignore
    List["SpecPredicate"],  # type: ignore
    FrozenSet[Any],
    Set[Any],
    PredicateFn,
    ValidatorFn,
    "Spec",
]


NO_ERROR_PATH = object()


@attr.s(auto_attribs=True, slots=True)
class ErrorDetails:
    message: str
    pred: SpecPredicate
    value: Any
    via: List[Tag] = attr.ib(factory=list)
    path: List[Any] = attr.ib(factory=list)

    def with_details(self, tag: Tag, loc: Any = NO_ERROR_PATH) -> "ErrorDetails":
        """
        Add the given tag to the `via` list and add a key path if one is specified by
        the caller.

        This method mutates the `via` and `path` list attributes directly rather than
        returning a new `ErrorDetails` instance.
        """
        self.via.insert(0, tag)
        if loc is not NO_ERROR_PATH:
            self.path.insert(0, loc)
        return self


@attr.s(auto_attribs=True, slots=True)
class ValidationError(Exception):
    errors: Sequence[ErrorDetails]


class Spec(ABC):
    @property
    @abstractmethod
    def tag(self) -> Tag:  # pragma: no cover
        """
        Return the tag used to identify this Spec.

        Tags are useful for debugging and in validation messages.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def _conformer(self) -> Optional[Conformer]:  # pragma: no cover
        """Return the custom conformer for this Spec."""
        raise NotImplementedError

    @property
    def conformer(self) -> Conformer:
        """Return the conformer attached to this Spec."""
        return self._conformer or self._default_conform

    @abstractmethod
    def validate(self, v: Any) -> Iterator[ErrorDetails]:  # pragma: no cover
        """
        Validate the value `v` against the Spec.

        Yields an iterable of Spec failures, if any.
        """
        raise NotImplementedError

    def validate_ex(self, v: Any):
        """
        Validate the value `v` against the Spec.

        Throws a `ValidationError` with a list of Spec failures, if any.
        """
        errors = list(self.validate(v))
        if errors:
            raise ValidationError(errors)

    def is_valid(self, v: Any) -> bool:
        """Returns True if `v` is valid according to the Spec, otherwise returns
        False."""
        try:
            next(self.validate(v))
        except StopIteration:
            return True
        else:
            return False

    def _default_conform(self, v):
        """
        Default conformer for the Spec.

        If no custom conformer is specified, this conformer will be invoked.
        """
        return v

    def conform_valid(self, v):
        """
        Conform `v` to the Spec without checking if v is valid first and return the
        possibly conformed value or `INVALID` if the value cannot be conformed.

        This function should be used only if `v` has already been check for validity.
        """
        return self.conformer(v)

    def conform(self, v: Any):
        """Conform `v` to the Spec, first checking if v is valid, and return the
        possibly conformed value or `INVALID` if the value cannot be conformed."""
        if self.is_valid(v):
            return self.conform_valid(v)
        else:
            return INVALID

    def with_conformer(self, conformer: Conformer) -> "Spec":
        """Return a new Spec instance with the new conformer."""
        return attr.evolve(self, conformer=conformer)

    def with_tag(self, tag: Tag) -> "Spec":
        """Return a new Spec instance with the new tag applied."""
        return attr.evolve(self, tag=tag)


def _enrich_errors(
    errors: Iterable[ErrorDetails], tag: Tag, loc: Any = NO_ERROR_PATH
) -> Iterable[ErrorDetails]:
    """
    Enrich the stream of errors with tag and location information.

    Tags are useful for determining which specs were evaluated to produce the error.
    Location information can help callers pinpoint exactly where in their data structure
    the error occurred. If no location information is relevant for the error (perhaps
    for a scalar spec type), then the default `NO_ERROR_PATH` should be used.
    """
    for error in errors:
        yield error.with_details(tag, loc=loc)


def compose_conformers(
    *specs: Spec, conform_final: Optional[Conformer] = None
) -> Conformer:
    """
    Return a single conformer which is the composition of the conformers from each of
    the child specs.

    Apply the `conform_final` conformer on the final return from the composition, if
    any.
    """

    def do_conform(v):
        conformed_v = v
        for spec in specs:
            conformed_v = spec.conform(conformed_v)
            if conformed_v is INVALID:
                break
        return conformed_v if conform_final is None else conform_final(conformed_v)

    return do_conform


@attr.s(auto_attribs=True, frozen=True, slots=True)
class ValidatorSpec(Spec):
    """Validator Specs yield richly detailed errors from their validation functions and
    can be useful for answering more detailed questions about their their input data
    than a simple predicate function."""

    tag: Tag
    _validate: ValidatorFn
    _conformer: Optional[Conformer] = None

    def validate(self, v) -> Iterator[ErrorDetails]:
        try:
            yield from _enrich_errors(self._validate(v), self.tag)
        except Exception as e:
            yield ErrorDetails(
                message=f"Exception occurred during Validation: {e}",
                pred=self,
                value=v,
                via=[self.tag],
            )

    @classmethod
    def from_validators(
        cls,
        tag: Tag,
        *preds: Union[ValidatorFn, "ValidatorSpec"],
        conformer: Optional[Conformer] = None,
    ) -> "ValidatorSpec":
        """Return a single Validator spec from the composition of multiple validator
        functions or ValidatorSpec instances."""
        assert len(preds) > 0, "At least on predicate must be specified"

        # Avoid wrapping an existing validator spec or singleton spec in an extra layer
        # of indirection
        if len(preds) == 1:
            if isinstance(preds[0], ValidatorSpec):
                return preds[0]
            else:
                return ValidatorSpec(tag, preds[0], conformer=conformer)

        specs = []
        for pred in preds:
            if isinstance(pred, ValidatorSpec):
                specs.append(pred)
            else:
                specs.append(ValidatorSpec(pred.__name__, pred))

        def do_validate(v) -> Iterator[ErrorDetails]:
            for spec in specs:
                yield from spec.validate(v)

        return cls(
            tag, do_validate, compose_conformers(*specs, conform_final=conformer)
        )


@attr.s(auto_attribs=True, frozen=True, slots=True)
class PredicateSpec(Spec):
    """
    Predicate Specs are useful for validating data with a boolean predicate function.

    Predicate specs can be useful for validating simple yes/no questions about data, but
    the errors they can produce are limited by the nature of the predicate return value.
    """

    tag: Tag
    _pred: PredicateFn
    _conformer: Optional[Conformer] = None

    def validate(self, v) -> Iterator[ErrorDetails]:
        try:
            if not self._pred(v):
                yield ErrorDetails(
                    message=f"Value '{v}' does not satisfy predicate '{self.tag or self._pred}'",
                    pred=self._pred,
                    value=v,
                    via=[self.tag],
                )
        except Exception as e:
            yield ErrorDetails(
                message=f"Exception occurred during Validation: {e}", pred=self, value=v
            )


_MUNGE_NAMES = re.compile(r"[\s|-]")


def _complement(pred: PredicateFn) -> PredicateFn:
    """Return the complement to the predicate function `pred`."""

    @functools.wraps(pred)
    def complement(v: Any) -> bool:
        return not pred(v)

    return complement


def _identity(x: T) -> T:
    """Return the argument."""
    return x


def pred_to_validator(
    message: str,
    complement: bool = False,
    convert_value: Callable[[Any], Any] = _identity,
):
    """Decorator to convert a simple predicate to a validator function."""

    def to_validator(pred: PredicateFn) -> ValidatorFn:
        pred = _complement(pred) if complement else pred

        @functools.wraps(pred)
        def validator(v) -> Iterable[ErrorDetails]:
            if pred(v):
                yield ErrorDetails(
                    message=message.format(value=convert_value(v)), pred=pred, value=v
                )

        return validator

    return to_validator


@attr.s(auto_attribs=True, frozen=True, slots=True)
class CollSpec(Spec):
    tag: Tag
    _spec: Spec
    _conformer: Optional[Conformer] = None
    _out_type: Optional[Type] = None
    _validate_coll: Optional[ValidatorSpec] = None

    @classmethod  # noqa: MC0001
    def from_val(
        cls,
        tag: Optional[Tag],
        sequence: Sequence[Union[SpecPredicate, Mapping[str, Any]]],
        conformer: Conformer = None,
    ):
        # pylint: disable=too-many-branches,too-many-locals
        spec = s(sequence[0])
        validate_coll: Optional[ValidatorSpec] = None

        try:
            kwargs = sequence[1]
            if not isinstance(kwargs, dict):
                raise TypeError("Collection spec options must be a dict")
        except IndexError:
            kwargs = {}

        validators = []

        allow_str: bool = kwargs.get("allow_str", False)  # type: ignore
        maxlength: Optional[int] = kwargs.get("maxlength", None)  # type: ignore
        minlength: Optional[int] = kwargs.get("minlength", None)  # type: ignore
        count: Optional[int] = kwargs.get("count", None)  # type: ignore
        type_: Optional[Type] = kwargs.get("kind", None)  # type: ignore
        out_type: Optional[Type] = kwargs.get("into", None)  # type: ignore

        if not allow_str and type_ is None:

            @pred_to_validator("Collection is a string, not a collection")
            def coll_is_str(v) -> bool:
                return isinstance(v, str)

            validators.append(coll_is_str)

        if maxlength is not None:

            if not isinstance(maxlength, int):
                raise TypeError("Collection maxlength spec must be an integer length")

            if maxlength < 0:
                raise ValueError("Collection maxlength spec cannot be less than 0")

            @pred_to_validator(
                "Collection length exceeds max length {maxlength}", convert_value=len
            )
            def coll_has_max_length(v) -> bool:
                return len(v) > maxlength  # type: ignore

            validators.append(coll_has_max_length)

        if minlength is not None:

            if not isinstance(minlength, int):
                raise TypeError("Collection minlength spec must be an integer length")

            if minlength < 0:
                raise ValueError("Collection minlength spec cannot be less than 0")

            @pred_to_validator(
                "Collection length does not meet minimum length {minlength}",
                convert_value=len,
            )
            def coll_has_min_length(v) -> bool:
                return len(v) < minlength  # type: ignore

            validators.append(coll_has_min_length)

        if minlength is not None and maxlength is not None:
            if minlength > maxlength:
                raise ValueError(
                    "Cannot define a spec with minlength greater than maxlength"
                )

        if count is not None:

            if not isinstance(count, int):
                raise TypeError("Collection count spec must be an integer length")

            if count < 0:
                raise ValueError("Collection count spec cannot be less than 0")

            if minlength is not None or maxlength is not None:
                raise ValueError(
                    "Cannot define a collection spec with count and minlength or maxlength"
                )

            @pred_to_validator(
                f"Collection length does not equal {count}", convert_value=len
            )
            def coll_is_exactly_len(v) -> bool:
                return len(v) != count

            validators.append(coll_is_exactly_len)

        if type_ and isinstance(type_, type):

            @pred_to_validator(
                f"Collection is not of type {type_}",
                complement=True,
                convert_value=type,
            )
            def coll_is_type(v) -> bool:
                return isinstance(v, type_)  # type: ignore

            validators.append(coll_is_type)

        if validators:
            validate_coll = ValidatorSpec.from_validators("coll", *validators)

        return cls(
            tag or "coll",
            spec=spec,
            conformer=conformer,
            out_type=out_type,
            validate_coll=validate_coll,
        )

    def validate(self, v) -> Iterator[ErrorDetails]:
        if self._validate_coll:
            yield from _enrich_errors(self._validate_coll.validate(v), self.tag)

        for i, e in enumerate(v):
            yield from _enrich_errors(self._spec.validate(e), self.tag, i)

    def _default_conform(self, v):
        return (self._out_type or type(v))(self._spec.conform(e) for e in v)


# In Python 3.6, you cannot inherit directly from Generic with slotted classes:
# https://github.com/python-attrs/attrs/issues/313
@attr.s(auto_attribs=True, frozen=True, slots=sys.version_info >= (3, 7))
class OptionalKey(Generic[T]):
    key: T


def _opt(k: T) -> OptionalKey:
    """Return `k` wrapped in a marker object indicating that the key is optional in
    associative specs."""
    return OptionalKey(k)


@attr.s(auto_attribs=True, frozen=True, slots=True)
class DictSpec(Spec):
    tag: Tag
    _reqkeyspecs: Mapping[Any, Spec] = attr.ib(factory=dict)
    _optkeyspecs: Mapping[Any, Spec] = attr.ib(factory=dict)
    _conformer: Optional[Conformer] = None

    @classmethod
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[str, SpecPredicate],
        conformer: Conformer = None,
    ):
        reqkeys = {}
        optkeys: MutableMapping[Any, Spec] = {}
        for k, v in kvspec.items():
            if isinstance(k, OptionalKey):
                optkeys[k.key] = s(v)
            else:
                reqkeys[k] = s(v)

        return cls(
            tag or "map", reqkeyspecs=reqkeys, optkeyspecs=optkeys, conformer=conformer
        )

    def validate(self, d) -> Iterator[ErrorDetails]:  # pylint: disable=arguments-differ
        try:
            for k, vspec in self._reqkeyspecs.items():
                if k in d:
                    yield from _enrich_errors(vspec.validate(d[k]), self.tag, k)
                else:
                    yield ErrorDetails(
                        message=f"Mapping missing key {k}",
                        pred=vspec,
                        value=d,
                        via=[self.tag],
                        path=[k],
                    )
        except TypeError:
            yield ErrorDetails(
                message=f"Value is not a mapping type",
                pred=self,
                value=d,
                via=[self.tag],
            )
            return

        for k, vspec in self._optkeyspecs.items():
            if k in d:
                yield from _enrich_errors(vspec.validate(d[k]), self.tag, k)

    def _default_conform(self, d):  # pylint: disable=arguments-differ
        conformed_d = {}
        for k, spec in self._reqkeyspecs.items():
            conformed_d[k] = spec.conform(d[k])

        for k, spec in self._optkeyspecs.items():
            if k in d:
                conformed_d[k] = spec.conform(d[k])

        return conformed_d


class ObjectSpec(DictSpec):
    def validate(self, o) -> Iterator[ErrorDetails]:  # pylint: disable=arguments-differ
        for k, vspec in self._reqkeyspecs.items():
            if hasattr(o, k):
                yield from _enrich_errors(vspec.validate(getattr(o, k)), self.tag, k)
            else:
                yield ErrorDetails(
                    message=f"Object missing attribute '{k}'",
                    pred=vspec,
                    value=o,
                    via=[self.tag],
                    path=[k],
                )

        for k, vspec in self._optkeyspecs.items():
            if hasattr(o, k):
                yield from _enrich_errors(vspec.validate(getattr(o, k)), self.tag, k)

    def _default_conform(self, o):  # pylint: disable=arguments-differ
        raise TypeError("Cannot use a default conformer for an Object")


@attr.s(auto_attribs=True, frozen=True, slots=True)
class SetSpec(Spec):
    tag: Tag
    _values: Union[Set, FrozenSet]
    _conformer: Optional[Conformer] = None

    def validate(self, v) -> Iterator[ErrorDetails]:
        if v not in self._values:
            yield ErrorDetails(
                message=f"Value '{v}' not in '{self._values}'",
                pred=self._values,
                value=v,
                via=[self.tag],
            )


@attr.s(auto_attribs=True, frozen=True, slots=True)
class TupleSpec(Spec):
    tag: Tag
    _pred: Tuple[SpecPredicate, ...]
    _specs: Tuple[Spec, ...]
    _conformer: Optional[Conformer] = None
    _namedtuple: Optional[Type[NamedTuple]] = None

    @classmethod
    def from_val(
        cls,
        tag: Optional[Tag],
        pred: Tuple[SpecPredicate, ...],
        conformer: Conformer = None,
    ):
        specs = tuple(s(e_pred) for e_pred in pred)

        spec_tags = tuple(re.sub(_MUNGE_NAMES, "_", spec.tag) for spec in specs)
        if tag is not None and len(specs) == len(set(spec_tags)):
            namedtuple_type = namedtuple(  # type: ignore
                re.sub(_MUNGE_NAMES, "_", tag), spec_tags
            )
        else:
            namedtuple_type = None  # type: ignore

        return cls(
            tag or "tuple",
            pred=pred,
            specs=specs,
            conformer=conformer,
            namedtuple=namedtuple_type,  # type: ignore
        )

    def validate(self, t) -> Iterator[ErrorDetails]:  # pylint: disable=arguments-differ
        try:
            if len(t) != len(self._specs):
                yield ErrorDetails(
                    message=f"Expected {len(self._specs)} values; found {len(t)}",
                    pred=self,
                    value=len(t),
                    via=[self.tag],
                )
                return

            for i, (e_pred, elem) in enumerate(zip(self._specs, t)):
                yield from _enrich_errors(e_pred.validate(elem), self.tag, i)
        except TypeError:
            yield ErrorDetails(
                message=f"Value is not a tuple type", pred=self, value=t, via=[self.tag]
            )

    def _default_conform(self, v):
        return ((self._namedtuple and self._namedtuple._make) or tuple)(
            spec.conform(v) for spec, v in zip(self._specs, v)
        )


def _tag_maybe(
    maybe_tag: Union[Tag, T], *args: T
) -> Tuple[Optional[str], Tuple[T, ...]]:
    """Return the Spec tag and the remaining arguments if a tag is given, else return
    the arguments."""
    tag = maybe_tag if isinstance(maybe_tag, str) else None
    return tag, (cast("Tuple[T, ...]", (maybe_tag, *args)) if tag is None else args)


def _anypred(*preds: SpecPredicate, conformer: Optional[Conformer] = None) -> Spec:
    """Return a Spec which may be satisfied if the input value satisfies at least one
    input Spec."""
    tag, preds = _tag_maybe(*preds)  # pylint: disable=no-value-for-parameter
    specs = [s(pred) for pred in preds]

    def _any_pred(e) -> bool:
        for spec in specs:
            if spec.is_valid(e):
                return True

        return False

    return PredicateSpec(tag or "any", pred=_any_pred, conformer=conformer)


def _allpred(*preds: SpecPredicate, conformer: Optional[Conformer] = None) -> Spec:
    """Return a Spec which requires all of the input Specs to be satisfied to validate
    input data."""
    tag, preds = _tag_maybe(*preds)  # pylint: disable=no-value-for-parameter
    specs = [s(pred) for pred in preds]

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


def _bool(
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


def _bytes(  # noqa: MC0001  # pylint: disable=too-many-arguments
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


def _every(tag: Optional[Tag] = None, conformer: Optional[Conformer] = None) -> Spec:
    """Return a Spec which returns True for every possible value."""

    def always_true(_) -> bool:
        return True

    return PredicateSpec(tag or "every", always_true, conformer=conformer)


def _datetime_spec(
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


_datetime = _datetime_spec(datetime)
_date = _datetime_spec(date)
_time = _datetime_spec(time)


def _nilable(
    *args: Union[Tag, SpecPredicate], conformer: Optional[Conformer] = None
) -> Spec:
    """Return a Spec which either satisfies a single Spec predicate or which is None."""
    tag, preds = _tag_maybe(*args)  # pylint: disable=no-value-for-parameter
    assert len(preds) == 1, "Only one predicate allowed"
    spec = s(cast("SpecPredicate", preds[0]))

    def nil_or_pred(e) -> bool:
        if e is None:
            return True

        return spec.is_valid(e)

    return PredicateSpec(tag or "nilable", pred=nil_or_pred, conformer=conformer)


def _num(
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


def _obj(
    *args: Union[Tag, SpecPredicate], conformer: Optional[Conformer] = None
) -> Spec:
    """Return a Spec for an Object."""
    tag, preds = _tag_maybe(*args)  # pylint: disable=no-value-for-parameter
    assert len(preds) == 1, "Only one predicate allowed"
    return ObjectSpec.from_val(
        tag or "object",
        cast("Mapping[str, SpecPredicate]", preds[0]),
        conformer=conformer,
    )


def _str_is_uuid(s: str) -> Iterator[ErrorDetails]:
    try:
        uuid.UUID(s)
    except ValueError:
        yield ErrorDetails(
            message=f"String does not contain UUID", pred=_str_is_uuid, value=s
        )


_STR_FORMATS = {"uuid": ValidatorSpec("uuid-str", _str_is_uuid)}
_STR_FORMAT_LOCK = threading.Lock()


if sys.version_info >= (3, 7):

    def _str_is_iso_date(s: str) -> Iterator[ErrorDetails]:
        try:
            date.fromisoformat(s)
        except ValueError:
            yield ErrorDetails(
                message=f"String does not contain ISO formatted date",
                pred=_str_is_iso_date,
                value=s,
            )

    def _str_is_iso_datetime(s: str) -> Iterator[ErrorDetails]:
        try:
            datetime.fromisoformat(s)
        except ValueError:
            yield ErrorDetails(
                message=f"String does not contain ISO formatted datetime",
                pred=_str_is_iso_datetime,
                value=s,
            )

    with _STR_FORMAT_LOCK:
        _STR_FORMATS["iso-date"] = ValidatorSpec("iso-date", _str_is_iso_date)
        _STR_FORMATS["iso-datetime"] = ValidatorSpec(
            "iso-datetime", _str_is_iso_datetime
        )

else:

    _ISO_DATE_REGEX = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

    def _str_is_iso_date(s: str) -> Iterator[ErrorDetails]:
        match = re.fullmatch(_ISO_DATE_REGEX, s)
        if match is not None:
            year, month, day = tuple(int(match.group(x)) for x in (1, 2, 3))
            d: Optional[date] = date(year, month, day)
        else:
            d = None

        if d is None:
            yield ErrorDetails(
                message=f"String does not contain ISO formatted date",
                pred=_str_is_iso_date,
                value=s,
            )

    with _STR_FORMAT_LOCK:
        _STR_FORMATS["iso-date"] = ValidatorSpec("iso-date", _str_is_iso_date)


def register_str_format(name: str, validate: ValidatorSpec) -> None:  # pragma: no cover
    """Register a new String format."""
    with _STR_FORMAT_LOCK:
        _STR_FORMATS[name] = validate


def _str(  # noqa: MC0001  # pylint: disable=too-many-arguments
    tag: Optional[Tag] = None,
    minlength: Optional[int] = None,
    maxlength: Optional[int] = None,
    regex: Optional[str] = None,
    format_: Optional[str] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """Return a spec that can validate strings against common rules."""

    @pred_to_validator(f"Value '{{value}}' is not a string", complement=True)
    def is_str(s: Any) -> bool:
        return isinstance(s, str)

    validators: List[Union[ValidatorFn, ValidatorSpec]] = [is_str]

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

    if regex is not None and format_ is None:
        _pattern = re.compile(regex)

        @pred_to_validator(
            f"String '{{value}}' does match regex '{regex}'", complement=True
        )
        def str_matches_regex(s: str) -> bool:
            return bool(_pattern.fullmatch(s))

        validators.append(str_matches_regex)
    elif regex is None and format_ is not None:
        with _STR_FORMAT_LOCK:
            validators.append(_STR_FORMATS[format_])
    elif regex is not None and format_ is not None:
        raise ValueError("Cannot define a spec with a regex and format")

    return ValidatorSpec.from_validators(tag or "str", *validators, conformer=conformer)


def _uuid(
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


def _explain(spec: Spec, v) -> Optional[ValidationError]:  # pragma: no cover
    """Return a ValidationError instance containing all of the errors validating `v`, if
    there were any; return None otherwise."""
    try:
        spec.validate_ex(v)
    except ValidationError as e:
        return e
    else:
        return None


def _fdef(
    argpreds: Tuple[SpecPredicate, ...] = (),
    kwargpreds: Optional[Mapping[str, SpecPredicate]] = None,
    retpred: Optional[SpecPredicate] = None,
):
    """Wrap a function `f` and validate its arguments, keyword arguments, and return
    value with Specs, if any are given."""
    argspecs = s(argpreds) if argpreds else None
    kwargspecs = s(kwargpreds) if kwargpreds else None
    retspec = s(retpred) if retpred else None

    assert [argspecs, kwargspecs, retspec].count(
        None
    ) < 3, "At least one fdef spec must be given"

    def wrap_f_specs(f):
        @functools.wraps(f)
        def wrapped_f(*args, **kwargs):
            if argspecs is not None:
                argspecs.validate_ex(args)
            if kwargspecs is not None:
                kwargspecs.validate_ex(kwargs)
            ret = f(*args, **kwargs)
            if retspec is not None:
                retspec.validate_ex(ret)
            return ret

        return wrapped_f

    return wrap_f_specs


# We are using this gross and weird API class singleton because MyPy currently
# does not typing attributes on function objects, so this is the only way
# for us to supply a callable with callable attributes.
#
# Based on this comment:
# https://github.com/python/mypy/issues/2087#issuecomment-462726600
class SpecAPI:
    __slots__ = ()

    def __call__(  # pylint: disable=inconsistent-return-statements
        self,
        *args: Union[Tag, SpecPredicate],
        conformer: Optional[Conformer] = None,
        **kwargs,
    ) -> Spec:
        """Return a new Spec from the given predicate or spec."""
        tag = args[0] if isinstance(args[0], str) else None
        pred = args[0] if tag is None else args[1]

        if isinstance(pred, (frozenset, set)):
            return SetSpec(tag or "set", pred, conformer=conformer)
        elif isinstance(pred, EnumMeta):
            return SetSpec(
                tag or pred.__name__,
                frozenset(
                    chain.from_iterable([mem, mem.name, mem.value] for mem in pred)
                ),
                conformer=conformer or pred,
            )
        elif isinstance(pred, tuple):
            return TupleSpec.from_val(tag, pred, conformer=conformer)
        elif isinstance(pred, list):
            return CollSpec.from_val(tag, pred, conformer=conformer)
        elif isinstance(pred, dict):
            return DictSpec.from_val(tag, pred, conformer=conformer)
        elif isinstance(pred, Spec):
            if conformer is not None:
                return pred.with_conformer(conformer)
            else:
                return pred
        elif callable(pred):
            sig = inspect.signature(pred)
            if sig.return_annotation is Iterator[ErrorDetails]:
                return ValidatorSpec(
                    tag or pred.__name__, cast(ValidatorFn, pred), conformer=conformer
                )
            else:
                return PredicateSpec(
                    tag or pred.__name__, cast(PredicateFn, pred), conformer=conformer
                )
        else:
            raise TypeError(f"Expected some spec predicate; received type {type(pred)}")

    # Spec factories
    any = staticmethod(_anypred)
    all = staticmethod(_allpred)
    bool = staticmethod(_bool)
    bytes = staticmethod(_bytes)
    date = staticmethod(_date)
    every = staticmethod(_every)
    explain = staticmethod(_explain)
    fdef = staticmethod(_fdef)
    inst = staticmethod(_datetime)
    nilable = staticmethod(_nilable)
    num = staticmethod(_num)
    opt = staticmethod(_opt)
    obj = staticmethod(_obj)
    str = staticmethod(_str)
    time = staticmethod(_time)
    uuid = staticmethod(_uuid)

    # Builtin pre-baked specs
    is_any = _every()
    is_bool = _bool()
    is_bytes = _bytes()
    is_date = _date()
    is_false = _bool(allowed_values={False})
    is_float = _num(type_=float)
    is_inst = _datetime()
    is_int = _num(type_=int)
    is_num = _num()
    is_str = _str()
    is_time = _time()
    is_true = _bool(allowed_values={True})
    is_uuid = _uuid()


s = SpecAPI()
