.. _usage:

Usage
=====

.. contents::
   :depth: 3

.. _constructing_specs:

Constructing Specs
------------------

To begin using the ``dataspec`` library, you can simply import the :py:func:`dataspec.s`
object:

.. code-block:: python

   from dataspec import s

:py:func:`dataspec.s` is a generic Spec constructor, which can be called to generate
new Specs from a variety of sources. It is a singleton instance of
:py:class:`dataspec.SpecAPI` and nearly all of the factory or convenience methods
below are available as static methods on :py:func:`dataspec.s`.

Specs are designed to be composed, so each of the spec types below can serve as the
base for more complex data definitions. For collection, mapping, and tuple type Specs,
Specs will be recursively created for child elements if they are types understood
by :py:func:`dataspec.s`.

Specs may also optionally be created with :ref:`tags`, which are just string names
provided in :py:class:`dataspec.ErrorDetails` objects emitted by Spec instance
:py:meth:`dataspec.Spec.validate` methods. For :py:func:`dataspec.s`, tags may be
provided as the first positional argument. Specs are required to have tags and all
builtin Spec factories will supply a default tag if one is not given.

.. _predicates_and_validators:

Predicate and Validators
------------------------

You can define a spec using any simple predicate you may have by passing the predicate
directly to the ``s`` function, since not every valid state of your data can be specified
using existing specs.

.. code-block:: python

   spec = s(lambda id_: uuid.UUID(id_).version == 4)
   spec.is_valid("4716df50-0aa0-4b7d-98a4-1f2b2bcb1c6b")  # True
   spec.is_valid("b4e9735a-ee8c-11e9-8708-4c327592fea9")  # False

Simple predicates make fine specs, but are unable to provide more details to the caller
about exactly why the input value failed to validate. Validator specs directly yield
:py:class:`dataspec.ErrorDetails` objects which can indicate more precisely why the
input data is failing to validate.

.. code-block:: python

   def _is_positive_int(v: Any) -> Iterable[ErrorDetails]:
       if not isinstance(v, int):
           yield ErrorDetails(
               message="Value must be an integer", pred=_is_positive_int, value=v
           )
       elif v < 1:
           yield ErrorDetails(
               message="Number must be greater than 0", pred=_is_positive_int, value=v
           )

   spec = s(_is_positive_int)
   spec.is_valid(5)      # True
   spec.is_valid(0.5)    # False
   spec.validate_ex(-1)  # ValidationError(errors=[ErrorDetails(message="Number must be greater than 0", ...)])

Simple predicates can be converted into validator functions using the builtin
:py:func:`pred_to_validator` decorator:

.. code-block:: python

   @pred_to_validator("Number must be greater than 0")
   def _is_positive_num(v: Union[int, float]) -> bool:
       return v > 0

   spec = s(_is_positive_num)
   spec.is_valid(5)      # True
   spec.is_valid(0.5)    # True
   spec.validate_ex(-1)  # ValidationError(errors=[ErrorDetails(message="Number must be greater than 0", ...)])

.. _type_specs:

Type Specs
----------

You can define a Spec that validates input values are instances of specific class types
by simply passing a Python type directly to the ``s`` constructor:

.. code-block:: python

   spec = s(str)
   spec.is_valid("a string")  # True
   spec.is_valid(3)           # False

.. note::

   ``s(None)`` is a shortcut for ``s(type(None))``.

.. _factories_usage:

Factories
---------

The ``s`` API also includes several Spec factories for common Python types such as
``bool``, ``bytes``, ``date``, ``datetime`` (via ``s.inst``), ``float`` (via ``s.num``),
``int`` (via ``s.num``), ``str``, ``time``, and ``uuid``.

``s`` also includes several pre-built Specs for basic types which are useful if you
only want to verify that a value is of a specific type. All the pre-built Specs
are supplied as `s.is_{type}` on ``s``.

.. _string_specs:

String Specs
^^^^^^^^^^^^

You can create a spec which validates strings with :py:meth:`dataspec.SpecAPI.str`.
Common string validations can be specified as keyword arguments, such as the min/max
length or a matching regex. If you are only interested in validating that a value is
a string without any further validations, spec features the predefined spec
``s.is_str`` (note no function call required).

.. _numeric_specs:

Numeric Specs
^^^^^^^^^^^^^

Likewise, numeric specs can be created using :py:meth:`dataspec.SpecAPI.num` , with
several builtin validations available as keyword arguments such as min/max value and
narrowing down the specific numeric types. If you are only interested in validating
that a value is numeric, you can use the builtin ``s.is_num`` or ``s.is_int`` or
``s.is_float`` specs.

.. _uuid_specs:

UUID Specs
^^^^^^^^^^

