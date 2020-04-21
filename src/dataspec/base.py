import functools
import inspect
import re
import sys
from abc import ABC, abstractmethod
from collections import namedtuple
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
    overload,
)

import attr

T = TypeVar("T")
V = TypeVar("V")


class Invalid:
    """
    Objects of type ``Invalid`` should be emitted from :py:data:`dataspec.Conformer` s
    if they are not able to conform a value or if it is not valid.

    Builtin ``Conformers`` emit the constant value :py:data:`dataspec.INVALID` if they
    cannot conform their input value. This allows for a fast identity check using
    Python's ``is`` operator, though for type checking ``Invalid`` will required.
    """


INVALID = Invalid()


ConformerFn = Callable[[T], Union[V, Invalid]]
Conformer = Union["IConformer", ConformerFn]
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


@overload
def make_conformer(f: None) -> None:
    ...


@overload
def make_conformer(f: Conformer) -> "IConformer":
    ...


def make_conformer(f):
    """
    Coerce ``f`` to a :py:class:`dataspec.IConformer` instance if it is a function or
    return the value otherwise if it is already an ``IConformer`` or ``None``.

    :param f: a function which can be coerced to a :py:class:`dataspec.IConformer` ,
        an existing :py:class:`dataspec.IConformer` instance, or :py:obj:`None`
    :return: a :py:class:`dataspec.IConformer` instance or :py:obj:`None`
    """
    if f is None or isinstance(f, IConformer):
        return f
    elif callable(f):
        return FunctionConformer(f)
    else:
        raise TypeError(f"Cannot coerce object of type {type(f)} to Conformer")


@attr.s(frozen=True, slots=sys.version_info >= (3, 7))
class IConformer(Generic[T, V], ABC):
    """
    Interface for complex conformers.

    In general, library users should strive to use functions of one argument (of type
    :py:obj:`dataspec.ConformerFn`) for conformers passed to :py:func:`dataspec.s` or
    any of its factory methods. For complex cases involving nested data structures,
    it may be necessary to construct a :py:class:`dataspec.IConformer` instance to
    avoid double validation on calls to :py:meth:`dataspec.Spec.conform_valid` .
    """

    @abstractmethod
    def __call__(self, v: T, is_valid: bool = False) -> Union[V, Invalid]:
        """
        Conform the value ``v`` .

        If ``is_valid`` is :py:obj:`True`, the entire value is assumed valid. In
        general, this is probably only useful for determining whether to call
        :py:meth:`dataspec.Spec.conform` or :py:meth:`dataspec.Spec.conform_valid` on
        child Specs.

        For normal cases, callers should provide a simple function of one argument
        and let ``dataspec`` wrap their function automatically.

        :param v: a value to be conformed
        :param is_valid: if :py:obj:`True`, the value can be treated as valid
        :return: the conformed value or an instance of :py:class:`dataspec.Invalid`
            if the value cannot be conformed
        """

    def compose(self, f: Union["Conformer", ConformerFn]) -> "IConformer":
        """
        Return an IConformer instance which is the composition of the current instance
        and the IConformer produced by calling ``make_conformer`` on ``f``.

        :param f: an :py:class:`dataspec.IConformer` or something that can be coerced
            to one
        :return: a new :py:class:`dataspec.IConformer` instance
        """
        new_conformer = make_conformer(f)

        def wrapped_conformer(v, is_valid: bool = False):
            return new_conformer(self(v, is_valid=is_valid), is_valid=is_valid)

        return FunctionConformer(wrapped_conformer)


@attr.s(auto_attribs=True, frozen=True, slots=True)
class FunctionConformer(IConformer):
    """
    A :py:class:`dataspec.IConformer` implementation for wrapping single-argument
    conformer functions.
    """

    f: ConformerFn

    def __call__(self, v: T, is_valid: bool = False) -> Union[V, Invalid]:
        return self.f(v)


