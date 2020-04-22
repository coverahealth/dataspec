from typing import Iterator

import pytest

from dataspec import INVALID, ErrorDetails, Spec, ValidationError, s
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


class TestSpecConformerComposition:
    def test_spec_compose_conformer_with_no_default_conformer(self):
        spec = s.str(regex=r"\d+")
        assert "1" == spec.conform("1")
        assert INVALID is spec.conform("abc")
        spec_w_conformer = spec.compose_conformer(int)
        assert 1 == spec_w_conformer.conform("1")
        assert INVALID is spec_w_conformer.conform("abc")

    def test_spec_compose_conformer_with_default_conformer(self):
        spec = s.str(regex=r"\d+", conformer=int)
        assert 1 == spec.conform("1")
        assert INVALID is spec.conform("abc")
        spec_w_conformer = spec.compose_conformer(lambda x: x * 2)
        assert 2 == spec_w_conformer.conform("1")
        assert INVALID is spec_w_conformer.conform("abc")

    @pytest.fixture
    def coll_spec_with_conformer_kwarg(self) -> Spec:
        # Test composition with the `s` constructor `conformer` keyword
        x = s([s.str(regex=r"\d+", conformer=int)], conformer=sum)
        v = x.conform(["1", "2", "3"])
        return v

    def test_coll_spec_with_outer_conformer_from_kwarg(
        self, coll_spec_with_conformer_kwarg: Spec
    ):
        assert 6 == coll_spec_with_conformer_kwarg.conform(["1", "2", "3"])
        assert INVALID is coll_spec_with_conformer_kwarg.conform(["1", 2, "3"])


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
