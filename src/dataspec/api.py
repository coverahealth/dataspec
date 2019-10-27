import functools
from typing import Mapping, Optional, Tuple, Union

from dataspec.base import (
    Conformer,
    Spec,
    SpecPredicate,
    Tag,
    ValidationError,
    make_spec,
)
from dataspec.factories import (
    all_spec,
    any_spec,
    bool_spec,
    bytes_spec,
    date_spec,
    datetime_spec,
    email_spec,
    every_spec,
    nilable_spec,
    num_spec,
    obj_spec,
    opt_key,
    str_spec,
    time_spec,
    url_str_spec,
    uuid_spec,
)

try:
    from dataspec.factories import datetime_str_spec
except ImportError:
    datetime_str_spec = None  # type: ignore


try:
    from dataspec.factories import phonenumber_spec
except ImportError:
    phonenumber_spec = None  # type: ignore


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

    def __call__(
        self, *args: Union[Tag, SpecPredicate], conformer: Optional[Conformer] = None
    ) -> Spec:
        return make_spec(*args, conformer=conformer)

    # Spec factories
    any = staticmethod(any_spec)
    all = staticmethod(all_spec)
    bool = staticmethod(bool_spec)
    bytes = staticmethod(bytes_spec)
    date = staticmethod(date_spec)
    email = staticmethod(email_spec)
    every = staticmethod(every_spec)
    inst = staticmethod(datetime_spec)
    nilable = staticmethod(nilable_spec)
    num = staticmethod(num_spec)
    obj = staticmethod(obj_spec)
    str = staticmethod(str_spec)
    time = staticmethod(time_spec)
    url = staticmethod(url_str_spec)
    uuid = staticmethod(uuid_spec)

    # Builtin pre-baked specs
    is_any = every_spec("is_any")
    is_bool = bool_spec("is_bool")
    is_bytes = bytes_spec("is_bytes")
    is_date = date_spec("is_date")
    is_email = email_spec("is_email")
    is_false = bool_spec("is_false", allowed_values={False})
    is_float = num_spec("is_float", type_=float)
    is_inst = datetime_spec("is_inst")
    is_int = num_spec("is_int", type_=int)
    is_num = num_spec("is_num")
    is_str = str_spec("is_str")
    is_time = time_spec("is_str")
    is_true = bool_spec("is_true", allowed_values={True})
    is_uuid = uuid_spec("is_true")

    # Utility functions
    explain = staticmethod(_explain)
    fdef = staticmethod(_fdef)
    opt = staticmethod(opt_key)

    # Conditionally available spec factories
    if datetime_str_spec is not None:
        inst_str = staticmethod(datetime_str_spec)

    if phonenumber_spec is not None:
        phone = staticmethod(phonenumber_spec)


s = SpecAPI()
