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
    Collection,
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

# In Python 3.6, you cannot inherit directly from Generic with slotted classes:
# https://github.com/python-attrs/attrs/issues/313
_USE_SLOTS_FOR_GENERIC = sys.version_info >= (3, 7)

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


Conformer = Callable[[T], Union[V, Invalid]]
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


T_input = TypeVar("T_input")
T_conformed = TypeVar("T_conformed")

# Generic types used for composing and replacing conformers
T_newinput = TypeVar("T_newinput")
T_composed = TypeVar("T_composed")
T_replaced = TypeVar("T_replaced")


class Spec(Generic[T_input, T_conformed], ABC):
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
        returns :py:obj:`False`.

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
    def conformer(
        self,
    ) -> Optional[Conformer[T_input, T_conformed]]:  # pragma: no cover
        """Return the custom conformer attached to this Spec, if one is defined."""
        return None

    @overload
    def conform(self: "Spec[T_input, T_input]", v: Any) -> Union[T_input, Invalid]:
        ...

    @overload  # noqa: F811
    def conform(
        self: "Spec[T_input, T_conformed]", v: Any
    ) -> Union[T_conformed, Invalid]:
        ...

    def conform(self, v: Any) -> Union[T_input, T_conformed, Invalid]:  # noqa: F811
        """
        Conform ``v`` to the Spec, returning the possibly conformed value or an
        instance of :py:class:`dataspec.Invalid` if the value is invalid cannot
        be conformed.

        Exceptions arising from calling :py:attr:`dataspec.Spec.conformer` with ``v``
        will be raised from this method.

        :param v: a value to conform
        :return: a conformed value or a :py:class:`dataspec.Invalid` instance if the
            input value could not be conformed
        """
        if self.is_valid(v):
            return self.conform_valid(v)  # pylint: disable=not-callable
        else:
            return INVALID

    @overload
    def conform_valid(self: "Spec[T_input, T_input]", v: T_input) -> T_input:
        ...

    @overload  # noqa: F811
    def conform_valid(
        self: "Spec[T_input, T_conformed]", v: T_input
    ) -> Union[T_conformed, Invalid]:
        ...

    def conform_valid(
        self, v: T_input
    ) -> Union[T_input, T_conformed, Invalid]:  # noqa: F811
        """
        Conform ``v`` to the Spec without checking if v is valid first and return the
        possibly conformed value or ``INVALID`` if the value cannot be conformed.

        This function should be used only if ``v`` has already been check for validity.

        Exceptions arising from calling :py:attr:`dataspec.Spec.conformer` with ``v``
        will be raised from this method.

        :param v: a *validated* value to conform
        :return: a conformed value or a :py:class:`dataspec.Invalid` instance if the
            input value could not be conformed
        """
        if self.conformer is None:
            return v
        return self.conformer(v)  # pylint: disable=not-callable

    @overload
    def compose_conformer(
        self: "Spec[T_input, T_input]", conformer: Conformer[T_input, T_replaced]
    ) -> "Spec[T_input, T_replaced]":
        ...

    @overload  # noqa: F811
    def compose_conformer(
        self: "Spec[T_input, T_conformed]",
        conformer: Conformer[T_conformed, T_composed],
    ) -> "Spec[T_input, T_composed]":
        ...

    def compose_conformer(self, conformer):  # noqa: F811
        """
        Return a new Spec instance with a new conformer which is the composition of the
        ``conformer`` and the current conformer for this Spec instance.

        If the current Spec instance has a custom conformer, this is equivalent to
        calling ``spec.with_conformer(lambda v: conformer(spec.conformer(v)))``.
        If the current Spec instance has no custom conformer, this is equivalent to
        calling :py:meth:`dataspec.Spec.with_conformer` with ``conformer``.

        To completely replace the conformer for this Spec instance, use
        :py:meth:`dataspec.Spec.with_conformer`.

        This method does not modify the current Spec instance.

        :param conformer: a conformer to compose with the conformer of the current
            Spec instance
        :return: a copy of the current Spec instance with the new composed conformer
        """
        existing_conformer = self.conformer

        if existing_conformer is None:
            return self.with_conformer(conformer)

        def conform_spec(v: T_input) -> Union[T_composed, Invalid]:
            assert existing_conformer is not None
            return conformer(existing_conformer(v))  # pylint: disable=not-callable

        return self.with_conformer(conform_spec)

    @overload
    def with_conformer(self, conformer: None) -> "Spec[T_input, T_input]":
        ...

    @overload  # noqa: F811
    def with_conformer(
        self, conformer: Conformer[T_newinput, T_replaced]
    ) -> "Spec[T_newinput, T_replaced]":
        ...

    def with_conformer(self, conformer):  # noqa: F811
        """
        Return a new Spec instance with the new conformer, replacing any custom
        conformers.

        If ``conformer`` is :py:obj:`None` , the returned Spec will have no custom
        conformer.

        To return a copy of the current Spec with a composition of the current
        Spec instance, use :py:meth:`dataspec.Spec.compose_conformer`.

        :param conformer: a conformer to replace the conformer of the current Spec
            instance or :py:obj:`None` to remove the conformer associated with this
        :return: a copy of the current Spec instance with new conformer
        """
        return attr.evolve(self, conformer=conformer)

    def with_tag(self, tag: Tag) -> "Spec[T_input, T_conformed]":
        """
        Return a new Spec instance with the new tag applied.

        This method does not modify the current Spec instance.

        :param tag: a new tag to use for the new Spec
        :return: a copy of the current Spec instance with the new tag applied
        """
        return attr.evolve(self, tag=tag)


