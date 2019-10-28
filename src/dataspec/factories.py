import re
import sys
import threading
import uuid
from datetime import date, datetime, time
from email.headerregistry import Address as EmailAddress
from functools import partial
from typing import (
    AbstractSet,
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
from urllib.parse import ParseResult, parse_qs, urlparse

import attr

from dataspec.base import (
    INVALID,
    Conformer,
    ErrorDetails,
    Invalid,
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
    """
    Return a Spec which validates input values against any one of an arbitrary
    number of input Specs.

    The returned Spec validates input values against the input Specs in the order
    they are passed into this function.

    If the returned Spec fails to validate the input value, the
    :py:meth:`dataspec.base.Spec.validate` method will emit a stream of
    :py:class:`dataspec.base.ErrorDetails` from all of failing constituent Specs.
    If any of the constituent Specs successfully validates the input value, then
    no :py:class:`dataspec.base.ErrorDetails` will be emitted by the
    :py:meth:`dataspec.base.Spec.validate` method.

    :param tag: an optional tag for the resulting spec
    :param preds: one or more Specs or values which can be converted into a Spec
    :param conformer: an optional conformer for the value
    :return: a Spec
    """
    tag, preds = _tag_maybe(*preds)  # pylint: disable=no-value-for-parameter
    specs = [make_spec(pred) for pred in preds]

    def _any_valid(e) -> Iterator[ErrorDetails]:
        errors = []
        for spec in specs:
            spec_errors = [error for error in spec.validate(e)]
            if spec_errors:
                errors.extend(spec_errors)
            else:
                return

        yield from errors

    return ValidatorSpec(tag or "any", _any_valid, conformer=conformer)


def all_spec(*preds: SpecPredicate, conformer: Optional[Conformer] = None) -> Spec:
    """
    Return a Spec which validates input values against all of the input Specs or
    spec predicates.

    For each Spec for which the input value is successfully validated, the value is
    successively passed to the Spec's :py:meth:`dataspec.base.Spec.conform_valid`
    method.

    The returned Spec's :py:meth:`dataspec.base.Spec.validate` method will emit
    a stream of :py:class:`dataspec.base.ErrorDetails` from the first failing
    constituent Spec. :py:class:`dataspec.base.ErrorDetails` emitted from Specs
    after a failing Spec will not be emitted, because the failing Spec's
    :py:meth:`dataspec.base.Spec.conform` would not successfully conform the value.

    The returned Spec's :py:meth:`dataspec.base.Spec.conform` method is the composition
    of all of the input Spec's ``conform`` methods.

    :param tag: an optional tag for the resulting spec
    :param preds: one or more Specs or values which can be converted into a Spec
    :param conformer: an optional conformer which will be applied to the final
        conformed value produced by the input Specs conformers
    :return: a Spec
    """
    tag, preds = _tag_maybe(*preds)  # pylint: disable=no-value-for-parameter
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
        conformer=compose_conformers(*specs, conform_final=conformer),
    )


def bool_spec(
    tag: Optional[Tag] = None,
    allowed_values: Optional[Set[bool]] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """
    Return a Spec which will validate boolean values.

    :param tag: an optional tag for the resulting spec
    :param allowed_values: if specified, a set of allowed boolean values
    :param conformer: an optional conformer for the value
    :return: a Spec which validates boolean values
    """

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
    length: Optional[int] = None,
    minlength: Optional[int] = None,
    maxlength: Optional[int] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """
    Return a spec that can validate bytes and bytearrays against common rules.

    If ``type_`` is specified, the resulting Spec will only validate the byte type
    or types named by ``type_``, otherwise :py:class:`byte` and :py:class:`bytearray`
    will be used.

    If ``length`` is specified, the resulting Spec will validate that input bytes
    measure exactly ``length`` bytes by by :py:func:`len`. If ``minlength`` is
    specified, the resulting Spec will validate that input bytes measure at least
    ``minlength`` bytes by by :py:func:`len`.  If ``maxlength`` is specified, the
    resulting Spec will validate that input bytes measure not more than ``maxlength``
    bytes by by :py:func:`len`. Only one of ``length``, ``minlength``, or ``maxlength``
    can be specified. If more than one is specified a :py:exc:`ValueError` will be
    raised. If any length value is specified less than 0 a :py:exc:`ValueError` will
    be raised. If any length value is not an :py:class:`int` a :py:exc:`TypeError`
    will be raised.

    :param tag: an optional tag for the resulting spec
    :param type_:  a single :py:class:`type` or tuple of :py:class:`type`s which
        will be used to type check input values by the resulting Spec
    :param length: if specified, the resulting Spec will validate that bytes are
        exactly ``length`` bytes long by :py:func:`len`
    :param minlength: if specified, the resulting Spec will validate that bytes are
        not fewer than ``minlength`` bytes long by :py:func:`len`
    :param maxlength: if specified, the resulting Spec will validate that bytes are
        not longer than ``maxlength`` bytes long by :py:func:`len`
    :param conformer: an optional conformer for the value
    :return: a Spec which validates bytes and bytearrays
    """

    @pred_to_validator(f"Value '{{value}}' is not a {type_}", complement=True)
    def is_bytes(s: Any) -> bool:
        return isinstance(s, type_)

    validators: List[Union[ValidatorFn, ValidatorSpec]] = [is_bytes]

    if length is not None:

        if not isinstance(length, int):
            raise TypeError("Byte length spec must be an integer length")

        if length < 0:
            raise ValueError("Byte length spec cannot be less than 0")

        if minlength is not None or maxlength is not None:
            raise ValueError(
                "Cannot define a byte spec with exact length "
                "and minlength or maxlength"
            )

        @pred_to_validator(f"Bytes length does not equal {length}", convert_value=len)
        def bytestr_is_exactly_len(v: Union[bytes, bytearray]) -> bool:
            return len(v) != length

        validators.append(bytestr_is_exactly_len)

    if minlength is not None:

        if not isinstance(minlength, int):
            raise TypeError("Byte minlength spec must be an integer length")

        if minlength < 0:
            raise ValueError("Byte minlength spec cannot be less than 0")

        @pred_to_validator(
            f"Bytes '{{value}}' does not meet minimum length {minlength}"
        )
        def bytestr_has_min_length(s: Union[bytes, bytearray]) -> bool:
            return len(s) < minlength  # type: ignore

        validators.append(bytestr_has_min_length)

    if maxlength is not None:

        if not isinstance(maxlength, int):
            raise TypeError("Byte maxlength spec must be an integer length")

        if maxlength < 0:
            raise ValueError("Byte maxlength spec cannot be less than 0")

        @pred_to_validator(f"Bytes '{{value}}' exceeds maximum length {maxlength}")
        def bytestr_has_max_length(s: Union[bytes, bytearray]) -> bool:
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
    """
    Return a Spec which validates every possible value.

    :param tag: an optional tag for the resulting spec
    :param conformer: an optional conformer for the value
    :return: a Spec which validates any value
    """

    def always_true(_) -> bool:
        return True

    return PredicateSpec(tag or "every", always_true, conformer=conformer)


_DEFAULT_STRPTIME_DATE = date(1900, 1, 1)
_DEFAULT_STRPTIME_TIME = time()


def _make_datetime_spec_factory(  # noqa: MC0001
    type_: Union[Type[datetime], Type[date], Type[time]]
) -> Callable[..., Spec]:
    """
    Factory function for generating datetime type spec factories.

    Yep.
    """

    aware_docstring_blurb = (
        """If ``is_aware`` is :py:obj:`True`, the resulting Spec will validate that input
    values are timezone aware. If ``is_aware`` is :py:obj:`False`, the resulting Spec
    will validate that inpute values are naive. If unspecified, the resulting Spec
    will not consider whether the input value is naive or aware."""
        if type_ is not date
        else """If ``is_aware`` is specified, a :py:exc:`TypeError` will be raised as
    :py:class:`datetime.date` values cannot be aware or naive."""
    )

    format_docstring_blurb = (
        f"""If the
    :py:class:`datetime.datetime` object parsed from the ``format_`` string contains
    a portion not available in :py:class:`datetime.{type_.__name__}, then the
    validator will emit an error at runtime."""
        if type_ is not datetime
        else ""
    )

    docstring = f"""
    Return a Spec which validates :py:class:`datetime.{type_.__name__}` types with
    common rules.

    If ``format_`` is specified, the resulting Spec will accept string values and
    attempt to coerce them to :py:class:`datetime.{type_.__name__}` instances first
    before applying the other specified validations. {format_docstring_blurb}

    If ``before`` is specified, the resulting Spec will validate that input values
    are before ``before`` by Python's ``<`` operator. If ``after`` is specified, the
    resulting Spec will validate that input values are after ``after`` by Python's
    ``>`` operator. If ``before`` and ``after`` are specified and ``after`` is before
    ``before``, a :py:exc:`ValueError` will be raised.

    {aware_docstring_blurb}

    :param tag: an optional tag for the resulting spec
    :param format: if specified, a time format string which will be fed to
        :py:meth:`datetime.{type_.__name__}.strptime` to convert the input string
        to a :py:class:`datetime.{type_.__name__}` before applying the other
        validations
    :param before: if specified, the input value must come before this date or time
    :param after: if specified, the input value must come after this date or time
    :param is_aware: if :py:obj:`True`, validate that input objects are timezone
        aware; if :py:obj:`False`, validate that input objects are naive; if
        :py:obj:`None`, do not consider whether the input value is naive or aware
    :param conformer: an optional conformer for the value
    :return: a Spec which validates :py:class:`datetime.{type_.__name__}` types
    """

    if type_ is date:

        def strptime(s: str, fmt: str) -> date:
            parsed = datetime.strptime(s, fmt)
            if parsed.time() != _DEFAULT_STRPTIME_TIME:
                raise TypeError(f"Parsed time includes date portion: {parsed.time()}")
            return parsed.date()

    elif type_ is time:

        def strptime(s: str, fmt: str) -> time:  # type: ignore
            parsed = datetime.strptime(s, fmt)
            if parsed.date() != _DEFAULT_STRPTIME_DATE:
                raise TypeError(f"Parsed date includes time portion: {parsed.date()}")
            return parsed.time()

    else:
        assert type_ is datetime

        strptime = datetime.strptime  # type: ignore

    def _datetime_spec_factory(  # pylint: disable=too-many-arguments
        tag: Optional[Tag] = None,
        format_: Optional[str] = None,
        before: Optional[type_] = None,  # type: ignore
        after: Optional[type_] = None,  # type: ignore
        is_aware: Optional[bool] = None,
        conformer: Optional[Conformer] = None,
    ) -> Spec:
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

        if after is not None and before is not None:
            if after < before:
                raise ValueError(
                    "Date spec 'after' criteria must be after"
                    "'before' criteria if both specified"
                )

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

        if format_ is not None:

            def conform_datetime_str(s: str) -> Union[datetime, date, time, Invalid]:
                try:
                    return strptime(s, format_)  # type: ignore
                except (TypeError, ValueError):
                    return INVALID

            def validate_datetime_str(s: str) -> Iterator[ErrorDetails]:
                try:
                    dt = strptime(s, format_)  # type: ignore
                except TypeError as e:
                    yield ErrorDetails(
                        message=f"String contains invalid portion for type: {e}",
                        pred=validate_datetime_str,
                        value=s,
                    )
                except ValueError:
                    yield ErrorDetails(
                        message=(
                            "String does not contain a date which can be "
                            f"parsed as '{format_}'"
                        ),
                        pred=validate_datetime_str,
                        value=s,
                    )
                else:
                    for validate in validators:
                        yield from validate(dt)

            return ValidatorSpec(
                tag or type.__name__,
                validate_datetime_str,
                conformer=conformer or conform_datetime_str,
            )
        else:
            return ValidatorSpec.from_validators(
                tag or type_.__name__, *validators, conformer=conformer
            )

    _datetime_spec_factory.__doc__ = docstring
    return _datetime_spec_factory


datetime_spec = _make_datetime_spec_factory(datetime)
date_spec = _make_datetime_spec_factory(date)
time_spec = _make_datetime_spec_factory(time)

try:
    from dateutil.parser import parse as parse_date, isoparse as parse_isodate
except ImportError:
    pass
else:

    def datetime_str_spec(  # pylint: disable=too-many-arguments
        tag: Optional[Tag] = None,
        iso_only: bool = False,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
        is_aware: Optional[bool] = None,
        conformer: Optional[Conformer] = None,
    ) -> Spec:
        """
        Return a Spec that validates strings containing date/time strings in
        most common formats.

        The resulting Spec will validate that the input value is a string which
        contains a date/time using :py:func:`dateutil.parser.parse`. If the input
        value can be determined to contain a valid :py:class:`datetime.datetime`
        instance, it will be validated against a datetime Spec as by a standard
        ``dataspec`` datetime Spec using the keyword options below.

        :py:func:`dateutil.parser.parse` cannot produce :py:class:`datetime.time`
        or :py:class:`datetime.date` instances directly, so this method will only
        produce :py:func:`datetime.datetime` instances even if the input string
        contains only a valid time or date, but not both.

        If ``iso_only`` keyword argument is ``True``, restrict the set of allowed
        input values to strings which contain ISO 8601 formatted strings. This is
        accomplished using :py:func:`dateutil.parser.isoparse`, which does not
        guarantee strict adherence to the ISO 8601 standard, but accepts a wider
        range of valid ISO 8601 strings than Python 3.7+'s
        :py:func:`datetime.datetime.fromisoformat` function.

        :param tag: an optional tag for the resulting spec
        :param iso_only: if True, restrict the set of allowed date strings to those
            formatted as ISO 8601 datetime strings; default is False
        :param before: if specified, a datetime that specifies the latest instant
            this Spec will validate
        :param after: if specified, a datetime that specifies the earliest instant
            this Spec will validate
        :param bool is_aware: if specified, indicate whether the Spec will validate
            either aware or naive :py:class:`datetime.datetime` instances.
        :param conformer: an optional conformer for the value; if one is not provided
            :py:func:`dateutil.parser.parse` will be used
        :return: a Spec which validates strings containing date/time strings
        """

        tag = tag or "datetime_str"

        @pred_to_validator(f"Value '{{value}}' is not type 'str'", complement=True)
        def is_str(x: Any) -> bool:
            return isinstance(x, str)

        dt_spec = datetime_spec(before=before, after=after, is_aware=is_aware)
        parse_date_str = parse_isodate if iso_only else parse_date

        def str_contains_datetime(s: str) -> Iterator[ErrorDetails]:
            try:
                parsed_dt = parse_date_str(s)  # type: ignore
            except (OverflowError, ValueError):
                yield ErrorDetails(
                    message=f"String '{s}' does not contain a datetime",
                    pred=str_contains_datetime,
                    value=s,
                )
            else:
                yield from dt_spec.validate(parsed_dt)

        return ValidatorSpec.from_validators(
            tag, is_str, str_contains_datetime, conformer=conformer or parse_date
        )


_IGNORE_OBJ_PARAM = object()
_EMAIL_RESULT_FIELDS = frozenset({"username", "domain"})


def _obj_attr_validator(  # pylint: disable=too-many-arguments
    object_name: str,
    attr: str,
    exact_attr: Any,
    regex_attr: Any,
    in_attr: Any,
    exact_attr_ignore: Any = _IGNORE_OBJ_PARAM,
    regex_attr_ignore: Any = _IGNORE_OBJ_PARAM,
    in_attr_ignore: Any = _IGNORE_OBJ_PARAM,
    disallowed_attrs_regex: Optional[AbstractSet[str]] = None,
) -> Optional[ValidatorFn]:
    """
    Create a validator function for an object attribute based on one of three
    distinct rules: exact value match (as Python ``==``), constrained set of exact
    values (using Python sets and the ``in`` operator), or a regex value match.

    :param object_name: the name of the validated object type for error messages
    :param attr: the name of the attribute on the object to check; will fed to
        Python's :py:func:`getattr` function
    :param exact_attr: if ``exact_attr`` is any value other than ``exact_attr_ignore``,
        create a validator function which checks that an object attribute exactly
        matches this value
    :param regex_attr: if ``regex_attr`` is any value other than ``regex_attr_ignore``,
        create a validator function which checks that an object attribute matches this
        regex pattern by :py:func:`re.fullmatch`
    :param in_attr: if ``in_attr`` is any value other than ``in_attr_ignore``,
        create a validator function which checks that an object attribute matches one
        of the values of this set
    :param exact_attr_ignore: the value of ``exact_attr` which indicates it should be
        ignored as a rule
    :param regex_attr_ignore: the value of ``regex_attr` which indicates it should be
        ignored as a rule
    :param in_attr_ignore: the value of ``in_attr` which indicates it should be
        ignored as a rule
    :param disallowed_attrs_regex: if specified, a set of attributes for which creating
        a regex rule should be disallowed
    :return: if any valid rules are given, return a validator function as defined above
    """

    def get_obj_attr(v: Any, attr: str = attr) -> Any:
        return getattr(v, attr)

    if exact_attr is not exact_attr_ignore:

        @pred_to_validator(
            f"{object_name} attribute '{attr}' value '{{value}}' is not '{exact_attr}'",
            complement=True,
            convert_value=get_obj_attr,
        )
        def obj_attr_equals(v: EmailAddress) -> bool:
            return get_obj_attr(v) == exact_attr

        return obj_attr_equals

    elif regex_attr is not regex_attr_ignore:

        if disallowed_attrs_regex is not None and attr in disallowed_attrs_regex:
            raise ValueError(
                f"Cannot define regex spec for {object_name} attribute '{attr}'"
            )

        if not isinstance(regex_attr, str):
            raise TypeError(
                f"{object_name} attribute '{attr}_regex' must be a string value"
            )

        pattern = re.compile(regex_attr)

        @pred_to_validator(
            f"{object_name} attribute '{attr}' value '{{value}}' does not "
            f"match regex '{regex_attr}'",
            complement=True,
            convert_value=get_obj_attr,
        )
        def obj_attr_matches_regex(v: EmailAddress) -> bool:
            return bool(re.fullmatch(pattern, get_obj_attr(v)))

        return obj_attr_matches_regex

    elif in_attr is not in_attr_ignore:

        if not isinstance(in_attr, (frozenset, set)):
            raise TypeError(
                f"{object_name} attribute '{attr}_in' must be set or frozenset"
            )

        @pred_to_validator(
            f"{object_name} attribute '{attr}' value '{{value}}' not in {in_attr}",
            complement=True,
            convert_value=get_obj_attr,
        )
        def obj_attr_is_allowed_value(v: EmailAddress) -> bool:
            return get_obj_attr(v) in in_attr

        return obj_attr_is_allowed_value
    else:
        return None


def email_spec(
    tag: Optional[Tag] = None, conformer: Optional[Conformer] = None, **kwargs
) -> Spec:
    """
    Return a spec that can validate strings containing email addresses.

    Email string specs always verify that input values are strings and that they can
    be successfully parsed by :py:func:`email.headerregistry.Address`.

    Other restrictions can be applied by passing any one of three different keyword
    arguments for any of the fields of :py:class:`email.headerregistry.Address`. For
    example, to specify restrictions on the ``username`` field, you could use the
    following keywords:

     * ``domain`` accepts any value (including :py:obj:`None`) and checks for an
       exact match of the keyword argument value
     * ``domain_in`` takes a :py:class:``set`` or :py:class:``frozenset`` and
       validates that the `domain`` field is an exact match with one of the
       elements of the set
     * ``domain_regex`` takes a :py:class:``str``, creates a Regex pattern from
       that string, and validates that ``domain`` is a match (by
       :py:func:`re.fullmatch`) with the given pattern

    The value :py:obj:`None` can be used for comparison in all cases, though the value
    :py:obj:`None` is never tolerated as a valid ``username`` or ``domain`` of an
    email address.

    At most only one restriction can be applied to any given field for the
    :py:class:`email.headerregistry.Address`. Specifying more than one restriction for
    a field will produce a :py:exc:`ValueError`.

    Providing a keyword argument for a non-existent field of
    :py:class:`urllib.parse.ParseResult` will produce a :py:exc:`ValueError`.

    :param tag: an optional tag for the resulting spec
    :param username: if specified, require an exact match for ``username``
    :param username_in: if specified, require ``username`` to match at least one value in the set
    :param username_regex: if specified, require ``username`` to match the regex pattern
    :param domain: if specified, require an exact match for ``domain``
    :param domain_in: if specified, require ``domain`` to match at least one value in the set
    :param domain_regex: if specified, require ``domain`` to match the regex pattern
    :param conformer: an optional conformer for the value
    :return: a Spec which can validate that a string contains an email address
    """
    tag = tag or "email"

    @pred_to_validator(f"Value '{{value}}' is not type 'str'", complement=True)
    def is_str(x: Any) -> bool:
        return isinstance(x, str)

    child_validators = []
    for email_attr in _EMAIL_RESULT_FIELDS:
        in_attr = kwargs.pop(f"{email_attr}_in", _IGNORE_OBJ_PARAM)
        regex_attr = kwargs.pop(f"{email_attr}_regex", _IGNORE_OBJ_PARAM)
        exact_attr = kwargs.pop(f"{email_attr}", _IGNORE_OBJ_PARAM)

        if (
            sum(
                int(v is not _IGNORE_OBJ_PARAM)
                for v in [in_attr, regex_attr, exact_attr]
            )
            > 1
        ):
            raise ValueError(
                f"Email specs may only specify one of {email_attr}, "
                f"{email_attr}_in, and {email_attr}_regex for any Email attribute"
            )

        attr_validator = _obj_attr_validator(
            "Email", email_attr, exact_attr, regex_attr, in_attr
        )
        if attr_validator is not None:
            child_validators.append(attr_validator)

    if kwargs:
        raise ValueError(f"Unused keyword arguments: {kwargs}")

    def validate_email(p: EmailAddress) -> Iterator[ErrorDetails]:
        for validate in child_validators:
            yield from validate(p)

    def str_contains_email(s: str) -> Iterator[ErrorDetails]:
        try:
            addr = EmailAddress(addr_spec=s)
        except (TypeError, ValueError) as e:
            yield ErrorDetails(
                message=f"String '{s}' does not contain a valid email address: {e}",
                pred=str_contains_email,
                value=s,
            )
        else:
            yield from validate_email(addr)

    return ValidatorSpec.from_validators(
        tag, is_str, str_contains_email, conformer=conformer
    )


def nilable_spec(
    *args: Union[Tag, SpecPredicate], conformer: Optional[Conformer] = None
) -> Spec:
    """
    Return a Spec which will validate values either by the input Spec or allow
    the value :py:obj:`None`.

    :param tag: an optional tag for the resulting spec
    :param pred: a Spec or value which can be converted into a Spec
    :param conformer: an optional conformer for the value
    :return: a Spec which validates either according to ``pred`` or the value
        :py:obj:`None`
    """
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
    """
    Return a Spec that can validate numeric values against common rules.

    If ``type_`` is specified, the resulting Spec will only validate the numeric
    type or types named by ``type_``, otherwise :py:class:`float` and :py:class:`int`
    will be used.

    If ``min_`` is specified, the resulting Spec will validate that input values are
    at least ``min_`` using Python's ``<`` operator. If ``max_`` is specified, the
    resulting Spec will validate that input values are not more than ``max_`` using
    Python's ``<`` operator. If ``min_`` and ``max_`` are specified and ``max_`` is
    less than ``min_``, a :py:exc:`ValueError` will be raised.

    :param tag: an optional tag for the resulting spec
    :param type_: a single :py:class:`type` or tuple of :py:class:`type`s which
        will be used to type check input values by the resulting Spec
    :param min_: if specified, the resulting Spec will validate that numeric values
        are not less than ``min_`` (as by ``<``)
    :param max_: if specified, the resulting Spec will validate that numeric values
        are not less than ``max_`` (as by ``>``)
    :param conformer: an optional conformer for the value
    :return: a Spec which validates numeric values
    """

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


try:  # noqa: MC0001
    import phonenumbers
except ImportError:
    pass
else:

    def conform_phonenumber(
        s: str, region: Optional[str] = None
    ) -> Union[Invalid, str]:
        """Return a string containing a telephone number in E.164 format or return
        the special value :py:obj:``dataspec.base.INVALID`` if the input string does
        not contain a telephone number."""
        try:
            p = phonenumbers.parse(s, region=region)
        except phonenumbers.NumberParseException:
            return INVALID
        else:
            return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)

    def phonenumber_spec(
        tag: Optional[Tag] = None,
        region: Optional[str] = None,
        is_possible: bool = True,
        is_valid: bool = True,
        conformer: Optional[Conformer] = conform_phonenumber,
    ) -> Spec:
        """
        Return a Spec that validates strings containing telephone number in most
        common formats.

        The resulting Spec will validate that the input value is a string which
        contains a telephone number using :py:func:`phonenumbers.parse`. If the input
        value can be determined to contain a valid telephone number, it will be
        validated against a Spec which validates properties specified by the keyword
        arguments of this function.

        If ``region`` is supplied, the region will be used as a hint for
        :py:func:`phonenumbers.parse` and the region of the parsed telephone number
        will be verified. Telephone numbers can be specified with their region as a
        "+" prefix, which takes precedence over the ``region`` hint. The Spec will
        reject parsed telephone numbers whose region differs from the specified region
        in all cases.

        If ``is_possible`` is True, the parsed telephone number will be validated
        as a possible telephone number for the parsed region (which may be different
        from the specified region).

        If ``is_valid`` is True, the parsed telephone number will be validated as a
        valid telephone number (as by :py:func:`phonenumbers.is_valid_number`).

        By default, the Spec supplies a conformer which conforms telephone numbers to
        the international E.164 format, which is globally unique.

        :param tag: an optional tag for the resulting spec
        :param region: an optional two-letter country code which, if provided, will
            be checked against the parsed telephone number's region
        :param is_possible: if True and the input number can be successfully parsed,
            validate that the number is a possible number (it has the right number of
            digits)
        :param is_valid: if True and the input number can be successfully parsed,
            validate that the number is a valid number (it is an an assigned exchange)
        :param conformer: an optional conformer for the value; if one is not provided
            a default conformer will be supplied which conforms the input telephone
            number into E.164 format
        :return: a Spec which validates strings containing telephone numbers
        """

        tag = tag or "phonenumber_str"

        @pred_to_validator(f"Value '{{value}}' is not type 'str'", complement=True)
        def is_str(x: Any) -> bool:
            return isinstance(x, str)

        validators = []

        if region is not None:
            region = region.upper()

            if phonenumbers.country_code_for_region(region) == 0:
                raise ValueError(f"Region '{region}' is not a valid region")

            country_code = phonenumbers.country_code_for_region(region)

            @pred_to_validator(
                f"Parsed telephone number regions ({{value}}) does not "
                f"match expected region {region}",
                complement=True,
                convert_value=lambda p: ", ".join(
                    phonenumbers.region_codes_for_country_code(p.country_code)
                ),
            )
            def validate_phonenumber_region(p: phonenumbers.PhoneNumber) -> bool:
                return p.country_code == country_code

            validators.append(validate_phonenumber_region)

            if conformer is conform_phonenumber:
                conformer = partial(conform_phonenumber, region=region)

        if is_possible:

            @pred_to_validator(
                f"Parsed telephone number '{{value}}' is not possible", complement=True
            )
            def validate_phonenumber_is_possible(p: phonenumbers.PhoneNumber) -> bool:
                return phonenumbers.is_possible_number(p)

            validators.append(validate_phonenumber_is_possible)

        if is_valid:

            @pred_to_validator(
                f"Parsed telephone number '{{value}}' is not valid", complement=True
            )
            def validate_phonenumber_is_valid(p: phonenumbers.PhoneNumber) -> bool:
                return phonenumbers.is_valid_number(p)

            validators.append(validate_phonenumber_is_valid)

        def validate_phonenumber(p: phonenumbers.PhoneNumber) -> Iterator[ErrorDetails]:
            for validate in validators:
                yield from validate(p)

        def str_contains_phonenumber(s: str) -> Iterator[ErrorDetails]:
            try:
                p = phonenumbers.parse(s, region=region)
            except phonenumbers.NumberParseException:
                yield ErrorDetails(
                    message=f"String '{s}' does not contain a telephone number",
                    pred=str_contains_phonenumber,
                    value=s,
                )
            else:
                yield from validate_phonenumber(p)

        return ValidatorSpec.from_validators(
            tag, is_str, str_contains_phonenumber, conformer=conformer
        )


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
    """
    Return a Spec that can validate strings against common rules.

    String Specs always validate that the input value is a :py:class:`str` type.

    If ``length`` is specified, the resulting Spec will validate that input strings
    measure exactly ``length`` characters by by :py:func:`len`. If ``minlength`` is
    specified, the resulting Spec will validate that input strings measure at least
    ``minlength`` characters by by :py:func:`len`.  If ``maxlength`` is specified,
    the resulting Spec will validate that input strings measure not more than
    ``maxlength`` characters by by :py:func:`len`. Only one of ``length``,
    ``minlength``, or ``maxlength`` can be specified. If more than one is specified a
    :py:exc:`ValueError` will be raised. If any length value is specified less than 0
    a :py:exc:`ValueError` will be raised. If any length value is not an
    :py:class:`int` a :py:exc:`TypeError` will be raised.

    If ``regex`` is specified, a Regex pattern will be created by :py:func:`re.compile`
    and :py:func:`re.fullmatch` will be used to validate input strings. If ``format_``
    is specified, the input string will be validated using the Spec registered to
    validate for the string name of the format. If ``conform_format`` is specified,
    the input string will be validated using the Spec registered to validate for the
    string name of the format and the default conformer registered with the format
    Spec will be set as the ``conformer`` for the resulting Spec. Only one of
    ``regex``, ``format_``, and ``conform_format`` may be specified when creating a
    string Spec; if more than one is specified, a :py:exc:`ValueError` will be
    raised.

    String format Specs may be registered using the function
    :py:func:`dataspec.factories.register_str_format_spec`. Alternatively, a string
    format validator function may be registered using the decorator
    :py:func:`dataspec.factories.register_str_format`. String formats may include a
    default conformer which will be applied for ``conform_format`` usages of the
    format.

    Several useful defaults are supplied as part of this library:

     * `iso-date` validates that a string contains a valid ISO 8601 date string
     * `iso-datetime` (Python 3.7+) validates that a string contains a valid ISO 8601
       date and time stamp
     * `iso-time` (Python 3.7+) validates that a string contains a valid ISO 8601
       time string
     * `uuid` validates that a string contains a valid UUID

    :param tag: an optional tag for the resulting spec
    :param length: if specified, the resulting Spec will validate that strings are
        exactly ``length`` characters long by :py:func:`len`
    :param minlength: if specified, the resulting Spec will validate that strings are
        not fewer than ``minlength`` characters long by :py:func:`len`
    :param maxlength: if specified, the resulting Spec will validate that strings are
        not longer than ``maxlength`` characters long by :py:func:`len`
    :param regex: if specified, the resulting Spec will validate that strings match
        the ``regex`` pattern using :py:func:`re.fullmatch`
    :param format_: if specified, the resulting Spec will validate that strings match
        the registered string format ``format``
    :param conform_format: if specified, the resulting Spec will validate that strings
        match the registered string format ``conform_format``; the resulting Spec will
        automatically use the default conformer supplied with the string format
    :param conformer: an optional conformer for the value
    :return: a Spec which validates strings
    """

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


_URL_RESULT_FIELDS = frozenset(
    {
        "scheme",
        "netloc",
        "path",
        "params",
        "fragment",
        "username",
        "password",
        "hostname",
        "port",
    }
)
_URL_DISALLOWED_REGEX_FIELDS = frozenset({"port"})


def url_str_spec(
    tag: Optional[Tag] = None,
    query: Optional[SpecPredicate] = None,
    conformer: Optional[Conformer] = None,
    **kwargs,
) -> Spec:
    """
    Return a spec that can validate URLs against common rules.

    URL string specs always verify that input values are strings and that they can
    be successfully parsed by :py:func:`urllib.parse.urlparse`.

    URL specs can specify a new or existing Spec or spec predicate value to validate
    the query string value produced by calling :py:func:`urllib.parse.parse_qs` on the
    :py:attr:`urllib.parse.ParseResult.query` attribute of the parsed URL result.

    Other restrictions can be applied by passing any one of three different keyword
    arguments for any of the fields (excluding :py:attr:`urllib.parse.ParseResult.query`)
    of :py:class:`urllib.parse.ParseResult`. For example, to specify restrictions on the
    ``hostname`` field, you could use the following keywords:

     * ``hostname`` accepts any value (including :py:obj:`None`) and checks for an
       exact match of the keyword argument value
     * ``hostname_in`` takes a :py:class:``set`` or :py:class:``frozenset`` and
       validates that the `hostname`` field is an exact match with one of the
       elements of the set
     * ``hostname_regex`` takes a :py:class:``str``, creates a Regex pattern from
       that string, and validates that ``hostname`` is a match (by
       :py:func:`re.fullmatch`) with the given pattern

    The value :py:obj:`None` can be used for comparison in all cases. Note that default
    the values for fields of :py:class:`urllib.parse.ParseResult` vary by field, so
    using None may produce unexpected results.

    At most only one restriction can be applied to any given field for the
    :py:class:`urllib.parse.ParseResult`. Specifying more than one restriction for
    a field will produce a :py:exc:`ValueError`.

    At least one restriction must be specified to create a URL string Spec.
    Attempting to create a URL Spec without specifying a restriction will produce a
    :py:exc:`ValueError`.

    Providing a keyword argument for a non-existent field of
    :py:class:`urllib.parse.ParseResult` will produce a :py:exc:`ValueError`.

    :param tag: an optional tag for the resulting spec
    :param query: an optional spec for the :py:class:`dict` created by calling
        :py:func:`urllib.parse.parse_qs` on the :py:attr:`urllib.parse.ParseResult.query`
        attribute of the parsed URL
    :param scheme: if specified, require an exact match for ``scheme``
    :param scheme_in: if specified, require ``scheme`` to match at least one value in the set
    :param schema_regex: if specified, require ``scheme`` to match the regex pattern
    :param netloc: if specified, require an exact match for ``netloc``
    :param netloc_in: if specified, require ``netloc`` to match at least one value in the set
    :param netloc_regex: if specified, require ``netloc`` to match the regex pattern
    :param path: if specified, require an exact match for ``path``
    :param path_in: if specified, require ``path`` to match at least one value in the set
    :param path_regex: if specified, require ``path`` to match the regex pattern
    :param params: if specified, require an exact match for ``params``
    :param params_in: if specified, require ``params`` to match at least one value in the set
    :param params_regex: if specified, require ``params`` to match the regex pattern
    :param fragment: if specified, require an exact match for ``fragment``
    :param fragment_in: if specified, require ``fragment`` to match at least one value in the set
    :param fragment_regex: if specified, require ``fragment`` to match the regex pattern
    :param username: if specified, require an exact match for ``username``
    :param username_in: if specified, require ``username`` to match at least one value in the set
    :param username_regex: if specified, require ``username`` to match the regex pattern
    :param password: if specified, require an exact match for ``password``
    :param password_in: if specified, require ``password`` to match at least one value in the set
    :param password_regex: if specified, require ``password`` to match the regex pattern
    :param hostname: if specified, require an exact match for ``hostname``
    :param hostname_in: if specified, require ``hostname`` to match at least one value in the set
    :param hostname_regex: if specified, require ``hostname`` to match the regex pattern
    :param port: if specified, require an exact match for ``port``
    :param port_in: if specified, require ``port`` to match at least one value in the set
    :param conformer: an optional conformer for the value
    :return: a Spec which can validate that a string contains a URL
    """

    @pred_to_validator(f"Value '{{value}}' is not a string", complement=True)
    def is_str(s: Any) -> bool:
        return isinstance(s, str)

    validators: List[Union[ValidatorFn, ValidatorSpec]] = [is_str]

    child_validators = []
    for url_attr in _URL_RESULT_FIELDS:
        in_attr = kwargs.pop(f"{url_attr}_in", _IGNORE_OBJ_PARAM)
        regex_attr = kwargs.pop(f"{url_attr}_regex", _IGNORE_OBJ_PARAM)
        exact_attr = kwargs.pop(f"{url_attr}", _IGNORE_OBJ_PARAM)

        if (
            sum(
                int(v is not _IGNORE_OBJ_PARAM)
                for v in [in_attr, regex_attr, exact_attr]
            )
            > 1
        ):
            raise ValueError(
                f"URL specs may only specify one of {url_attr}, "
                f"{url_attr}_in, and {url_attr}_regex for any URL attribute"
            )

        attr_validator = _obj_attr_validator(
            "URL",
            url_attr,
            exact_attr,
            regex_attr,
            in_attr,
            disallowed_attrs_regex=_URL_DISALLOWED_REGEX_FIELDS,
        )
        if attr_validator is not None:
            child_validators.append(attr_validator)

    if query is not None:
        query_spec: Optional[Spec] = make_spec(query)
    else:
        query_spec = None

    if kwargs:
        raise ValueError(f"Unused keyword arguments: {kwargs}")

    if query_spec is None and not child_validators:
        raise ValueError(f"URL specs must include at least one validation rule")

    def validate_parse_result(v: ParseResult) -> Iterator[ErrorDetails]:
        for validate in child_validators:
            yield from validate(v)

        if query_spec is not None:
            query_dict = parse_qs(v.query)
            yield from query_spec.validate(query_dict)

    def validate_url(s: str) -> Iterator[ErrorDetails]:
        try:
            url = urlparse(s)
        except ValueError as e:
            yield ErrorDetails(
                message=f"String does not contain a valid URL: {e}",
                pred=validate_url,
                value=s,
            )
        else:
            yield from validate_parse_result(url)

    validators.append(validate_url)

    return ValidatorSpec.from_validators(
        tag or "url_str", *validators, conformer=conformer
    )


def uuid_spec(
    tag: Optional[Tag] = None,
    versions: Optional[Set[int]] = None,
    conformer: Optional[Conformer] = None,
) -> Spec:
    """
    Return a Spec that can validate UUIDs against common rules.

    UUID Specs always validate that the input value is a :py:class:`uuid.UUID` type.

    If ``versions`` is specified, the resulting Spec will validate that input UUIDs
    are the RFC 4122 variant and that they are one of the specified integer versions
    of RFC 4122 variant UUIDs. If ``versions`` specifies an invalid RFC 4122 variant
    UUID version, a :py:exc:`ValueError` will be raised.

    :param tag: an optional tag for the resulting spec
    :param versions: an optional set of integers of 1, 3, 4, and 5 which the input
        :py:class:`uuid.UUID` must match; otherwise, any version will pass the Spec
    :param conformer: an optional conformer for the value
    :return: a Spec which validates UUIDs
    """

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
