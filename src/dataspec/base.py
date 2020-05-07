import functools
import inspect
import re
import sys
from abc import ABC, abstractmethod
from collections import defaultdict, namedtuple
from enum import EnumMeta
from itertools import chain
from typing import (
    Any,
    Callable,
    FrozenSet,
    Generic,
    Hashable,
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
ObjectSpecKey = Union[str, "OptionalKey[str]"]
PredicateFn = Callable[[Any], bool]
ValidatorFn = Callable[[Any], Iterable["ErrorDetails"]]
Tag = str

SpecPredicate = Union[  # type: ignore
    Mapping[Hashable, "SpecPredicate"],  # type: ignore
    Mapping[ObjectSpecKey, "SpecPredicate"],  # type: ignore
    Tuple["SpecPredicate", ...],  # type: ignore
    List["SpecPredicate"],  # type: ignore
    FrozenSet[Any],
    Set[Any],
    Type[Any],
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

    def as_map(self) -> Mapping[str, Union[str, List[str]]]:
        """
        Return a map of the fields of this instance converted to strings or a list of
        strings, suitable for being converted into JSON.

        The :py:attr:`dataspec.ErrorDetails.pred` attribute will be stringified in one
        of three ways. If ``pred`` is a :py:class:`dataspec.Spec` instance, ``pred``
        will be converted to the :py:attr:`dataspec.Spec.tag` of that instance. If
        ``pred`` is a callable (as by :py:func:`callable`) , it will be converted to
        the ``__name__`` of the callable. Otherwise, ``pred`` will be passed directly
        to :py:func:`str`.

        ``message`` will remain a string. ``value`` will be passed to :py:func:`str`
        directly. ``via`` and ``path`` will be returned as a list of strings.

        :return: a mapping of string keys to strings or lists of strings
        """
        if isinstance(self.pred, Spec):
            pred = self.pred.tag
        elif callable(self.pred):
            # Lambdas just have the name '<lambda>', but there's not much
            # we can do about that
            pred = self.pred.__name__
        else:
            pred = str(self.pred)

        return {
            "message": self.message,
            "pred": pred,
            "value": str(self.value),
            "via": list(self.via),
            "path": [str(e) for e in self.path],
        }


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

    def validate_all(self, v: Any) -> List[ErrorDetails]:  # pragma: no cover
        """
        Validate the value ``v`` against the Spec, returning a :py:class:`list` of all
        Spec failures of ``v`` as :py:class:`dataspec.ErrorDetails` instances.

        This method is equivalent to ``list(spec.validate(v))``. If an empty list is
        returned ``v`` is valid according to the Spec.

        :param v: a value to validate
        :return: a list of Spec failures as :py:class:`dataspec.ErrorDetails`
            instances, if any
        """
        return list(self.validate(v))

    def validate_ex(self, v: Any) -> None:
        """
        Validate the value ``v`` against the Spec, throwing a
        :py:class:`dataspec.ValidationError` containing a list of all of the Spec
        failures for ``v`` , if any. Returns :py:obj:`None` otherwise.

        :param v: a value to validate
        :return: :py:obj:`None`
        """
        errors = self.validate_all(v)
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
    def conformer(self) -> Optional[Conformer]:  # pragma: no cover
        """Return the custom conformer attached to this Spec, if one is defined."""
        return None

    def conform(self, v: Any):
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

    def conform_valid(self, v: Any):
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

    def compose_conformer(self, conformer: Conformer) -> "Spec":
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

        def conform_spec(v: T) -> Union[V, Invalid]:
            assert existing_conformer is not None
            return conformer(existing_conformer(v))  # pylint: disable=not-callable

        return self.with_conformer(conform_spec)

    def with_conformer(self, conformer: Optional[Conformer]) -> "Spec":
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

    def with_tag(self, tag: Tag) -> "Spec":
        """
        Return a new Spec instance with the new tag applied.

        This method does not modify the current Spec instance.

        :param tag: a new tag to use for the new Spec
        :return: a copy of the current Spec instance with the new tag applied
        """
        return attr.evolve(self, tag=tag)


def tag_maybe(
    maybe_tag: Union[Tag, T], *args: T
) -> Tuple[Optional[Tag], Tuple[T, ...]]:
    """Return the Spec tag and the remaining arguments if a tag is given, else return
    the arguments."""
    tag = maybe_tag if isinstance(maybe_tag, str) else None
    return tag, (cast("Tuple[T, ...]", (maybe_tag, *args)) if tag is None else args)


@attr.s(auto_attribs=True, frozen=True, slots=True)
class ValidatorSpec(Spec):
    """Validator Specs yield richly detailed errors from their validation functions and
    can be useful for answering more detailed questions about their their input data
    than a simple predicate function."""

    tag: Tag
    _validate: ValidatorFn
    conformer: Optional[Conformer] = None

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
        cls, tag: Tag, *preds: ValidatorFn, conformer: Optional[Conformer] = None,
    ) -> Spec:
        """Return a single Validator spec from the composition of multiple validator
        functions."""
        assert len(preds) > 0, "At least on predicate must be specified"

        # Avoid wrapping an existing validator function in an extra layer of
        # indirection
        if len(preds) == 1:
            return ValidatorSpec(tag, preds[0], conformer=conformer)

        def do_validate(v) -> Iterator[ErrorDetails]:
            for pred in preds:
                yield from pred(v)

        return cls(tag, do_validate, conformer=conformer)


@attr.s(auto_attribs=True, frozen=True, slots=True)
class PredicateSpec(Spec):
    """
    Predicate Specs are useful for validating data with a boolean predicate function.

    Predicate specs can be useful for validating simple yes/no questions about data, but
    the errors they can produce are limited by the nature of the predicate return value.
    """

    tag: Tag
    _pred: PredicateFn
    conformer: Optional[Conformer] = None

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


CollSpecKwargs = Mapping[str, Union[bool, int, Type, None]]


@attr.s(auto_attribs=True, frozen=True, slots=True)
class CollSpec(Spec):
    tag: Tag
    _spec: Spec
    conformer: Optional[Conformer] = None
    _out_type: Optional[Type] = None
    _validate_coll: Optional[Spec] = None

    @classmethod  # noqa: MC0001
    def from_val(
        cls,
        tag: Optional[Tag],
        sequence: Sequence[Union[SpecPredicate, CollSpecKwargs]],
        conformer: Conformer = None,
    ) -> Spec:
        # pylint: disable=too-many-branches,too-many-locals
        spec = make_spec(cast(SpecPredicate, sequence[0]))
        validate_coll: Optional[Spec] = None

        kwargs: CollSpecKwargs
        try:
            kwargs = cast(CollSpecKwargs, sequence[1])
            if not isinstance(kwargs, dict):
                raise TypeError("Collection spec options must be a dict")
        except IndexError:
            kwargs = {}

        validators = []

        allow_str: bool = kwargs.get("allow_str", False)
        maxlength: Optional[int] = kwargs.get("maxlength", None)
        minlength: Optional[int] = kwargs.get("minlength", None)
        count: Optional[int] = kwargs.get("count", None)
        type_: Optional[Type] = kwargs.get("kind", None)
        out_type: Optional[Type] = kwargs.get("into", None)

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

        def conform_coll(v: Iterable) -> Iterable:
            return (out_type or type(v))(spec.conform(e) for e in v)  # type: ignore[call-arg]  # noqa

        return cls(
            tag or "coll",
            spec=spec,
            conformer=compose_conformers(conform_coll, conformer),
            out_type=out_type,
            validate_coll=validate_coll,
        )

    def validate(self, v) -> Iterator[ErrorDetails]:
        if self._validate_coll:
            yield from _enrich_errors(self._validate_coll.validate(v), self.tag)

        for i, e in enumerate(v):
            yield from _enrich_errors(self._spec.validate(e), self.tag, i)


T_hashable = TypeVar("T_hashable", bound=Hashable)


@attr.s(auto_attribs=True, frozen=True, slots=_USE_SLOTS_FOR_GENERIC)
class OptionalKey(Generic[T_hashable]):
    key: T_hashable


@attr.s(auto_attribs=True, frozen=True, slots=True)
class _KeySpec:
    spec: Spec
    is_optional: bool = False


@attr.s(auto_attribs=True, frozen=True, slots=True)
class DictSpec(Spec):
    tag: Tag
    _keyspecs: Mapping[Hashable, _KeySpec] = attr.ib(factory=dict)
    conformer: Optional[Conformer] = None

    @classmethod
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[Hashable, SpecPredicate],
        conformer: Optional[Conformer] = None,
    ) -> Spec:
        keyspecs = {}
        for k, v in kvspec.items():
            if isinstance(k, OptionalKey):
                if k.key in keyspecs:
                    raise KeyError(f"Optional key '{k.key}' duplicates existing key")
                keyspecs[k.key] = _KeySpec(make_spec(v), is_optional=True)
            else:
                if k in keyspecs:
                    raise KeyError(f"Required key '{k}' duplicates existing key")
                keyspecs[k] = _KeySpec(make_spec(v))

        def conform_mapping(d: Mapping) -> Mapping:
            conformed_d = {}
            for k, keyspec in keyspecs.items():
                if keyspec.is_optional:
                    if k in d:
                        conformed_d[k] = keyspec.spec.conform(d[k])
                else:
                    conformed_d[k] = keyspec.spec.conform(d[k])

            return conformed_d

        return cls(
            tag or "map",
            keyspecs=keyspecs,
            conformer=compose_conformers(conform_mapping, conformer),
        )

    def validate(self, d) -> Iterator[ErrorDetails]:  # pylint: disable=arguments-differ
        try:
            for k, keyspec in self._keyspecs.items():
                if keyspec.is_optional:
                    if k in d:
                        yield from _enrich_errors(
                            keyspec.spec.validate(d[k]), self.tag, k
                        )
                else:
                    if k in d:
                        yield from _enrich_errors(
                            keyspec.spec.validate(d[k]), self.tag, k
                        )
                    else:
                        yield ErrorDetails(
                            message=f"Mapping missing key {k}",
                            pred=keyspec.spec,
                            value=d,
                            via=[self.tag],
                            path=[k],
                        )
        except (AttributeError, TypeError):
            yield ErrorDetails(
                message="Value is not a mapping type",
                pred=self,
                value=d,
                via=[self.tag],
            )
            return

    # pylint: disable=protected-access
    @classmethod
    def merge(
        cls,
        tag: Optional[Tag],
        *specs: "DictSpec",
        conformer: Optional[Conformer] = None,
    ) -> Spec:
        assert len(specs) >= 2, "Must merge at least two Specs"

        map_pred: MutableMapping[Hashable, List[SpecPredicate]] = defaultdict(list)
        for spec in specs:
            for k, keyspec in spec._keyspecs.items():
                map_pred[OptionalKey(k) if keyspec.is_optional else k].append(
                    keyspec.spec
                )

        return cls.from_val(
            tag or f"merge-of-{'-'.join(spec.tag for spec in specs)}",
            {k: all_spec(str(k), *v) for k, v in map_pred.items()},
            conformer=conformer,
        )