@attr.s(auto_attribs=True, slots=True)
class ErrorDetails:
    """
    ``ErrorDetails`` instances encode details about values which fail Spec validation.

    The ``message`` of an ``ErrorDetails`` object gives a human-readable description of
    why the value failed to validate. The ``message`` is intended for logs and debugging
    purposes by application developers. The ``message`` is *not* intended for
    non-technical users and dataspec makes no guarantees that builtin error messages
    could be read and understood by such users.

    ``ErrorDetails`` instances may be emitted for values failing "child" Specs from
    within mapping, collection, or tuple Specs or they may be emitted from simple
    predicate failures. The ``path`` attribute indicates directly which nested element
    triggered the Spec failure.

    ``via`` indicates the list of all Specs that were evaluated up to and include the
    current failure for this particular branch of logic. Tags for sibling Specs to the
    current Spec will not be included in ``via``. Because multiple Specs may be
    evaluated against the same value, it is likely that the number of Tags in ``via``
    will not match the number elements in the ``path``.

    :param message: a string message intended for developers to indicate why the
        input value failed to validate
    :param pred: the input Spec predicate that caused the failure
    :param value: the value that failed to validate
    :param via: a list of :py:data:`dataspec.Tag` s for :py:class:`dataspec.Spec` s
        that were evaluated up to and including the one that caused this failure
    :param path: a list of indexes or keys that indicate the path to the current value
        from the primary value being validated; this is most useful for nested data
        structures such as ``Mapping`` types and collections
    """

    message: str
    pred: SpecPredicate
    value: Any
    via: List[Tag] = attr.ib(factory=list)
    path: List[Any] = attr.ib(factory=list)

    def with_details(self, tag: Tag, loc: Any = NO_ERROR_PATH) -> "ErrorDetails":
        """
        Add the given tag to the ``via`` list and add a key path if one is specified by
        the caller.

        This method mutates the ``via`` and ``path`` list attributes directly rather than
        returning a new ``ErrorDetails`` instance.
        """
        self.via.insert(0, tag)
        if loc is not NO_ERROR_PATH:
            self.path.insert(0, loc)
        return self


@attr.s(auto_attribs=True, slots=True)
class ValidationError(Exception):
    """
    ``ValidationErrors`` are thrown by :py:meth:`dataspec.Spec.validate_ex` and contain
    a sequence of all :py:class:`dataspec.ErrorDetails` instances generated by the Spec
    for the input value.

    :param errors: a sequence of all :py:class:`dataspec.ErrorDetails` instancess
        generated by the Spec for the input value
    """

    errors: Sequence[ErrorDetails]


