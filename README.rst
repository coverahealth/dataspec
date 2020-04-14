Data Spec
=========

.. image:: https://img.shields.io/pypi/v/dataspec.svg?style=flat-square
   :target: https://pypi.org/project/dataspec/
   :alt: Package (on PyPI)

.. image:: https://img.shields.io/pypi/pyversions/dataspec.svg?style=flat-square
   :target: https://pypi.org/project/dataspec/
   :alt: Supported Python Versions

.. image:: https://img.shields.io/pypi/implementation/dataspec.svg?style=flat-square
   :target: https://pypi.org/project/dataspec/
   :alt: Supported Python Implementations

.. image:: https://img.shields.io/circleci/project/github/coverahealth/dataspec/master.svg?style=flat-square
   :target: https://circleci.com/gh/coverahealth/dataspec
   :alt: Build Status (on CircleCI)

.. image:: https://img.shields.io/readthedocs/dataspec?style=flat-square
   :target: https://dataspec.readthedocs.io/
   :alt: Documentation (on ReadTheDocs)

.. image:: https://img.shields.io/github/license/coverahealth/dataspec.svg?style=flat-square
   :target: https://github.com/coverahealth/dataspec/blob/master/LICENSE
   :alt: MIT License

Dataspec is a data specification and normalization toolkit written in pure Python.
With Dataspec, you can create Specs to validate and normalize data of almost any
shape. Dataspec is inspired by Clojure's `spec <https://clojure.org/guides/spec>`_
library.

What are Specs?
---------------

Specs are declarative data specifications written in pure Python code. Specs can be
created using the generic Spec constructor function ``s``. Specs provide two useful and
related functions. The first is to evaluate whether an arbitrary data structure
satisfies the specification. The second function is to conform (or normalize) valid
data structures into a canonical format.

The simplest Specs are based on common predicate functions, such as
``lambda x: isinstance(x, str)`` which asks "Is the object x an instance of ``str``?".
Fortunately, Specs are not limited to being created from single predicates. Specs can
also be created from groups of predicates, composed in a variety of useful ways, and
even defined for complex data structures. Because Specs are ultimately backed by
pure Python code, any question that you can answer about your data in code can be
encoded in a Spec.

Features
--------

* Simple API using primarily native Python types and data structures

* Stateless, immutable Spec objects are designed to be created once, reused, and composed

* Rich error objects point to the exact location of the error in the input value

* Builtin factories for many common validations

Installation
------------

Dataspec is developed on `GitHub <https://github.com/coverahealth/dataspec>`_ and hosted
on `PyPI <https://pypi.org/project/dataspec/>`_. You can fetch Dataspec using ``pip``:

.. code-block:: bash

   pip install dataspec

To enable support for phone number specs or arbitrary date strings, you can choose the
extras when you install:

.. code-block:: bash

   pip install dataspec[dates]
   pip install dataspec[phonenumbers]

Getting Started
---------------

To begin using the ``dataspec`` library, you can simply import the ``s`` object:

.. code-block:: python

   from dataspec import s

``s`` is a generic constructor for creating new Specs. Many useful Specs can be
composed from basic Python objects like types, functions, and data structures. The
"Hello, world!" equivalent for creating new Specs might be a simple Spec that validates
that an input is a string (a Python ``str`` ). We can do this by simply passing the
Python ``str`` type directly to ``s``. When ``s`` receives an instance of a ``type``
object, it assumes you want to create a Spec that validates input values are of that
type:

.. code-block:: python

   spec = s(str)
   spec.is_valid("a string")  # True
   spec.is_valid(3)           # False

Often you want to assert more than one condition on an input value. After all, it's
fairly trivial to assert type checks on a value. In fact, this may even be done by
a deserialization library on your behalf. Perhaps you're interested in checking that
your input is a string and that it contains only numbers and hyphens. ``dataspec`` lets
you define Specs with boolean logic, which can be useful for asserting multiple
conditions on your input:

.. code-block:: python

   spec = s.all(str, lambda s: all(c.isdecimal() or c == "-" for c in s))
   spec.is_valid("212-867-5309")     # True
   spec.is_valid("Philip Jennings")  # False

Composition is at the heart of ``dataspec`` 's design. In the previous example, we
learned a few useful things. First, ``s`` is actually a callable object with static
methods which help produce other sorts of Specs. Second, we can see that when we
pass objects understood to ``s`` into various Spec constructors, they are automatically
coerced into the appropriate Spec type. Here, we passed a ``type``, which we used
previously. We also passed in a function of one argument returning a boolean; in
``dataspec``, these are called predicates and they are turned into Specs which validate
input values if the function returns ``True`` and fail otherwise. Finally, we learned
that ``s.all`` can be used to produce ``and`` -type boolean logic between different
Specs. (You can produce ``or`` Specs using ``s.any``).

In the previous example, we used the ``and`` logic to check for our conditions to show
various different features of ``dataspec``. However, in real code you'd likely take
advantage of ``dataspec`` 's builtin ``s.str`` factory, which can assert several useful
properties of strings (in addition to the basic ``isinstance`` check). In the case
above, perhaps we really wanted to check for a US ZIP code (with the trailing 4 digits).
We can perform that check using a simple regex string validator:

