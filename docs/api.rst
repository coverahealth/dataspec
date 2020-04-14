.. _api:

Dataspec API
============

.. contents::
   :depth: 2

.. _creating_specs:

Creating Specs
--------------

.. autofunction:: dataspec.s

``dataspec.s`` is a singleton of :py:class:`dataspec.SpecAPI` which can be imported and
used directly as a generic :py:class:`dataspec.Spec` constructor.

For more information, see :py:meth:`dataspec.SpecAPI.__call__`.

.. autoclass:: dataspec.SpecAPI
   :members:
   :special-members: __call__

.. _types:

Types
-----

.. automodule:: dataspec
   :members: Spec, SpecPredicate, Tag, Conformer, PredicateFn, ValidatorFn
   :noindex:

.. _spec_errors:

Spec Errors
-----------

.. automodule:: dataspec
   :members: ErrorDetails, Invalid, ValidationError
   :noindex:

.. autodata:: dataspec.INVALID

.. _utilities:

Utilities
---------

.. automodule:: dataspec
   :members: pred_to_validator, register_str_format, register_str_format_spec, tag_maybe