@attr.s(auto_attribs=True, frozen=True, slots=_USE_SLOTS_FOR_GENERIC)
class ValidatorSpec(Spec[T_input, T_conformed]):
    """Validator Specs yield richly detailed errors from their validation functions and
    can be useful for answering more detailed questions about their their input data
    than a simple predicate function."""

    tag: Tag
    _validate: ValidatorFn
    conformer: Optional[Conformer[T_input, T_conformed]] = None

    def validate(self, v: Any) -> Iterator[ErrorDetails]:
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

        def do_validate(v: Any) -> Iterator[ErrorDetails]:
            for spec in specs:
                yield from spec.validate(v)

        return cls(
            tag, do_validate, compose_spec_conformers(*specs, conform_final=conformer)
        )


@attr.s(auto_attribs=True, frozen=True, slots=_USE_SLOTS_FOR_GENERIC)
class PredicateSpec(Spec[T_input, T_conformed]):
    """
    Predicate Specs are useful for validating data with a boolean predicate function.

    Predicate specs can be useful for validating simple yes/no questions about data, but
    the errors they can produce are limited by the nature of the predicate return value.
    """

    tag: Tag
    _pred: PredicateFn
    conformer: Optional[Conformer[T_input, T_conformed]] = None

    def validate(self, v: Any) -> Iterator[ErrorDetails]:
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


T_collinput = TypeVar("T_collinput", bound=Iterable)


@attr.s(auto_attribs=True, frozen=True, slots=_USE_SLOTS_FOR_GENERIC)
class CollSpec(Spec[T_collinput, T_conformed]):
    tag: Tag
    _spec: Spec
    conformer: Optional[Conformer[T_collinput, T_conformed]] = None
    _out_type: Optional[Type] = None
    _validate_coll: Optional[ValidatorSpec] = None

    @classmethod
    @overload
    def from_val(
        cls,
        tag: Optional[Tag],
        sequence: Sequence[Union[SpecPredicate, Mapping[str, Any]]],
        conformer: None = None,
    ) -> Spec[Iterable, Collection]:
        ...

    @classmethod  # noqa: F811
    @overload
    def from_val(
        cls,
        tag: Optional[Tag],
        sequence: Sequence[Union[SpecPredicate, Mapping[str, Any]]],
        conformer: Conformer[T_collinput, T_composed],
    ) -> Spec[T_collinput, T_composed]:
        ...

    @classmethod  # noqa: MC0001, F811
    def from_val(
        cls,
        tag: Optional[Tag],
        sequence: Sequence[Union[SpecPredicate, Mapping[str, Any]]],
        conformer: Optional[Conformer] = None,
    ) -> Spec:
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

        def conform_coll(v: T_collinput) -> Iterable:
            return (out_type or type(v))(spec.conform(e) for e in v)  # type: ignore[call-arg]  # noqa

        return cls(
            tag or "coll",
            spec=spec,
            conformer=compose_conformers(conform_coll, *filter(None, (conformer,))),
            out_type=out_type,
            validate_coll=validate_coll,
        )

    def validate(self, v: Any) -> Iterator[ErrorDetails]:
        if self._validate_coll:
            yield from _enrich_errors(self._validate_coll.validate(v), self.tag)

        for i, e in enumerate(v):
            yield from _enrich_errors(self._spec.validate(e), self.tag, i)


