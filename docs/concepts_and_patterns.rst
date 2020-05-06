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
by :py:func:`s() <dataspec.s>`. Specs can be composed using boolean logic with
:py:func:`s.all() <dataspec.SpecAPI.all>` and :py:func:`s.any() <dataspec.SpecAPI.any>`.
Many of the builtin factories accept existing specs or values which can be coerced to
specs. With Dataspec, you can easily start speccing out your code and gradually add
new specs and build off of existing specs as your app evolves.

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

Predicate functions should satisfy the :py:data:`dataspec.PredicateFn` type and will be
wrapped in the ``PredicateSpec`` spec type.

.. _validators:

Validators
^^^^^^^^^^

Validators are like predicates in that they answer the same fundamental questions about
data that predicates do. However, Validators are a Spec concept that allow us to
retrieve richer error data from Spec failures than we can natively with a simple
predicate. Validators are functions of one argument which return 0 or more
:py:class:`ErrorDetails` instances (typically ``yield`` -ed as a generator) describing
the error.

Validator functions should satisfy the :py:data:`dataspec.ValidatorFn` type and will be
wrapped in the ``ValidatorSpec`` spec type.

.. _conformers:

Conformers
^^^^^^^^^^

Conformers are functions of one argument, ``x``, that return either a conformed value,
which may be ``x`` itself, a new value based on ``x``, or an object of type
:py:class:`Invalid <dataspec.Invalid>` if the value cannot be conformed. Builtin specs
typically return the constant :py:obj:`INVALID <dataspec.INVALID>`, which allows for
a quick identity check (via the ``is`` operator) in many cases.

All specs may include conformers. Scalar spec types such as ``PredicateSpec`` and
``ValidatorSpec`` simply return their argument if it satisfies the spec. Specs for
more complex data structures supply a default conformer which produce new data
structures after applying any child conformation functions to the data structure
elements.

.. _tags:

Tags
^^^^

Tags are simple string names for specs. Tags most often appear in
:py:class:`ErrorDetails <dataspec.ErrorDetails>` objects when an input value cannot
be validated indicating the spec or specs which failed. This is useful for both
debugging and producing useful user-facing validation messages. All Specs can be
created with custom tags, which are specified as a string in the first positional
argument of any spec creation function. Callers are not required to provide tags, but
tags are *required* on Spec instances so ``dataspec`` provides a default value for
all builtin spec types.

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

.. note::

   If nothing changes between definitions, then consider defining your Spec at the
   module level instead. Spec instances are immutable and stateless, so they only need
   to be defined once.

.. _reuse:

Reuse
^^^^^

Specs are designed to be immutable and stateless, so they may be reused across many
different contexts. Often, the only thing that changes between uses is the tag or
conformer. Specs provide a convenient API for generating copies of themselves with new
tags and conformers. You can even generate new specs with a composition of the existing
spec's conformer. The API for creating new copies of specs always returns new copies,
leaving the existing spec unmodified, so you can safely create copies of specs with
slight tweaks without fear of unexpected modification.

In an application setting, it may make sense to collocate your common specs in a single
sub-module or sub-package so they can be easily referred to from other parts of the
application. We typically do not recommend ``CONSTANT_CASE`` for module-level specs,
since there tend to be quite a few of them and the all-caps names are more challenging
to skim.