class Spec(ABC):
    """
    The abstract base class of all Specs.

    All Specs returned by :py:data:`dataspec.s` conform to this interface.
    """

    @property
    @abstractmethod
    def tag(self) -> Tag:  # pragma: no cover
        """
        Return the tag used to identify this Spec.

        Tags are useful for debugging and in validation messages.
        """
        raise NotImplementedError

    @abstractmethod
    def validate(self, v: Any) -> Iterator[ErrorDetails]:  # pragma: no cover
        """
        Validate the value ``v`` against the Spec, yielding successive Spec failures as
        :py:class:`dataspec.ErrorDetails` instances, if any.

        By definition, if ``next(spec.validate(v))`` raises ``StopIteration``, the
        first time it is called, the value is considered valid according to the Spec.

        :param v: a value to validate
        :return: an iterator of Spec failures as :py:class:`dataspec.ErrorDetails`
            instances, if any
        """
        raise NotImplementedError

    def validate_ex(self, v: Any) -> None:
        """
        Validate the value ``v`` against the Spec, throwing a
        :py:class:`dataspec.ValidationError` containing a list of all of the Spec
        failures for ``v`` , if any. Returns :py:obj:`None` otherwise.

        :param v: a value to validate
        :return: :py:obj:`None`
        """
        errors = list(self.validate(v))
        if errors:
            raise ValidationError(errors)

    def is_valid(self, v: Any) -> bool:
        """
        Returns :py:obj:`True` if ``v`` is valid according to the Spec, otherwise
        returns :py:obj:`False` .

        :param v: a value to validate
        :return: :py:obj:`True` if the value is valid according to the Spec, otherwise
            :py:obj:`False`
        """
        try:
            next(self.validate(v))
        except StopIteration:
            return True
        else:
            return False

    @property
    def conformer(self) -> Optional[IConformer]:
        """Return the custom conformer attached to this Spec, if one is defined."""
        return None

    def conform(self, v: Any):
        """
        Conform ``v`` to the Spec, returning the possibly conformed value or an
        instance of :py:class:`dataspec.Invalid` if the value cannot be conformed.

        :param v: a value to conform
        :return: a conformed value or a :py:class:`dataspec.Invalid` instance if the
            input value could not be conformed
        """
        if self.is_valid(v):
            if self.conformer is None:
                return v
            return self.conformer(v, is_valid=True)  # pylint: disable=not-callable
        else:
            return INVALID

    def conform_valid(self, v: Any):
        """
        Conform ``v`` to the Spec without checking if v is valid first and return the
        possibly conformed value or ``INVALID`` if the value cannot be conformed.

        This function should be used only if ``v`` has already been check for validity.

        :param v: a *validated* value to conform
        :return: a conformed value or a :py:class:`dataspec.Invalid` instance if the
            input value could not be conformed
        """
        if self.conformer is None:
            return v
        return self.conformer(v, is_valid=True)  # pylint: disable=not-callable

    def compose_conformer(self, conformer: Conformer) -> "Spec":
        """
        Return a new Spec instance with a new conformer which is the composition of the
        ``conformer`` and the current conformer for this Spec instance.

        If the current Spec instance has a custom conformer, this is equivalent to
        calling ``spec.with_conformer(lambda v: new_conformer(spec.conformer(v)))`` .
        If the current Spec instance has no custom conformer, this is equivalent to
        calling :py:meth:`dataspec.Spec.with_conformer` with ``conformer`` .

        To completely replace the conformer for this Spec instance, use
        :py:meth:`dataspec.Spec.with_conformer` .

        This method does not modify the current Spec instance.

        :param conformer: a conformer to compose with the conformer of the current
            Spec instance
        :return: a copy of the current Spec instance with the new composed conformer
        """
        existing_conformer = self.conformer

        if existing_conformer is None:
            return self.with_conformer(conformer)

        return self.with_conformer(existing_conformer.compose(conformer))

    def with_conformer(self, conformer: Optional[Conformer]) -> "Spec":
        """
        Return a new Spec instance with the new conformer, replacing any custom
        conformers.

        If ``conformer`` is :py:obj:`None` , the returned Spec will have no custom
        conformer.

        To return a copy of the current Spec with a composition of the current
        Spec instance, use :py:meth:`dataspec.Spec.compose_conformer` .

        :param conformer: a conformer to replace the conformer of the current Spec
            instance or :py:obj:`None` to remove the conformer associated with this

        :return: a copy of the current Spec instance with new conformer
        """
        return attr.evolve(self, conformer=conformer)

    def with_tag(self, tag: Tag) -> "Spec":
        """
        Return a new Spec instance with the new tag applied.

        This method does not modify the current Spec instance.

        :param tag: a new tag to use for the new Spec
        :return: a copy of the current Spec instance with the new tag applied
        """
        return attr.evolve(self, tag=tag)


@attr.s(auto_attribs=True, frozen=True, slots=True)
class ValidatorSpec(Spec):
    """Validator Specs yield richly detailed errors from their validation functions and
    can be useful for answering more detailed questions about their their input data
    than a simple predicate function."""

    tag: Tag
    _validate: ValidatorFn
    conformer: Optional[IConformer] = attr.ib(default=None, converter=make_conformer)  # type: ignore[misc]  # noqa

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
            tag, do_validate, compose_spec_conformers(*specs, conform_final=conformer)
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
    conformer: Optional[IConformer] = attr.ib(default=None, converter=make_conformer)  # type: ignore[misc]  # noqa

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