In a previous section, we used a simple predicate to check that a UUID was a certain
version of an RFC 4122 variant UUID. However, ``dataspec`` includes the builtin UUID
spec factory :py:meth:`dataspec.SpecAPI.uuid` which can simplify the logic here:

.. code-block:: python

   spec = s.uuid(versions={4})
   spec.is_valid("4716df50-0aa0-4b7d-98a4-1f2b2bcb1c6b")  # True
   spec.is_valid("b4e9735a-ee8c-11e9-8708-4c327592fea9")  # False

Additionally, if you are only interested in validating that a value is a UUID, the
builting spec ``s.is_uuid`` is available.

.. _time_and_date_specs:

Time and Date Specs
^^^^^^^^^^^^^^^^^^^

``dataspec`` includes some builtin Specs for Python's ``datetime``, ``date``, and
``time`` classes. With the builtin specs, you can validate that any of these three
class types are before or after a given. Suppose you want to verify that someone is 18
by checking their date of birth:

.. code-block:: python

   spec = s.date(after=date.today() - timedelta(years=18))
   spec.is_valid(date.today() - timedelta(years=21))  # True
   spec.is_valid(date.today() - timedelta(years=12))  # False

For datetimes (instants) and times, you can also use ``is_aware=True`` to specify that
the instance be timezone-aware (e.g. not naive).

You can use the builtins ``s.is_date``, ``s.is_inst``, and ``s.is_time`` if you only
want to validate that a value is an instance of any of those classes.

.. note::

   ``dataspec`` supports specs for arbitrary date strings if you have
   ``python-dateutil`` installed. See :py:meth:`dataspec.SpecAPI.inst_str` for info.

.. _phone_number_specs:

Phone Number Specs
^^^^^^^^^^^^^^^^^^

``dataspec`` supports creating Specs for validating telephone numbers from strings
using :py:meth:`dataspec.SpecAPI.phone` *if you have the*
`phonenumbers <https://github.com/daviddrysdale/python-phonenumbers>`_ *library
installed*. Telephone number Specs can validate that a telephone number is merely
formatted correctly or they can validate that a telephone number is both possible
and valid (via ``phonenumbers`` ).

.. code-block:: python

   spec = s.phone(region="US")
   spec.is_valid("(212) 867-5309")  # True
   spec.conform("(212) 867-5309")   # "+12128675309"
   spec.is_valid("(22) 867-5309")   # False

.. _email_address_and_url_specs:

Email Address and URL Specs
^^^^^^^^^^^^^^^^^^^^^^^^^^^

``dataspec`` features Spec factories for validating email addresses using
:py:meth:`dataspec.SpecAPI.email` and URLs using :py:meth:`dataspec.SpecAPI.url`.

Email addresses are validated using Python's builtin ``email.headerregistry.Address``
class to parse email addresses into username and domain. For each of ``username`` and
``domain`` , you may validate that the value is an exact match, is one of a set of
possible matches, or that it matches a regex pattern. To produce a Spec which only
validates email addresses from ``gmail.com`` or ``googlemail.com``:

.. code-block:: python

   spec = s.email(domain_in={"gmail.com", "googlemail.com"})
   spec = s.email(domain_regex=r"(gmail|googlemail)\.com")
   spec = s.email(domain="gmail.com")  # Don't allow "googlemail.com" email addresses

No more than one keyword filter may be supplied for either of ``username`` or
``domain``.

URLs are validated using Python's builtin ``urllib`` module to parse URLs into their
constituent components: ``scheme`` , ``netloc`` , ``path`` , ``params`` , ``fragment`` ,
``username`` , ``password`` , ``hostname``, and ``port``. URL Specs may optionally
provide a Spec for the ``dict`` created by parsing the query-string (if present) for
the URL. Specs for each of the components of a URL allow the same filters as described
above for email addresses. For more information, see :py:meth:`dataspec.SpecAPI.url`.

.. _enumeration_specs:

Enumeration (Set) Specs
-----------------------

Commonly, you may be interested in validating that a value is one of a constrained set
of known values. In Python code, you would use an ``Enum`` type to model these values.
To define an enumermation spec, you can pass an existing ``Enum`` value into
:py:func:`dataspec.s` :

.. code-block:: python

   class YesNo(Enum):
       YES = "Yes"
       NO = "No"

   s(YesNo).is_valid("Yes")    # True
   s(YesNo).is_valid("Maybe")  # False

Any valid representation of the ``Enum`` value would satisfy the spec, including the
value, alias, and actual ``Enum`` value (like ``YesNo.NO``).

Additionally, for simpler cases you can specify an enum using Python ``set`` s (or
``frozenset`` s):

