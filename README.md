# Data Spec

[![PyPI](https://img.shields.io/pypi/v/dataspec.svg?style=flat-square)](https://pypi.org/project/dataspec/) [![python](https://img.shields.io/pypi/pyversions/dataspec.svg?style=flat-square)](https://pypi.org/project/dataspec/) [![pyimpl](https://img.shields.io/pypi/implementation/dataspec.svg?style=flat-square)](https://pypi.org/project/dataspec/) [![CircleCI](	https://img.shields.io/circleci/project/github/coverahealth/dataspec/master.svg?style=flat-square)](https://circleci.com/gh/coverahealth/dataspec) [![license](https://img.shields.io/github/license/coverahealth/dataspec.svg?style=flat-square)](https://github.com/coverahealth/dataspec/blob/master/LICENSE)

## What are Specs?

Specs are declarative data specifications written in pure Python code. Specs can be
created using the Spec utility function `s`. Specs provide two useful and related
functions. The first is to evaluate whether an arbitrary data structure satisfies
the specification. The second function is to conform (or normalize) valid data
structures into a canonical format.

The simplest Specs are based on common predicate functions, such as
`lambda x: isinstance(x, str)` which asks "Is the object x an instance of `str`?".
Fortunately, Specs are not limited to being created from single predicates. Specs can
also be created from groups of predicates, composed in a variety of useful ways, and
even defined for complex data structures. Because Specs are ultimately backed by
pure Python code, any question that you can answer about your data in code can be
encoded in a Spec.

## How to Use

To begin using the `spec` library, you can simply import the `s` object:

```python
from dataspec import s
```

Nearly all of the useful functionality in `spec` is packed into `s`.

### Spec API

`s` is a generic Spec constructor, which can be called to generate new Specs from
a variety of sources:

 * Enumeration specs:
     * Using a Python `set` or `frozenset`: `s({"a", "b", ...})`, or
     * Using a Python `Enum` like `State`, `s(State)`.
 * Collection specs:
     * Using a Python `list`: `s([State])`
 * Mapping type specs:
     * Using a Python `dict`: `s({"name": s.is_str})`
 * Tuple type specs:
     * Using a Python `tuple`: `s((s.is_str, s.is_num))`
 * Specs based on:
     * Using a standard Python predicate: `s(lambda x: x > 0)`
     * Using a Python function yielding `ErrorDetails`

Specs are designed to be composed, so each of the above spec types can serve as the
base for more complex data definitions. For collection, mapping, and tuple type Specs,
Specs will be recursively created for child elements if they are types understood
by `s`.

Specs may also optionally be created with "tags", which are just string names provided
in `ErrorDetails` objects emitted by Spec instance `validate` methods. Specs are
required to have tags and all builtin Spec factories will supply a default tag if
one is not given.

The `s` API also includes several Spec factories for common Python types such as
`bool`, `bytes`, `date`, `datetime` (via `s.inst`), `float` (via `s.num`), `int`
(via `s.num`), `str`, `time`, and `uuid`.

`s` also includes several pre-built Specs for basic types which are useful if you
only want to verify that a value is of a specific type. All the pre-built Specs
are supplied as `s.is_{type}` on `s`.

All Specs provide the following API:

 * `Spec.is_valid(x)` returns a `bool` indicating if `x` is valid according to the
   Spec definition
 * `Spec.validate(x)` yields consecutive `ErrorDetails` describing every spec
   violation for `x`. By definition, if `next(Spec.validate(x))` returns an
   empty generator, then `x` satisfies the Spec.
 * `Spec.validate_ex(x)` throws a `ValidationError` containing the full list of
   `ErrorDetails` of errors occurred validating `x` if any errors are encountered.
   Otherwise, returns `None`.
 * `Spec.conform(x)` attempts to conform `x` according to the Spec conformer iff
   `x` is valid according to the Spec. Otherwise returns `INVALID`.
 * `Spec.conform_valid(x)` conforms `x` using the Spec conformer, without checking
   first if `x` is valid. Useful if you wish to check your data for validity and
   conform it in separate steps without incurring validation costs twice.
 * `Spec.with_conformer(c)` returns a new Spec instance with the Conformer `c`.
   The old Spec instance is not modified.
 * `Spec.with_tag(t)` returns a new Spec instance with the Tag `t`. The old Spec
   instance is not modified.

### Scalar Specs

The simplest data specs are those which evaluate Python's builtin scalar types:
strings, integers, floats, and booleans.

You can create a spec which validates strings with `s.str()`. Common string
validations can be specified as keyword arguments, such as the min/max length or a
matching regex. If you are only interested in validating that a value is a string
without any further validations, spec features the predefined spec `s.is_str` (note
no function call required).

Likewise, numeric specs can be created using `s.num()`, with several builtin
validations available as keyword arguments such as min/max value and narrowing down
the specific numeric types. If you are only interested in validating that a value is
numeric, you can use the builtin `s.is_num` or `s.is_int` or `s.is_float` specs.

### Predicate Specs

You can define a spec using any simple predicate you may have by passing the predicate
directly to the `s` function, since not every valid state of your data can be specified
using existing specs.

```python
spec = s(lambda id_: uuid.UUID(id_).version == 4)
spec.is_valid("4716df50-0aa0-4b7d-98a4-1f2b2bcb1c6b")  # True
spec.is_valid("b4e9735a-ee8c-11e9-8708-4c327592fea9")  # False
```

### UUID Specs

In the previous section, we used a simple predicate to check that a UUID was a certain
version of an RFC 4122 variant UUID. However, `spec` includes builtin UUID specs which
can simplify the logic here:

```python
spec = s.uuid(versions={4})
spec.is_valid("4716df50-0aa0-4b7d-98a4-1f2b2bcb1c6b")  # True
spec.is_valid("b4e9735a-ee8c-11e9-8708-4c327592fea9")  # False
```

Additionally, if you are only interested in validating that a value is a UUID, the
builting spec `s.is_uuid` is available.

### Date Specs

`spec` includes some builtin Specs for Python's `datetime`, `date`, and `time` classes.
With the builtin specs, you can validate that any of these three class types are before
or after a given. Suppose you want to verify that someone is 18 by checking their date
of birth:

```python
spec = s.date(after=date.today() - timedelta(years=18))
spec.is_valid(date.today() - timedelta(years=21))  # True
spec.is_valid(date.today() - timedelta(years=12))  # False
```

For datetimes (instants) and times, you can also use `is_aware=True` to specify that
the instance be timezone-aware (e.g. not naive).

You can use the builtins `s.is_date`, `s.is_inst`, and `s.is_time` if you only want to
validate that a value is an instance of any of those classes.

### Set (Enum) Specs

Commonly, you may be interested in validating that a value is one of a constrained set
of known values. In Python code, you would use an `Enum` type to model these values.
To define an enumermation spec, you can use either pass an existing `Enum` value into
your spec:

```python
class YesNo(Enum):
    YES = "Yes"
    NO = "No"

s(YesNo).is_valid("Yes")    # True
s(YesNo).is_valid("Maybe")  # False
```

Any valid representation of the `Enum` value would satisfy the spec, including the
value, alias, and actual `Enum` value (like `YesNo.NO`).

Additionally, for simpler cases you can specify an enum using Python `set`s (or
`frozenset`s):

```python
s({"Yes", "No"}).is_valid("Yes")    # True
s({"Yes", "No"}).is_valid("Maybe")  # False
```

### Collection Specs

Specs can be defined for values in homogenous collections as well. Define a spec for
a homogenous collection as a list passed to `s` with the first element as the Spec
for collection elements:

```python
s([s.num(min_=0)]).is_valid([1, 2, 3, 4])  # True
s([s.num(min_=0)]).is_valid([-11, 2, 3])   # False
```

You may also want to assert certain conditions that apply to the collection as a whole.
Spec allows you to specify an _optional_ dictionary as the second element of the list
with a few possible rules applying to the collection as a whole, such as length and
collection type.

```python
s([s.num(min_=0), {"kind": list}]).is_valid([1, 2, 3, 4])  # True
s([s.num(min_=0), {"kind": list}]).is_valid({1, 2, 3, 4})  # False
```

Collection specs conform input collections by applying the element conformer(s) to each
element of the input collection. Callers can specify an `"into"` key in the collection
options dictionary as part of the spec to specify which type of collection is emitted
by the collection spec default conformer. Collection specs which do not specify the
`"into"` collection type will conform collections into the same type as the input
collection.

### Tuple Specs

Specs can be defined for heterogenous collections of elements, which is often the use
case for Python's `tuple` type. To define a spec for a tuple, pass a tuple of specs for
each element in the collection at the corresponding tuple index:

```
s(
    (
        s.str("id", format_="uuid"),
        s.str("first_name"),
        s.str("last_name"),
        s.str("date_of_birth", format_="iso-date"),
        s("gender", {"M", "F"}),
    )
)
```

Tuple specs conform input tuples by applying each field's conformer(s) to the fields of
the input tuple to return a new tuple. If each field in the tuple spec has a unique tag
and the tuple has a custom tag specified, the default conformer will yield a
`namedtuple` with the tuple spec tag as the type name and the field spec tags as each
field name. The type name and field names will be munged to be valid Python
identifiers.

### Mapping Specs

Specs can be defined for mapping/associative types and objects. To define a spec for a
mapping type, pass a dictionary of specs to `s`. The keys should be the expected key
value (most often a string) and the value should be the spec for values located in that
key. If a mapping spec contains a key, the spec considers that key _required_. To
specify an _optional_ key in the spec, wrap the key in `s.opt`. Optional keys will
be validated if they are present, but allow the map to exclude those keys without
being considered invalid.

```python
s(
    {
        "id": s.str("id", format_="uuid"),
        "first_name": s.str("first_name"),
        "last_name": s.str("last_name"),
        "date_of_birth": s.str("date_of_birth", format_="iso-date"),
        "gender": s("gender", {"M", "F"}),
        s.opt("state"): s("state", {"CA", "GA", "NY"}),
    }
)
```

Above the key `"state"` is optional in tested  values, but if it is provided it must
be one of `"CA"`, `"GA"`, or `"NY"`.

*Note:* Mapping specs do not validate that input values _only_ contain the expected
set of keys. Extra keys will be ignored. This is intentional behavior.

Mapping specs conform input dictionaries by applying each field's conformer(s) to
the fields of the input map to return a new dictionary. As a consequence, the value
returned by the mapping spec default conformer will not include any extra keys
included in the input. Optional keys will be included in the conformed value if they
appear in the input map.

### Combination Specs

In most of the previous examples, we used basic builtin Specs. However, real world
data often more nuanced specifications for data. Fortunately, Specs were designed
to be composed. In particular, Specs can be composed using standard boolean logic.
To specify an `or` spec, you can use `s.any(...)` with any `n` specs.

```python
spec = s.any(s.str(format_="uuid"), s.str(maxlength=0))
spec.is_valid("4716df50-0aa0-4b7d-98a4-1f2b2bcb1c6b")  # True
spec.is_valid("")            # True
spec.is_valid("3837273723")  # False
```

Similarly, to specify an `and` spec, you can use `s.all(...)` with any `n` specs:

```python
spec = s.all(s.str(format_="uuid"), s(lambda id_: uuid.UUID(id_).version == 4))
spec.is_valid("4716df50-0aa0-4b7d-98a4-1f2b2bcb1c6b")  # True
spec.is_valid("b4e9735a-ee8c-11e9-8708-4c327592fea9")  # False
```

`and` Specs apply each child Spec's conformer to the value during validation,
so you may assume the output of the previous Spec's conformer in subsequent
Specs.

### Examples

Suppose you'd like to define a Spec for validating that a string is at least 10
characters long (ignore encoding nuances), you could define that as follows:

```python
spec = s.str(minlength=10)
spec.is_valid("a string")         # False
spec.is_valid("London, England")  # True
```

Or perhaps you'd like to check that every number in a list is above a certain value:

```python
spec = s([s.num(min_=70), {"kind": list}])
spec.is_valid([70, 83, 92, 99])  # True
spec.is_valid({70, 83, 92, 99})  # False, as the input collection is a set
spec.is_valid([43, 66, 80, 93])  # False, not all numbers above 70
```

A more realistic case for a Spec is validating incoming data at the application
boundaries. Suppose you're accepting a user profile submission as a JSON object over
an HTTP endpoint, you could validate the data like so:

```python
spec = s(
    "user-profile",
    {
        "id": s.str("id", format_="uuid"),
        "first_name": s.str("first_name"),
        "last_name": s.str("last_name"),
        "date_of_birth": s.str("date_of_birth", format_="iso-date"),
        "gender": s("gender", {"M", "F"}),
        s.opt("state"): s.str(minlength=2, maxlength=2),
    }
)
spec.is_valid(  # True
    {
        "id": "e1bc9fb2-a4d3-4683-bfef-3acc61b0edcc",
        "first_name": "Carl",
        "last_name": "Sagan",
        "date_of_birth": "1996-12-20",
        "gender": "M",
        "state": "CA",
    }
)
spec.is_valid(  # True; note that extra keys _are ignored_
    {
        "id": "958e2f55-5fdf-4b84-a522-a0765299ba4b",
        "first_name": "Marie",
        "last_name": "Curie",
        "date_of_birth": "1867-11-07",
        "gender": "F",
        "occupation": "Chemist",
    }
)
spec.is_valid(  # False; missing "gender" key
    {
        "id": "958e2f55-5fdf-4b84-a522-a0765299ba4b",
        "first_name": "Marie",
        "last_name": "Curie",
        "date_of_birth": "1867-11-07",
    }
)
```

## Concepts

### Predicates

Predicates are functions of one argument which return a boolean. Predicates answer
questions such as "is `x` an instance of `str`?" or "is `n` greater than `0`?".
Frequently in Python, predicates are simply expressions used in an `if` statement.
In functional programming languages (and particularly in Lisps), it is more common
to encode these predicates in functions which can be combined using lambdas or
partials to be reused. Spec encourages that functional paradigm and benefits
directly from it.

Predicate functions should satisfy the `PredicateFn` type and can be wrapped in the
`PredicateSpec` spec type.

### Validators

Validators are like predicates in that they answer the same fundamental questions about
data that predicates do. However, Validators are a Spec concept that allow us to
retrieve richer error data from Spec failures than we can natively with a simple
predicate. Validators are functions of one argument which return 0 or more `ErrorDetails`
instances (typically `yield`ed as a generator) describing the error.

Validator functions should satisfy the `ValidatorFn` type and can be wrapped in the
`ValidatorSpec` spec type.

### Conformers

Conformers are functions of one argument, `x`, that return either a conformed value,
which may be `x` itself, a new value based on `x`, or the special Spec value
`INVALID` if the value cannot be conformed.

All specs may include conformers. Scalar spec types such as `PredicateSpec` and
`ValidatorSpec` simply return their argument if it satisfies the spec. Specs for
more complex data structures supply a default conformer which produce new data
structures after applying any child conformation functions to the data structure
elements.

### Tags

All Specs can be created with optional tags, specified as a string in the first
positional argument of any spec creation function. Tags are useful for providing
useful names for specs in debugging and validation messages.

## TODOs
 - in dict specs, default child spec tag from corresponding dictionary key
 - break out conformers into separate object? main value would be to propogate
   `.conform_valid()` calls all the way through; currently they don't propogate
   past collection, dict, and tuple specs
   
## License

MIT License