def kv_spec(
    tag_or_pred: Union[Tag, SpecPredicate],
    *preds: SpecPredicate,
    conform_keys: bool = False,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """
    Return a Spec that validates mapping types against a single Spec for all keys
    and a single Spec for all values.

    If ``conform_keys`` is specified as :py:obj:`True`, the default conformer will
    conform keys and values. By default, ``conform_keys`` is :py:obj:`False` to avoid
    duplicate names produced during the conformation.

    The returned Spec's :py:meth:`dataspec.Spec.conform` method will return a
    :py:class:`dict` with values conformed by the corresponding input Spec. If a
    ``conformer`` is provided via keyword argument, that conformer will be provided a
    :py:class:`dict` with the conformed :py:class:`dict` as described above. Otherwise,
    the default conformer will simply return the conformed :py:class:`dict` . Note that
    the default conformer does **not** modify the input mapping in place.

    Exactly two Specs must be provided or a :py:class:`ValueError` will be raised
    during construction.

    :param tag_or_pred: an optional tag for the resulting spec or the key Spec
        or value which can be converted into a Spec
    :param preds: if a tag is given, preds should be exactly two Specs or values
        which can be converted into Specs; the first shall be the Spec for the
        keys and the second shall be the Spec for values
    :param conform_keys: if :py:obj:`True`, the default conformer will also conform
        keys according to the input key Spec; default is :py:obj:`False`
    :param conformer: an optional conformer which will be composed with the
        default conformer
    :return: a Spec
    """
    tag, preds = tag_maybe(tag_or_pred, *preds)

    if len(preds) != 2:
        raise ValueError("Must specify a key and value Spec for k/v Specs")

    tag = tag or "kv"
    keyspec = make_spec(preds[0])
    valspec = make_spec(preds[1])

    def _kv_valid(d) -> Iterator[ErrorDetails]:
        assert tag is not None

        try:
            for k, v in d.items():
                yield from _enrich_errors(keyspec.validate(k), tag, d)
                yield from _enrich_errors(valspec.validate(v), tag, k)
        except (AttributeError, TypeError):
            yield ErrorDetails(
                message="Value is not a mapping type",
                pred=_kv_valid,
                value=d,
                via=[tag],
            )
            return

    if conform_keys:

        def conform_mapping(d: Mapping) -> Mapping:
            return {keyspec.conform(k): valspec.conform(v) for k, v in d.items()}

    else:

        def conform_mapping(d: Mapping) -> Mapping:
            return {k: valspec.conform(v) for k, v in d.items()}

    return ValidatorSpec(
        tag, _kv_valid, conformer=compose_conformers(conform_mapping, conformer),
    )


@attr.s(auto_attribs=True, frozen=True, slots=True)
class ObjectSpec(Spec):
    tag: Tag
    _reqattrspecs: Mapping[str, Spec] = attr.ib(factory=dict)
    _optattrspecs: Mapping[str, Spec] = attr.ib(factory=dict)
    conformer: Optional[Conformer] = None

    @classmethod
    def from_val(
        cls,
        tag: Optional[Tag],
        kvspec: Mapping[ObjectSpecKey, SpecPredicate],
        conformer: Optional[Conformer] = None,
    ) -> Spec:
        reqattrs = {}
        optattrs: MutableMapping[str, Spec] = {}
        for k, v in kvspec.items():
            if isinstance(k, OptionalKey):
                if k.key in reqattrs:
                    raise KeyError(
                        f"Optional attribute '{k.key}' duplicates key already defined in required attributes"
                    )
                optattrs[k.key] = make_spec(v)
            else:
                if k in optattrs:
                    raise KeyError(
                        f"Required attribute '{k}' duplicates key already defined in optional attributes"
                    )
                reqattrs[k] = make_spec(v)

        return cls(
            tag or "obj",
            reqattrspecs=reqattrs,
            optattrspecs=optattrs,
            conformer=conformer,
        )

    def validate(self, o) -> Iterator[ErrorDetails]:  # pylint: disable=arguments-differ
        for k, vspec in self._reqattrspecs.items():
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

        for k, vspec in self._optattrspecs.items():
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
    conformer: Optional[Conformer] = None

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
            conformer=compose_conformers(_enum_conformer(pred), conformer,),
        )