.. code-block:: python

   s({"Yes", "No"}).is_valid("Yes")    # True
   s({"Yes", "No"}).is_valid("Maybe")  # False

.. _collection_specs:

Collection Specs
----------------

Specs can be defined for values in homogenous collections as well. Define a spec for
a homogenous collection as a list passed to :py:func:`dataspec.s` with the first
element as the Spec for collection elements:

.. code-block:: python

   s([s.num(min_=0)]).is_valid([1, 2, 3, 4])  # True
   s([s.num(min_=0)]).is_valid([-11, 2, 3])   # False

You may also want to assert certain conditions that apply to the collection as a whole.
``dataspec`` allows you to specify an *optional* dictionary as the second element of
the list with a few possible rules applying to the collection as a whole, such as
length and collection type.

.. code-block:: python

   s([s.num(min_=0), {"kind": list}]).is_valid([1, 2, 3, 4])  # True
   s([s.num(min_=0), {"kind": list}]).is_valid({1, 2, 3, 4})  # False

Collection specs conform input collections by applying the element conformer(s) to each
element of the input collection. Callers can specify an ``"into"`` key in the collection
options dictionary as part of the spec to specify which type of collection is emitted
by the collection spec default conformer. Collection specs which do not specify the
``"into"`` collection type will conform collections into the same type as the input
collection.

.. _mapping_specs:

Mapping Specs
-------------

Specs can be defined for mapping/associative types and objects. To define a spec for a
mapping type, pass a dictionary of specs to ``s``. The keys should be the expected key
value (most often a string) and the value should be the spec for values located in that
key. If a mapping spec contains a key, the spec considers that key *required*. To
specify an *optional* key in the spec, wrap the key in :py:meth:`dataspec.SpecAPI.opt`.
Optional keys will be validated if they are present, but allow the map to exclude those
keys without being considered invalid.

.. code-block:: python

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

Above the key ``"state"`` is optional in tested  values, but if it is provided it must
be one of ``"CA"``, ``"GA"``, or ``"NY"``.

.. note::

   Mapping specs do not validate that input values *only* contain the expected
   set of keys. Extra keys will be ignored. This is intentional behavior.

.. note::

   To apply the mapping Spec key as the tag of the value Spec, use
   :py:meth:`dataspec.SpecAPI.dict_tag` to construct your mapping Spec. For more
   precise control over the value Spec tags, prefer :py:func:`dataspec.s`.

Mapping specs conform input dictionaries by applying each field's conformer(s) to
the fields of the input map to return a new dictionary. As a consequence, the value
returned by the mapping spec default conformer will not include any extra keys
included in the input. Optional keys will be included in the conformed value if they
appear in the input map.

.. _merging_mapping_specs:

Merging Mapping Specs
^^^^^^^^^^^^^^^^^^^^^

TBD

.. _tuple_specs:

Tuple Specs
-----------

Specs can be defined for heterogenous collections of elements, which is often the use
case for Python's ``tuple`` type. To define a spec for a tuple, pass a tuple of specs for
each element in the collection at the corresponding tuple index:

.. code-block:: python

   s(
       (
           s.str("id", format_="uuid"),
           s.str("first_name"),
           s.str("last_name"),
           s.str("date_of_birth", format_="iso-date"),
           s("gender", {"M", "F"}),
       )
   )

Tuple specs conform input tuples by applying each field's conformer(s) to the fields of
the input tuple to return a new tuple. If each field in the tuple spec has a unique tag
and the tuple has a custom tag specified, the default conformer will yield a
``namedtuple`` with the tuple spec tag as the type name and the field spec tags as each
field name. The type name and field names will be munged to be valid Python
identifiers.

.. _combination_specs:

Combination Specs
-----------------

In most of the previous examples, we used basic builtin Specs. However, real world data
often more nuanced specifications for data. Fortunately, Specs were designed to be
composed. In particular, Specs can be composed using standard boolean logic. To specify
an ``or`` spec, you can use :py:meth:`dataspec.SpecAPI.any` with any ``n`` specs.

.. code-block:: python

   spec = s.any(s.str(format_="uuid"), s.str(maxlength=0))
   spec.is_valid("4716df50-0aa0-4b7d-98a4-1f2b2bcb1c6b")  # True
   spec.is_valid("")            # True
   spec.is_valid("3837273723")  # False

Similarly, to specify an ``and`` spec, you can use :py:meth:`dataspec.SpecAPI.all` with
any ``n`` specs:

.. code-block:: python

   spec = s.all(s.str(format_="uuid"), s(lambda id_: uuid.UUID(id_).version == 4))
   spec.is_valid("4716df50-0aa0-4b7d-98a4-1f2b2bcb1c6b")  # True
   spec.is_valid("b4e9735a-ee8c-11e9-8708-4c327592fea9")  # False