@attr.s(auto_attribs=True, frozen=True, slots=_USE_SLOTS_FOR_GENERIC)
class OptionalKey(Generic[T]):
    key: T


T_mapinput = TypeVar("T_mapinput", bound=Mapping)


@attr.s(auto_attribs=True, frozen=True, slots=_USE_SLOTS_FOR_GENERIC)
class DictSpec(Spec[T_mapinput, T_conformed]):
    tag: Tag
    _reqkeyspecs: Mapping[Any, Spec] = attr.ib(factory=dict)
    _optkeyspecs: Mapping[Any, Spec] = attr.ib(factory=dict)
    conformer: Optional[Conformer[T_mapinput, T_conformed]] = None

    @classmethod
    @overload
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[str, SpecPredicate],
        conformer: None = None,
    ) -> Spec[T_mapinput, Mapping]:
        ...

    @classmethod  # noqa: F811
    @overload
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[str, SpecPredicate],
        conformer: Conformer[Mapping, T_conformed],
    ) -> Spec[T_mapinput, T_conformed]:
        ...

    @classmethod  # noqa: F811
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[str, SpecPredicate],
        conformer: Optional[Conformer] = None,
    ) -> Spec:
        reqkeys = {}
        optkeys: MutableMapping[Any, Spec] = {}
        for k, v in kvspec.items():
            if isinstance(k, OptionalKey):
                optkeys[k.key] = make_spec(v)
            else:
                reqkeys[k] = make_spec(v)

        def conform_mapping(d: Mapping) -> Mapping:
            conformed_d = {}
            for k, spec in reqkeys.items():
                conformed_d[k] = spec.conform(d[k])

            for k, spec in optkeys.items():
                if k in d:
                    conformed_d[k] = spec.conform(d[k])

            return conformed_d

        return cls(
            tag or "map",
            reqkeyspecs=reqkeys,
            optkeyspecs=optkeys,
            conformer=compose_conformers(conform_mapping, *filter(None, (conformer,))),
        )

    def validate(
        self, d: Any
    ) -> Iterator[ErrorDetails]:  # pylint: disable=arguments-differ
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


class ObjectSpec(DictSpec[T_input, T_conformed]):
    @classmethod
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[str, SpecPredicate],
        conformer: Optional[Conformer] = None,
    ):
        """
        Return a Spec for an arbitrary object instance.

        Overwrite the default conformer provided for ``DictSpec`` s, since it does not
        make sense for objects.
        """
        return super().from_val(tag, kvspec).with_conformer(conformer)

    def validate(
        self, o: Any
    ) -> Iterator[ErrorDetails]:  # pylint: disable=arguments-differ
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


def _enum_conformer(e: EnumMeta) -> Conformer[Any, EnumMeta]:
    """Create a conformer for Enum types which accepts Enum instances, Enum values,
    and Enum names."""

    def conform_enum(v: Any) -> Union[EnumMeta, Invalid]:
        try:
            return e(v)
        except ValueError:
            try:
                return e[v]
            except KeyError:
                return INVALID

    return conform_enum


@attr.s(auto_attribs=True, frozen=True, slots=_USE_SLOTS_FOR_GENERIC)
class SetSpec(Spec[T_input, T_conformed]):
    tag: Tag
    _values: Union[Set, FrozenSet]
    conformer: Optional[Conformer[T_input, T_conformed]] = None

    def validate(self, v: Any) -> Iterator[ErrorDetails]:
        if v not in self._values:
            yield ErrorDetails(
                message=f"Value '{v}' not in '{self._values}'",
                pred=self._values,
                value=v,
                via=[self.tag],
            )

    @classmethod
    @overload
    def from_enum(
        cls, tag: Optional[Tag], pred: EnumMeta, conformer: None = None
    ) -> Spec[T_input, EnumMeta]:
        ...

    @classmethod  # noqa: F811
    @overload
    def from_enum(
        cls,
        tag: Optional[Tag],
        pred: EnumMeta,
        conformer: Conformer[T_input, T_conformed],
    ) -> Spec[T_input, T_conformed]:
        ...

    @classmethod  # noqa: F811
    def from_enum(
        cls, tag: Optional[Tag], pred: EnumMeta, conformer: Optional[Conformer] = None
    ) -> Spec:
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


