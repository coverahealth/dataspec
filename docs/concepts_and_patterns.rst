.. _concepts_and_patterns:

Concepts and Patterns
=====================

.. contents::
   :depth: 3

.. _concepts:

Concepts
--------

.. _composition:

Composition
^^^^^^^^^^^

Specs are designed to be composed, so each of the builtin spec types can serve as the
base for more complex data definitions. For collection, mapping, and tuple type Specs,
Specs will be recursively created for child elements if they are types understood
by :py:func:`dataspec.s`.

.. _predicates:

Predicates
^^^^^^^^^^

Predicates are functions of one argument which return a boolean. Predicates answer
questions such as "is ``x`` an instance of ``str``?" or "is ``n`` greater than ``0``?".
Frequently in Python, predicates are simply expressions used in an ``if`` statement.
In functional programming languages (and particularly in Lisps), it is more common
to encode these predicates in functions which can be combined using lambdas or
partials to be reused. Spec encourages that functional paradigm and benefits
directly from it.

Predicate functions should satisfy the :py:data:`PredicateFn` type and can be wrapped
in the ``PredicateSpec`` spec type.

.. _validators:

Validators
^^^^^^^^^^

Validators are like predicates in that they answer the same fundamental questions about
data that predicates do. However, Validators are a Spec concept that allow us to
retrieve richer error data from Spec failures than we can natively with a simple
predicate. Validators are functions of one argument which return 0 or more
:py:class:`ErrorDetails` instances (typically ``yield`` -ed as a generator) describing
the error.

Validator functions should satisfy the :py:data:`ValidatorFn` type and can be wrapped
in the ``ValidatorSpec`` spec type.

.. _conformers:

Conformers
^^^^^^^^^^

Conformers are functions of one argument, ``x``, that return either a conformed value,
which may be ``x`` itself, a new value based on ``x``, or the special Spec value
``INVALID`` if the value cannot be conformed.

All specs may include conformers. Scalar spec types such as ``PredicateSpec`` and
``ValidatorSpec`` simply return their argument if it satisfies the spec. Specs for
more complex data structures supply a default conformer which produce new data
structures after applying any child conformation functions to the data structure
elements.

.. _tags:

Tags
^^^^

All Specs can be created with optional tags, specified as a string in the first
positional argument of any spec creation function. Tags are useful for providing
useful names for specs in debugging and validation messages.

.. _patterns:

Patterns
--------

.. _factory_pattern:

Factories
^^^^^^^^^

Often when validating documents such as a CSV or a JSON blob, you'll find yourself
writing a series of similar specs again and again. In situations like these, it is
recommended to create a factory function for generating specs consistently. ``dataspec``
uses this pattern for many of the common spec types described above. This encourages
reuse of commonly used specs and should help enforce consistency across your domain.

.. _reuse:

Reuse
^^^^^

Specs are designed to be immutable, so they may be reused in many different contexts.
Often, the only thing that changes between uses is the tag or conformer. Specs provide
a convenient API for generating copies of themselves (not modifying the original) which
update only the relevant attribute. Additionally, Specs can be combined in many useful
ways to avoid having to redefine common validations repeatedly.