@attr.s(auto_attribs=True, frozen=True, slots=True)
class CollSpec(Spec):
    tag: Tag
    _spec: Spec
    conformer: Optional[IConformer] = attr.ib(default=None, converter=make_conformer)  # type: ignore[misc]  # noqa
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
        spec = make_spec(sequence[0])
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
                f"Collection length {{value}} exceeds max length {maxlength}",
                convert_value=len,
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
                f"Collection length {{value}} does not meet minimum length {minlength}",
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

        class CollConformer(IConformer):
            def __call__(self, v, is_valid: bool = False):
                conform = spec.conform_valid if is_valid else spec.conform
                return (out_type or type(v))(conform(e) for e in v)  # noqa

        conform_coll = CollConformer()

        return cls(
            tag or "coll",
            spec=spec,
            conformer=conform_coll.compose(conformer)
            if conformer is not None
            else conform_coll,
            out_type=out_type,
            validate_coll=validate_coll,
        )

    def validate(self, v) -> Iterator[ErrorDetails]:
        if self._validate_coll:
            yield from _enrich_errors(self._validate_coll.validate(v), self.tag)

        for i, e in enumerate(v):
            yield from _enrich_errors(self._spec.validate(e), self.tag, i)


# In Python 3.6, you cannot inherit directly from Generic with slotted classes:
# https://github.com/python-attrs/attrs/issues/313
@attr.s(auto_attribs=True, frozen=True, slots=sys.version_info >= (3, 7))
class OptionalKey(Generic[T]):
    key: T


@attr.s(auto_attribs=True, frozen=True, slots=True)
class DictSpec(Spec):
    tag: Tag
    _reqkeyspecs: Mapping[Any, Spec] = attr.ib(factory=dict)
    _optkeyspecs: Mapping[Any, Spec] = attr.ib(factory=dict)
    conformer: Optional[IConformer] = attr.ib(default=None, converter=make_conformer)  # type: ignore[misc]  # noqa

    @classmethod
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[str, SpecPredicate],
        conformer: Optional[Conformer] = None,
    ):
        reqkeys = {}
        optkeys: MutableMapping[Any, Spec] = {}
        for k, v in kvspec.items():
            if isinstance(k, OptionalKey):
                optkeys[k.key] = make_spec(v)
            else:
                reqkeys[k] = make_spec(v)

        class DictConformer(IConformer):
            def __call__(self, d: Mapping, is_valid: bool = False) -> Mapping:
                return self.conform_valid(d) if is_valid else self.conform(d)

            def conform(self, d: Mapping) -> Mapping:
                conformed_d = {}
                for k, spec in reqkeys.items():
                    conformed_d[k] = spec.conform(d[k])

                for k, spec in optkeys.items():
                    if k in d:
                        conformed_d[k] = spec.conform(d[k])

                return conformed_d

            def conform_valid(self, d: Mapping) -> Mapping:
                conformed_d = {}
                for k, spec in reqkeys.items():
                    conformed_d[k] = spec.conform_valid(d[k])

                for k, spec in optkeys.items():
                    if k in d:
                        conformed_d[k] = spec.conform_valid(d[k])

                return conformed_d

        conform_mapping = DictConformer()

        return cls(
            tag or "map",
            reqkeyspecs=reqkeys,
            optkeyspecs=optkeys,
            conformer=conform_mapping.compose(conformer)
            if conformer is not None
            else conform_mapping,
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
                message="Value is not a mapping type",
                pred=self,
                value=d,
                via=[self.tag],
            )
            return

        for k, vspec in self._optkeyspecs.items():
            if k in d:
                yield from _enrich_errors(vspec.validate(d[k]), self.tag, k)