_MUNGE_NAMES = re.compile(r"[\s|-]")


@attr.s(auto_attribs=True, frozen=True, slots=True)
class TupleSpec(Spec):
    tag: Tag
    _pred: Tuple[SpecPredicate, ...]
    _specs: Tuple[Spec, ...]
    conformer: Optional[Conformer] = None
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

        def conform_tuple(v) -> Union[Tuple, NamedTuple]:
            return ((namedtuple_type and namedtuple_type._make) or tuple)(
                spec.conform(v) for spec, v in zip(specs, v)
            )

        return cls(
            tag or "tuple",
            pred=pred,
            specs=specs,
            conformer=compose_conformers(conform_tuple, conformer),
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


def compose_conformers(*conformers: Optional[Conformer]) -> Optional[Conformer]:
    """
    Return a single conformer which is the composition of the input conformers.

    If a single conformer is given, return the conformer.
    """

    conformers = tuple(filter(None, conformers))

    if not conformers:
        return None

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


def all_spec(
    tag_or_pred: Union[Tag, SpecPredicate],
    *preds: SpecPredicate,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """
    Return a Spec which validates input values against all of the input Specs or
    spec predicates.

    For each Spec for which the input value is successfully validated, the value is
    successively passed to the Spec's :py:meth:`dataspec.Spec.conform_valid` method.

    The returned Spec's :py:meth:`dataspec.Spec.validate` method will emit a stream
    of :py:class:`dataspec.ErrorDetails`` from the first failing constituent Spec.
    :py:class:`dataspec.ErrorDetails` emitted from Specs after a failing Spec will
    not be emitted, because the failing Spec's :py:meth:`dataspec.Spec.conform``
    would not successfully conform the value.

    The returned Spec's :py:meth:`dataspec.Spec.conform` method is the composition
    of all of the input Spec's ``conform`` methods.

    If no Specs or Spec predicates are given, a :py:class:`ValueError` will be raised.
    If only one Spec or Spec predicate is provided, it will be passed to
    :py:func:`dataspec.s` with the given ``tag`` and ``conformer`` and the value
    returned without merging.

    This method is not suitable for producing a union of mapping Specs. To merge
    mapping Specs, use :py:meth:`dataspec.SpecAPI.merge` instead.

    :param tag_or_pred: an optional tag for the resulting spec or the first Spec or
        value which can be converted into a Spec; if no tag is provided, the default is
        ``"all"``
    :param preds: zero or more Specs or values which can be converted into a Spec
    :param conformer: an optional conformer which will be applied to the final
        conformed value produced by the input Specs conformers
    :return: a Spec
    """
    tag, preds = tag_maybe(tag_or_pred, *preds)

    if not preds:
        raise ValueError("Must provide at least one Spec for 'all' Specs")

    if len(preds) == 1:
        return make_spec(
            *filter(None, (tag,)),  # type: ignore[arg-type]  # noqa: F821
            preds[0],
            conformer=conformer,
        )

    specs = [make_spec(pred) for pred in preds]

    def _all_valid(e) -> Iterator[ErrorDetails]:
        """Validate e against successive conformations to spec in specs."""

        for spec in specs:
            errors = []
            for error in spec.validate(e):
                errors.append(error)
            if errors:
                yield from errors
                return
            e = spec.conform_valid(e)

    return ValidatorSpec(
        tag or "all",
        _all_valid,
        conformer=compose_conformers(*(spec.conformer for spec in specs), conformer,),
    )


def any_spec(
    tag_or_pred: Union[Tag, SpecPredicate],
    *preds: SpecPredicate,
    tag_conformed: bool = False,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """
    Return a Spec which validates input values against any one of an arbitrary
    number of input Specs.

    The returned Spec validates input values against the input Specs in the order
    they are passed into this function.

    If the returned Spec fails to validate the input value, the
    :py:meth:`dataspec.Spec.validate` method will emit a stream of
    :py:class:`dataspec.ErrorDetails` from all of failing constituent Specs. If any of
    the constituent Specs successfully validates the input value, then no
    :py:class:`dataspec.ErrorDetails` will be emitted by the
    :py:meth:`dataspec.Spec.validate` method.

    The conformer for the returned Spec will select the conformer for the first
    constituent Spec which successfully validates the input value. If a ``conformer``
    is specified for this Spec, that conformer will be applied after the successful
    Spec's conformer. If ``tag_conformed`` is specified, the final conformed value
    from both conformers will be wrapped in a tuple, where the first element is the
    tag of the successful Spec and the second element is the final conformed value.
    If ``tag_conformed`` is not specified (which is the default), the conformer will
    emit the conformed value directly.

    If no Specs or Spec predicates are given, a :py:class:`ValueError` will be raised.
    If only one Spec or Spec predicate is provided, it will be passed to
    :py:func:`dataspec.s` with the given ``tag`` and ``conformer`` and the value
    returned without merging.

    :param tag_or_pred: an optional tag for the resulting spec or the first Spec or
        value which can be converted into a Spec; if no tag is provided, the default is
        ``"any"``
    :param preds: zero or more Specs or values which can be converted into a Spec
    :param tag_conformed: if :py:obj:`True`, the conformed value will be wrapped in a
        2-tuple where the first element is the successful spec and the second element
        is the conformed value; if :py:obj:`False`, return only the conformed value
    :param conformer: an optional conformer for the value
    :return: a Spec
    """
    tag, preds = tag_maybe(tag_or_pred, *preds)

    if not preds:
        raise ValueError("Must provide at least one Spec for 'any' Specs")

    if len(preds) == 1:
        return make_spec(
            *filter(None, (tag,)),  # type: ignore[arg-type]  # noqa: F821
            preds[0],
            conformer=conformer,
        )

    specs = [make_spec(pred) for pred in preds]

    def _any_valid(e) -> Iterator[ErrorDetails]:
        errors = []
        for spec in specs:
            spec_errors = list(spec.validate(e))
            if spec_errors:
                errors.extend(spec_errors)
            else:
                return

        yield from errors

    def _conform_any(e):
        for spec in specs:
            spec_errors = list(spec.validate(e))
            if spec_errors:
                continue

            conformed = spec.conform_valid(e)
            assert conformed is not INVALID
            if conformer is not None:
                conformed = conformer(conformed)
            if tag_conformed:
                conformed = (spec.tag, conformed)
            return conformed

        return INVALID

    return ValidatorSpec(tag or "any", _any_valid, conformer=_conform_any)


def merge_spec(
    tag_or_pred: Union[Tag, SpecPredicate],
    *preds: SpecPredicate,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """
    Merge two or more mapping Specs into a single new Spec.

    The returned Spec validates input values against a mapping Spec which is created
    from the union of input mapping Specs. Mapping Specs will be merged in the order
    they are provided. Individual key Specs whose keys appear more than one input Spec
    will be merged as via :py:meth:`dataspec.SpecAPI.all` in the order they are passed
    into this function.

    If no Specs or Spec predicates are given, a :py:class:`ValueError` will be raised.
    If only one Spec or Spec predicate is provided, it will be passed to
    :py:func:`dataspec.s` with the given ``tag`` and ``conformer`` and the value returned
    without merging. If any Specs or Spec predicates are provided which are not mapping
    Specs or which cannot be coerced to mapping Specs, a :py:class:`TypeError` will be
    raised.

    The returned Spec's :py:meth:`dataspec.Spec.conform` method is a standard mapping
    Spec default conformer. Keys not defined in the union of key sets will be dropped
    during conformation. Values with more than one Spec defined in the input Specs
    will be conformed as by :py:meth:`dataspec.SpecAPI.all` applied to all of their
    input Specs in the order they were provided. Values with exactly one Spec will
    use that Spec as given.

    :param tag_or_pred: an optional tag for the resulting spec or the first Spec or
        value which can be converted into a Spec; if no tag is provided, the default is
        computed as ``"merge-of-spec1-and-spec2-..."``
    :param preds: zero or more mapping Specs or values which can be converted into a
        mapping Spec
    :param conformer: an optional conformer for the value
    :return: a single mapping Spec which is the union of all input Specs
    """
    tag, preds = tag_maybe(tag_or_pred, *preds)

    if not preds:
        raise ValueError("Must provide at least one mapping Spec to merge")

    if len(preds) == 1:
        return make_spec(
            *filter(None, (tag,)),  # type: ignore[arg-type]  # noqa: F821
            preds[0],
            conformer=conformer,
        )

    specs = [make_spec(pred) for pred in preds]

    for spec in specs:
        if not isinstance(spec, DictSpec):
            raise TypeError(f"Can only merge mapping spec types, not '{type(spec)}'")

    return DictSpec.merge(
        tag, *cast("Tuple[DictSpec, ...]", specs), conformer=conformer
    )


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
    tag_or_pred: Union[Tag, SpecPredicate],
    *preds: SpecPredicate,
    conformer: Optional[Conformer] = None,
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
    singleton and conform the input value to the corresponding :py:class:`enum.Enum`
    value.

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

    :param tag_or_pred: an optional tag for the resulting spec or a Spec or value which
        can be converted into a Spec; if no tag is provided, the default depends on the
        input type:

        * for ``frozenset`` and ``set`` predicates, the default is ``"set"``

        * for ``Enum`` predicates, the default is the name of the enum

        * for ``tuple`` predicates, the default is ``"tuple"``

        * for ``list`` (collection) predicates, the default is ``"coll"``

        * for ``dict`` (mapping) predicates, the default is ``"map"``

        * for ``type`` predicates, the default is the name of the type

        * for callable predicates, the default is the name of the function

    :param preds: if a tag is given, exactly one spec predicate; if no tag is given,
        this should not be specified
    :param conformer: an optional :py:data:`dataspec.Conformer` for the value
    :return: a :py:class:`dataspec.base.Spec` instance
    """
    tag, preds = tag_maybe(tag_or_pred, *preds)

    if len(preds) != 1:
        raise TypeError("Expected some spec predicate")

    try:
        pred = preds[0]
    except IndexError:
        raise TypeError("Expected some spec predicate")

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
