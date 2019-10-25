from typing import Iterator

import pytest

from dataspec import ErrorDetails, ValidationError, s
from dataspec.base import PredicateSpec, ValidatorSpec


class TestSpecConstructor:
    @pytest.mark.parametrize("v", [None, 5, 3.14, 8j])
    def test_invalid_specs(self, v):
        with pytest.raises(TypeError):
            s(v)

    def test_spec_with_no_pred(self):
        with pytest.raises(IndexError):
            s("string")

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

    def test_no_signature_for_builtins(self):
        s.all(s.str(), str.istitle)


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