.. note::

   ``and`` Specs apply each child Spec's conformer to the value during validation,
   so you may assume the output of the previous Spec's conformer in subsequent
   Specs.

.. note::

   The names ``any`` and ``all`` were chosen because ``or`` and ``and`` are not valid
   Python since they are reserved keywords.

.. _utility_specs:

Utility Specs
-------------

Often when dealing with real world data, you may wish to allow certain values to be
blank or ``None``. We *could* handle these cases with :ref:`combination_specs`, but
since they occur so commonly, ``dataspec`` features a couple of utility Specs for
quickly defining these cases. For cases where ``None`` is a valid value, you can wrap
your Spec with :py:meth:`dataspec.SpecAPI.nilable`. If you are dealing with strings and
need to allow a blank value (as is often the case when handling CSVs), you can wrap
your Spec with :py:meth:`dataspec.SpecAPI.blankable`.

.. code-block:: python

   spec = s.nilable("birth_date", s.str(format_="iso-date"))
   spec.is_valid(None)          # True
   spec.is_valid("1980-09-14")  # True
   spec.is_valid("")            # False
   spec.is_valid("09/14/1980")  # False, because the string is not ISO formatted

   spec = s.blankable("birth_date", s.str(format_="iso-date"))
   spec.is_valid(None)          # False
   spec.is_valid("1980-09-14")  # True
   spec.is_valid("")            # True
   spec.is_valid("09/14/1980")  # False

In certain cases, you may be willing to accept invalid data and overwrite it with a
default value during conformation. For such cases, you can specify a default value
whenever the input value does not pass validation for another spec using
:py:meth:`dataspec.SpecAPI.default`. The value supplied to the ``default`` keyword
argument will be provided by the conformer if the inner Spec does not validate.

.. code-block:: python

   spec = s.default("birth_date_or_none", s.str(format=_"iso-date"), default=None)
   spec.is_valid(None)          # True; conforms to None
   spec.is_valid("1980-09-14")  # True; conforms to "1980-09-14"
   spec.is_valid("")            # True; conforms to None
   spec.is_valid("09/14/1980")  # True; conforms to None

.. note::

   As a consequence of the default value, ``s.default(...)`` Specs consider every value
   valid. If you do not want to permit all values to pass, you should not use
   ``s.default``.

Occasionally, it may be useful to allow any value to pass validation. For these cases
:py:meth:`dataspec.SpecAPI.every` is perfect.

.. note::

   You may want to combine ``s.every(...)`` with ``s.all(...)`` to perform a pre-
   conformation step prior to later steps. In this case, it may still be useful to
   provide a slightly more strict validation to ensure your conformer does not throw
   an exception.

Conformation
------------

Data validation is only one half of the value proposition for using ``dataspec``. After
you've validated that data is valid, the next step is to normalize it into a canonical
format. Conformers are functions of one argument that can accept a validated value and
emit a canonical representation of that value. Conformation is the component of
``dataspec`` that helps you normalize data.

Every Spec value comes with a default conformer. For most Specs, that conformer simply
returns the value it was passed, though a few builtin Specs do provide a richer,
canonicalized version of the input data. For example, :py:meth:`dataspec.SpecAPI.date`
conforms a date (possibly from a ``strptime`` format string) into a ``date`` object.
Note that **none** of the builtin Spec conformers ever modify the data they are passed.
``dataspec`` conformers always create new data structures and return the conformed
values. Custom conformers can modify their data in-flight, but that is not recommended
since it will be harder reason about failures (in particular, if a mutating conformer
appeared in the middle of ``s.all(...)`` Spec and a later Spec produced an error).

Most common Spec workflows will involve validating that your data is, in fact, valid
using :py:meth:`dataspec.Spec.is_valid` or :py:meth:`dataspec.Spec.validate` for richer
error details and then calling :py:meth:`dataspec.Spec.conform_valid` if it is valid
or dealing with the error if not.

User Provided Conformers
^^^^^^^^^^^^^^^^^^^^^^^^

When you create Specs, you can always provide a conformer using the ``conformer``
keyword argument. This function will be called any time you call
:py:meth:`dataspec.Spec.conform` on your Spec or any Spec your Spec is a part of. The
``conformer`` keyword argument for :py:func:`dataspec.s` and other builtin factories
will always apply your conformer as by :py:meth:`dataspec.Spec.compose_conformer` ,
rather than replacing the default conformer. To have your conformer *completely*
replace the default conformer (if one is provided), you can use the
:py:meth:`dataspec.Spec.with_conformer` method on the returned Spec.