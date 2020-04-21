from typing import Iterator

import pytest

from dataspec import ErrorDetails, ValidationError, s
from dataspec.base import PredicateSpec, ValidatorSpec, pred_to_validator


class TestSpecConstructor:
    @pytest.mark.parametrize("v", [5, 3.14, 8j, "a value"])
    def test_invalid_specs(self, v):
        with pytest.raises(TypeError):
            s(v)

    def test_validator_spec(self):
        def is_valid(v) -> Iterator[ErrorDetails]:
            if v:
                yield ErrorDetails("This value is invalid", pred=is_valid, value=v)

        assert isinstance(s(is_valid), ValidatorSpec)

    def test_predicate_spec(self):
        def is_valid_no_sig(_):
            return True

        assert isinstance(s(is_valid_no_sig), PredicateSpec)

        def is_valid(_) -> bool:
            return True

        assert isinstance(s(is_valid), PredicateSpec)

    def test_pred_to_validator(self):
        @pred_to_validator("This value is invalid")
        def is_valid(v) -> bool:
            return bool(v)

        assert isinstance(s(is_valid), ValidatorSpec)

    def test_no_signature_for_builtins(self):
        s.all(s.str(), str.istitle)

    def test_no_conformer_default(self):
        assert s(str).conformer is None

    def test_construct_with_existing_spec_replaces_conformer(self):
        spec = s(str, conformer=str.upper)
        assert spec.conformer is str.upper
        new_spec = s(spec, conformer=str.lower)
        assert new_spec.conformer is str.lower
        assert spec.conformer is str.upper

    def test_predicate_exception(self):
        assert not s(lambda v: int(v) > 0).is_valid("something")


class TestFunctionSpecs:
    def test_arg_specs(self):
        @s.fdef(argpreds=(s.is_num, s.is_num))
        def add(x, y):
            return x + y

        add(1, 2)
        add(3.14, 2.72)

        with pytest.raises(ValidationError):
            add("hi ", "there")

    def test_kwarg_specs(self):
        @s.fdef(kwargpreds={"x": s.is_num, "y": s.is_num})
        def add(*, x, y):
            return x + y

        add(x=1, y=2)
        add(x=3.14, y=2.72)

        with pytest.raises(ValidationError):
            add(x="hi ", y="there")

    def test_return_spec(self):
        @s.fdef(retpred=s.is_num)
        def add(x, y):
            return x + y

        add(1, 2)
        add(3.14, 2.72)

        with pytest.raises(ValidationError):
            add("hi ", "there")