class ObjectSpec(DictSpec):
    @classmethod
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[str, SpecPredicate],
        conformer: Conformer = None,
    ):
        def conform_object(_: Any):
            raise TypeError("Cannot use a default conformer for an Object")

        return super().from_val(tag, kvspec).with_conformer(conformer or conform_object)

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


def _enum_conformer(e: EnumMeta) -> Conformer:
    """Create a conformer for Enum types which accepts Enum instances, Enum values,
    and Enum names."""

    def conform_enum(v) -> Union[EnumMeta, Invalid]:
        try:
            return e(v)
        except ValueError:
            try:
                return e[v]
            except KeyError:
                return INVALID

    return conform_enum


@attr.s(auto_attribs=True, frozen=True, slots=True)
class SetSpec(Spec):
    tag: Tag
    _values: Union[Set, FrozenSet]
    conformer: Optional[IConformer] = attr.ib(default=None, converter=make_conformer)  # type: ignore[misc]  # noqa

    def validate(self, v) -> Iterator[ErrorDetails]:
        if v not in self._values:
            yield ErrorDetails(
                message=f"Value '{v}' not in '{self._values}'",
                pred=self._values,
                value=v,
                via=[self.tag],
            )

    @classmethod
    def from_enum(
        cls, tag: Optional[Tag], pred: EnumMeta, conformer: Optional[Conformer] = None
    ):
        return cls(
            tag or pred.__name__,
            frozenset(
                chain.from_iterable(
                    [mem, mem.name, mem.value] for mem in pred  # type: ignore[var-annotated]  # noqa
                )
            ),
            conformer=compose_conformers(
                _enum_conformer(pred), *filter(None, (conformer,)),
            ),
        )


