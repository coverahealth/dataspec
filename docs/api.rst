.. py:currentmodule:: dataspec

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

.. autoclass:: Spec
   :members:

.. data:: SpecPredicate

   SpecPredicates are values that can be coerced into Specs by :py:func:`dataspec.s`.

.. data:: Tag

   Tags are string names given to :py:class:`dataspec.Spec` instances which are emitted
   in :py:class:`dataspec.ErrorDetails` instances to indicate which Spec or Specs were
   evaluated to produce the error.

.. data:: Conformer

   Conformers are functions of one argument which return either a conformed value or
   an instance of :py:class:`dataspec.Invalid` (such as :py:obj:`dataspec.INVALID`).

.. data:: PredicateFn

   Predicate functions are functions of one argument which return :py:class:`bool`
   indicating whether or not the argument is valid or not.

.. data:: ValidatorFn

   Validator functions are functions of one argument which yield successive
   :py:class:`dataspec.ErrorDetails` instances indicating exactly why input values
   do not meet the Spec.

.. _spec_errors:

Spec Errors
-----------

.. autoclass:: ErrorDetails
   :members:

.. autoclass:: Invalid

.. autoclass:: ValidationError
   :members:

.. data:: dataspec.INVALID

   ``INVALID`` is a singleton instance of :py:class:`dataspec.Invalid` emitted by
   builtin conformers which can be used for a quick ``is`` identity check.

.. _utilities:

Utilities
---------

.. automodule:: dataspec
   :members: pred_to_validator, register_str_format, tag_maybe