.. code-block:: python

   spec = s.str("us_zip_plus_4", regex=r"\d{5}\-\d{4}")
   spec.is_valid("10001-3093")  # True
   spec.is_valid("10001")       # False
   spec.is_valid("N0L 1E0")     # False

Scalar Specs like the one above are trivially different from the same checks you could
write in raw Python. The real power of ``dataspec`` comes from its ability to compose
Specs for larger, nested data structures. Suppose you were accepting a physician
profile object via a JSON API and you wanted to validate that the physician licenses
were valid in all of the states you operate in:

.. code-block:: python

   operating_states = s("operating_states", {"CA", "GA", "NY"})
   license_states = s("license_states", [operating_states, {"kind": list}])
   license_states.is_valid(["CA", "NY"])  # True
   license_states.is_valid(["SD", "GA"])  # False, you do not operate in South Dakota
   license_states.is_valid({"CA"})        # False, as the input collection is a set

In the previous example, we learned a bit more about ``dataspec``. First, we can see
that Spec objects are designed to be reused. We declared ``operating_states`` as a
separate Spec from ``license_states`` with the intent that we could use it as a
component of other Specs. Specs are immutable and stateless, so they can be reused in
other Specs without issue. Next, we can see that we're expecting a collection, indicated
by the Python ``list`` wrapping ``operating_states`` in the ``license_states`` Spec.
In particular, we are expecting exactly a ``list``, not a ``set`` or ``tuple``.
Third, we are expecting a limited set of enumerated values, indicated by
``operating_states`` being a ``set``. Values not in the set are rejected. ``dataspec``
also supports using Python's ``Enum`` objects for defining enumerated types.

We did declare two separate Specs and pass both to ``s`` directly. However, we could
have declared the entire Spec inline and ``s`` would have converted each child value
into a Spec automatically: ``s([{"CA", "GA", "NY"}, {"kind": list}])`` .

Building on the previous example, let's suppose we want to validate a simplified
version of that physician profile object. Spec is great for validating data at your
application boundaries. You can pass it your deserialized input values and it will
help you ensure that you're receiving data in the shape your internal services
expect:

.. code-block:: python

   spec = s(
       "user-profile",
       {
           "id": s.str("id", format_="uuid"),
           "first_name": s.str("first_name"),
           "last_name": s.str("last_name"),
           "date_of_birth": s.str("date_of_birth", format_="iso-date"),
           s.opt("gender"): s("gender", {"M", "F"}),
           "license_states": license_states,  # using the previously defined Spec
       }
   )
   spec.is_valid(  # True
       {
           "id": "e1bc9fb2-a4d3-4683-bfef-3acc61b0edcc",
           "first_name": "Carl",
           "last_name": "Sagan",
           "date_of_birth": "1996-12-20",
           "license_states": ["CA"],
       }
   )
   spec.is_valid(  # False; the optional "gender" key included an invalid value
       {
           "id": "e1bc9fb2-a4d3-4683-bfef-3acc61b0edcc",
           "first_name": "Carl",
           "last_name": "Sagan",
           "date_of_birth": "1996-12-20",
           "gender": "O",
           "license_states": ["CA"],
       }
   )
   spec.is_valid(  # True; note that extra keys _are ignored_
       {
           "id": "958e2f55-5fdf-4b84-a522-a0765299ba4b",
           "first_name": "Marie",
           "last_name": "Curie",
           "date_of_birth": "1867-11-07",
           "gender": "F",
           "license_states": ["NY", "GA"],
           "occupation": "Chemist",
       }
   )
   spec.is_valid(  # False; the "license_states" includes the invalid value "TX"
       {
           "id": "958e2f55-5fdf-4b84-a522-a0765299ba4b",
           "first_name": "Marie",
           "last_name": "Curie",
           "date_of_birth": "1867-11-07",
           "license_states": ["TX"],
       }
   )

``dataspec`` includes plenty of additional functionality which is not discussed above.
Read more at `Read the Docs <https://dataspec.readthedocs.io>`_.

Why not X?
----------

Python's ecosystem features a rich collection of data validation and normalization
tools, so a new entrant in the space naturally begs the question "why didn't you just
use X instead?". Before creating Dataspec, we surveyed a wide variety of different
tools and had even used one or two in our production service. All of these tools are
generally successful at validating data, but each had some issue that caused us to
pass.

* Many of the libraries in this space primarily help validate data, but do not always
  help you normalize or conform that data after it has been validated. Dataspec
  provides validation and conformation out of the box.

* Libraries which do feature validation and normalization often complect these two
  steps. Dataspec validation is a discrete step that occurs before conformation, so
  it is easy to reason about failures in validation.

* Some of the libraries we tried were stateful or leaned too heavily on mutability.
  We tend to prefer immutable and stateless objects where mutability and state is not
  required. Specs in Dataspec are completely stateless and conformation always produces
  a new value. This is certainly more costly than mutating inputs, but mutating code
  is harder to reason about and is a major source of bugs, so we prefer to avoid it.

* Many libraries we surveyed focused on defining validations from the top-down, rather
  than encouraging composition. Specs in Dataspec are designed to be created once,
  reused, and composed, rather than requiring a separate definition for each usage.

License
-------

MIT License