T_conformed_tuple = TypeVar("T_conformed_tuple", bound=Union[Tuple, NamedTuple])


@attr.s(auto_attribs=True, frozen=True, slots=_USE_SLOTS_FOR_GENERIC)
class TupleSpec(Spec[T_input, T_conformed]):
    tag: Tag
    _pred: Tuple[SpecPredicate, ...]
    _specs: Tuple[Spec, ...]
    conformer: Optional[Conformer[T_input, T_conformed]] = None
    _namedtuple: Optional[Type[NamedTuple]] = None

    @classmethod
    @overload
    def from_val(
        cls,
        tag: Optional[Tag],
        pred: Tuple[SpecPredicate, ...],
        conformer: None = None,
    ) -> Spec[T_input, Union[Tuple, NamedTuple]]:
        ...

    @classmethod  # noqa: F811
    @overload
    def from_val(
        cls,
        tag: Optional[Tag],
        pred: Tuple[SpecPredicate, ...],
        conformer: Conformer[T_input, T_conformed],
    ) -> Spec[T_input, T_conformed]:
        ...

    @classmethod  # noqa: F811
    def from_val(
        cls,
        tag: Optional[Tag],
        pred: Tuple[SpecPredicate, ...],
        conformer: Optional[Conformer] = None,
    ) -> Spec:
        specs = tuple(make_spec(e_pred) for e_pred in pred)

        spec_tags = tuple(re.sub(_MUNGE_NAMES, "_", spec.tag) for spec in specs)
        namedtuple_type: Optional[Type[NamedTuple]]
        if tag is not None and len(specs) == len(set(spec_tags)):
            namedtuple_type = namedtuple(  # type: ignore
                re.sub(_MUNGE_NAMES, "_", tag), spec_tags
            )
        else:
            namedtuple_type = None

        def conform_tuple(v: Union[Tuple, NamedTuple]) -> Union[Tuple, NamedTuple]:
            return ((namedtuple_type and namedtuple_type._make) or tuple)(
                spec.conform(v) for spec, v in zip(specs, v)
            )

        return cls(
            tag or "tuple",
            pred=pred,
            specs=specs,
            conformer=compose_conformers(conform_tuple, *filter(None, (conformer,))),
            namedtuple=namedtuple_type,
        )

    def validate(
        self, t: Any
    ) -> Iterator[ErrorDetails]:  # pylint: disable=arguments-differ
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
            if conformed_v is INVALID or isinstance(conformed_v, Invalid):
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

    This function bypasses the :py:meth:`dataspec.Spec.conform` method and accesses
    :py:attr:`dataspec.Spec.conformer` directly.
    """

    return compose_conformers(
        *filter(None, chain((spec.conformer for spec in specs), (conform_final,)))
    )


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


@overload
def type_spec(tag: Optional[Tag], tp: Type, conformer: None,) -> Spec[T_input, T_input]:
    ...


@overload
def type_spec(
    tag: Optional[Tag], tp: Type, conformer: Conformer[T_input, T_conformed],
) -> Spec[T_input, T_conformed]:
    ...


def type_spec(
    tag: Optional[Tag] = None, tp: Type = object, conformer: Optional[Conformer] = None
):
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
    a shortcut for ``type(None)``. To specify a nilable value, you should use
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

    Specs may be be created from existing Specs. If an existing :py:class:`datspec.Spec`
    instance is given, that Spec will be returned without modification. If a tag is
    given, a new Spec will be created from the existing Spec with the new tag. If a
    conformer is given, a new Spec will be created from the existing Spec with the new
    conformer (*replacing* any conformer on the existing Spec, rather than composing).
    If both a new tag and conformer are given, a new Spec will be returned with both
    the new tag and conformer.

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