@attr.s(auto_attribs=True, frozen=True, slots=True)
class TupleSpec(Spec):
    tag: Tag
    _pred: Tuple[SpecPredicate, ...]
    _specs: Tuple[Spec, ...]
    conformer: Optional[IConformer] = attr.ib(default=None, converter=make_conformer)  # type: ignore[misc]  # noqa
    _namedtuple: Optional[Type[NamedTuple]] = None

    @classmethod
    def from_val(
        cls,
        tag: Optional[Tag],
        pred: Tuple[SpecPredicate, ...],
        conformer: Conformer = None,
    ):
        specs = tuple(make_spec(e_pred) for e_pred in pred)

        spec_tags = tuple(re.sub(_MUNGE_NAMES, "_", spec.tag) for spec in specs)
        if tag is not None and len(specs) == len(set(spec_tags)):
            namedtuple_type = namedtuple(  # type: ignore
                re.sub(_MUNGE_NAMES, "_", tag), spec_tags
            )
        else:
            namedtuple_type = None  # type: ignore

        class TupleConformer(IConformer):
            def __call__(
                self, v: Tuple, is_valid: bool = False
            ) -> Union[Tuple, NamedTuple]:
                return self.conform_valid(v) if is_valid else self.conform(v)

            def conform(self, v: Tuple) -> Tuple:
                return ((namedtuple_type and namedtuple_type._make) or tuple)(
                    spec.conform(v) for spec, v in zip(specs, v)
                )

            def conform_valid(self, v: Tuple) -> Tuple:
                return ((namedtuple_type and namedtuple_type._make) or tuple)(
                    spec.conform_valid(v) for spec, v in zip(specs, v)
                )

        conform_tuple = TupleConformer()

        return cls(
            tag or "tuple",
            pred=pred,
            specs=specs,
            conformer=conform_tuple.compose(conformer)
            if conformer is not None
            else conform_tuple,
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


def _enrich_errors(
    errors: Iterable[ErrorDetails], tag: Tag, loc: Any = NO_ERROR_PATH
) -> Iterable[ErrorDetails]:
    """
    Enrich the stream of errors with tag and location information.

    Tags are useful for determining which specs were evaluated to produce the error.
    Location information can help callers pinpoint exactly where in their data structure
    the error occurred. If no location information is relevant for the error (perhaps
    for a scalar spec type), then the default ``NO_ERROR_PATH`` should be used.
    """
    for error in errors:
        yield error.with_details(tag, loc=loc)


def compose_conformers(*conformers: Conformer) -> Conformer:
    """
    Return a single conformer which is the composition of the input conformers.

    If a single conformer is given, return the conformer.
    """

    if len(conformers) == 1:
        return conformers[0]

    def do_conform(v):
        conformed_v = v
        for conform in conformers:
            conformed_v = conform(conformed_v)
            if conformed_v is INVALID:
                break
        return conformed_v

    return do_conform


def compose_spec_conformers(
    *specs: Spec, conform_final: Optional[Conformer] = None
) -> Conformer:
    """
    Return a single conformer which is the composition of the conformers from each of
    the child specs.

    Apply the ``conform_final`` conformer on the final return from the composition, if
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


_MUNGE_NAMES = re.compile(r"[\s|-]")


def _complement(pred: PredicateFn) -> PredicateFn:
    """Return the complement to the predicate function ``pred``."""

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
    **fmtkwargs,
) -> Callable[[PredicateFn], ValidatorFn]:
    """
    Decorator which converts a simple predicate function to a validator function.

    If the wrapped predicate returns a truthy value, the wrapper function will emit a
    single :py:class:`dataspec.base.ErrorDetails` object with the ``message`` format
    string interpolated with the failing value as ``value`` (possibly subject to
    conversion by the optional keyword argument ``convert_value``) and any other
    key/value pairs from ``fmtkwargs``.

    If ``complement`` keyword argument is ``True``, the return value of the decorated
    predicate will be converted as by Python's ``not`` operator and the return value
    will be used to determine whether or not an error has occurred. This is a
    convenient way to negate a predicate function without having to modify the function
    itself.

    :param message: a format string which will be the base error message in the
        resulting :py:class:`dataspec.base.ErrorDetails` object
    :param complement: if :py:obj:``True``, the boolean complement of the decorated
        function's return value will indicate failure
    :param convert_value: an optional function which can convert the value before
        interpolating it into the error message
    :param fmtkwargs: optional key/value pairs which will be interpolated into
        the error message
    :return: a validator function which can be fed into a
        :py:class:`dataspec.base.ValidatorSpec`
    """

    assert "value" not in fmtkwargs, "Key 'value' is not allowed in pred format kwargs"

    def to_validator(pred: PredicateFn) -> ValidatorFn:
        pred = _complement(pred) if complement else pred

        @functools.wraps(pred)
        def validator(v) -> Iterable[ErrorDetails]:
            if pred(v):
                yield ErrorDetails(
                    message=message.format(value=convert_value(v), **fmtkwargs),
                    pred=pred,
                    value=v,
                )

        validator.is_validator_fn = True  # type: ignore
        return validator

    return to_validator


def type_spec(
    tag: Optional[Tag] = None, tp: Type = object, conformer: Optional[Conformer] = None
) -> Spec:
    """Return a spec that validates inputs are instances of tp."""

    @pred_to_validator(f"Value '{{value}}' is not a {tp.__name__}", complement=True)
    def is_instance_of_type(v: Any) -> bool:
        return isinstance(v, tp)

    return ValidatorSpec(
        tag or f"is_{tp.__name__}", is_instance_of_type, conformer=conformer
    )


def make_spec(  # pylint: disable=inconsistent-return-statements  # noqa: MC0001
    *args: Union[Tag, SpecPredicate], conformer: Optional[Conformer] = None
) -> Spec:
    """
    Create a new Spec instance from a :py:obj:`dataspec.base.SpecPredicate`.

    Specs may be created from a variety of functions. Functions which take a single
    argument and return a boolean value can produce simple Specs. For more detailed
    error messages, callers can provide a function which takes a single argument and
    yields consecutive ``ErrorDetails`` (in particular, the return annotation should
    be *exactly* ``Iterator[ErrorDetails]`` ).

    Specs may be created from Python types, in which case a Spec will be produced
    that performs an :py:func:`isinstance` check. :py:obj:`None` may be provided as
    a shortcut for ``type(None)`` . To specify a nilable value, you should use
    :py:meth:`dataspec.SpecAPI.nilable` instead.

    Specs may be created for enumerated types using a Python ``set`` or ``frozenset``
    or using Python :py:class:`enum.Enum` types. Specs created for enumerated types
    based on :py:class:`enum.Enum` values validate the Enum name, value, or Enum
    singleton and conform the the Enum singleton.

    Specs may be created for homogeneous collections using a Python ``list`` type.
    Callers can specify a few additional parameters for collection specs by providing
    an optional dictionary of values in the second position of the input ``list``.
    To validate the input collection type, provide the ``"kind"`` key with a collection
    type. To specify the output type used by the default conformer, provide the
    ``"into"`` keyword with a collection type.

    Specs may be created for mapping types using a Python ``dict`` type. The input
    ``dict`` maps key values (most often strings) to Specs (or values which can be
    coerced to Specs by this function). Mapping Specs validate that an input map
    contains the required keys and that the value associated with the key matches
    the given Spec. Mapping specs can be specified with optional keys by wrapping
    the optional key with ``s.opt``. If that key is present in the input value, it
    will be validated against the given Spec. However, if the input value does not
    contain the optional key, the map is still considered valid. Mapping Specs do not
    assert that input values contain *only* the keys given in the Spec -- this is by
    design.

    Specs may be created for heterogeneous collections using a Python ``tuple`` type.
    Tuple Specs will conform into ``collections.NamedTuple`` s, with each element in
    the input tuple being validated and conformed to the corresponding element in the
    Spec.

    :param tag: an optional :py:data:`dataspec.Tag` for the resulting spec
    :param pred: a value which can be be converted into a :py:class:`dataspec.Spec`
    :param conformer: an optional :py:data:`dataspec.Conformer` for the value
    :return: a :py:class:`dataspec.base.Spec` instance
    """
    tag = args[0] if isinstance(args[0], str) else None

    try:
        pred = args[0] if tag is None else args[1]
    except IndexError:
        raise TypeError("Expected some spec predicate; received only a Tag")

    if isinstance(pred, (frozenset, set)):
        return SetSpec(tag or "set", pred, conformer=conformer)
    elif isinstance(pred, EnumMeta):
        return SetSpec.from_enum(tag, pred, conformer=conformer)
    elif isinstance(pred, tuple):
        return TupleSpec.from_val(tag, pred, conformer=conformer)
    elif isinstance(pred, list):
        return CollSpec.from_val(tag, pred, conformer=conformer)
    elif isinstance(pred, dict):
        return DictSpec.from_val(tag, pred, conformer=conformer)
    elif isinstance(pred, Spec):
        if tag is not None:
            pred = pred.with_tag(tag)
        if conformer is not None:
            pred = pred.with_conformer(conformer)
        return pred
    elif isinstance(pred, type):
        return type_spec(tag, pred, conformer=conformer)
    elif callable(pred):
        try:
            sig: Optional[inspect.Signature] = inspect.signature(pred)
        except (TypeError, ValueError):
            # Some builtins may not be inspectable
            sig = None

        if (
            sig is not None and sig.return_annotation is Iterator[ErrorDetails]
        ) or getattr(pred, "is_validator_fn", False):
            return ValidatorSpec(
                tag or pred.__name__, cast(ValidatorFn, pred), conformer=conformer
            )
        else:
            return PredicateSpec(
                tag or pred.__name__, cast(PredicateFn, pred), conformer=conformer
            )
    elif pred is None:
        return type_spec(tag, type(None), conformer=conformer)
    else:
        raise TypeError(f"Expected some spec predicate; received type {type(pred)}")
