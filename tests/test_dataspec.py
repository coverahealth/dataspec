import random
import re
import sys
import uuid
from datetime import date, datetime, time, timezone
from enum import Enum
from typing import Iterator, Optional, Type

import attr
import pytest

from dataspec import INVALID, ErrorDetails, Spec, ValidationError, s
from dataspec.impl import PredicateSpec, ValidatorSpec


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


class TestCollSpecValidation:
    @pytest.mark.parametrize(
        "v,path",
        [([[1]], [0]), ([[1, 2, "3"]], [0, 2]), ([[1, 2, 3], [4, "5", 6]], [1, 1])],
    )
    def test_error_details(self, v, path):
        try:
            s([[s.num(min_=0), {"minlength": 3}]]).validate_ex(v)
        except ValidationError as e:
            err = e.errors[0]
            assert path == err.path

    class TestMinlengthValidation:
        @pytest.fixture
        def minlength_spec(self) -> Spec:
            return s([s.str(format_="uuid"), {"minlength": 3}])

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_minlength(self, v):
            with pytest.raises(ValueError):
                s([s.str(format_="uuid"), {"minlength": v}])

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_minlength(self, v):
            with pytest.raises(TypeError):
                s([s.str(format_="uuid"), {"minlength": v}])

        @pytest.mark.parametrize(
            "coll",
            [
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ],
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ],
            ],
        )
        def test_minlength_spec(self, minlength_spec: Spec, coll):
            assert minlength_spec.is_valid(coll)

        @pytest.mark.parametrize(
            "coll",
            [
                [],
                ["a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9"],
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ],
                ["a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9", "", "not a uuid"],
            ],
        )
        def test_minlength_spec_failure(self, minlength_spec: Spec, coll):
            assert not minlength_spec.is_valid(coll)

    class TestMaxlengthValidation:
        @pytest.fixture
        def maxlength_spec(self) -> Spec:
            return s([s.str(format_="uuid"), {"maxlength": 2}])

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_maxlength(self, v):
            with pytest.raises(ValueError):
                s([s.str(format_="uuid"), {"maxlength": v}])

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_maxlength(self, v):
            with pytest.raises(TypeError):
                s([s.str(format_="uuid"), {"maxlength": v}])

        @pytest.mark.parametrize(
            "coll",
            [
                [],
                ["a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9"],
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ],
            ],
        )
        def test_maxlength_spec(self, maxlength_spec: Spec, coll):
            assert maxlength_spec.is_valid(coll)

        @pytest.mark.parametrize(
            "coll",
            [
                ["", "definitely not a uuid"],
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ],
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ],
            ],
        )
        def test_maxlength_spec_failure(self, maxlength_spec: Spec, coll):
            assert not maxlength_spec.is_valid(coll)

    class TestCountValidation:
        @pytest.fixture
        def count_spec(self) -> Spec:
            return s([s.str(format_="uuid"), {"count": 2}])

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_count(self, v):
            with pytest.raises(ValueError):
                s([s.str(format_="uuid"), {"count": v}])

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_count(self, v):
            with pytest.raises(TypeError):
                s([s.str(format_="uuid"), {"count": v}])

        @pytest.mark.parametrize(
            "coll",
            [
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ]
            ],
        )
        def test_maxlength_spec(self, count_spec: Spec, coll):
            assert count_spec.is_valid(coll)

        @pytest.mark.parametrize(
            "coll",
            [
                [],
                ["a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9"],
                ["", "definitely not a uuid"],
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ],
                [
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                    "a333a14a-a3bd-4100-93bc-4b4ce9a1f8d9",
                ],
            ],
        )
        def test_count_spec_failure(self, count_spec: Spec, coll):
            assert not count_spec.is_valid(coll)

        @pytest.mark.parametrize(
            "opts",
            [
                {"count": 2, "minlength": 3},
                {"count": 2, "maxlength": 3},
                {"count": 2, "minlength": 1, "maxlength": 3},
            ],
        )
        def test_count_and_minlength_or_maxlength_agreement(self, opts):
            with pytest.raises(ValueError):
                s([s.str(format_="uuid"), opts])

    def test_minlength_and_maxlength_agreement(self):
        s([s.str(format_="uuid"), {"minlength": 3, "maxlength": 3}])
        s([s.str(format_="uuid"), {"minlength": 3, "maxlength": 5}])

        with pytest.raises(ValueError):
            s([s.str(format_="uuid"), {"minlength": 5, "maxlength": 3}])

    class TestKindValidation:
        @pytest.fixture(params=[frozenset, list, set, tuple])
        def kind(self, request) -> Type:
            return request.param

        @pytest.fixture
        def other_kind(self, kind: Type) -> Type:
            return random.choice(
                list(filter(lambda t: t is not kind, [frozenset, list, set, tuple]))
            )

        @pytest.fixture
        def kind_spec(self, kind: Type) -> Spec:
            return s([s.is_str, {"kind": kind}])

        def test_kind_validation(self, kind: Type, kind_spec: Spec):
            assert kind_spec.is_valid(kind(["a", "b", "c"]))

        def test_kind_validation_failure(self, other_kind: Type, kind_spec: Spec):
            assert not kind_spec.is_valid(other_kind(["a", "b", "c"]))


class TestCollSpecConformation:
    @pytest.fixture
    def coll_spec(self) -> Spec:
        return s([s.str(length=2, conformer=str.upper)])

    def test_coll_conformation(self, coll_spec: Spec):
        conformed = coll_spec.conform(["CA", "ga", "IL", "ny"])
        assert type(conformed) is list
        assert ["CA", "GA", "IL", "NY"] == conformed

    @pytest.fixture
    def set_spec(self) -> Spec:
        return s([s.str(length=2, conformer=str.upper), {"into": set}])

    def test_set_coll_conformation(self, set_spec: Spec):
        conformed = set_spec.conform(["CA", "ga", "IL", "ny", "ca"])
        assert type(conformed) is set
        assert {"CA", "GA", "IL", "NY"} == conformed


class TestDictSpecValidation:
    @pytest.fixture
    def dict_spec(self) -> Spec:
        return s(
            {
                "id": s.str("id", format_="uuid"),
                "first_name": s.str("first_name"),
                "last_name": s.str("last_name"),
                "date_of_birth": s.str("date_of_birth", format_="iso-date"),
                "gender": s("gender", {"M", "F"}),
                s.opt("state"): s("state", {"CA", "GA", "NY"}),
            }
        )

    @pytest.mark.parametrize(
        "d",
        [
            {
                "id": "e1bc9fb2-a4d3-4683-bfef-3acc61b0edcc",
                "first_name": "Carl",
                "last_name": "Sagan",
                "date_of_birth": "1996-12-20",
                "gender": "M",
                "state": "CA",
            },
            {
                "id": "958e2f55-5fdf-4b84-a522-a0765299ba4b",
                "first_name": "Marie",
                "last_name": "Curie",
                "date_of_birth": "1867-11-07",
                "gender": "F",
                "occupation": "Chemist",
            },
            {
                "id": "54a9489e-b5b6-4320-aedf-9bc6ef5f4910",
                "first_name": "Greta",
                "last_name": "Thunberg",
                "date_of_birth": "2003-01-03",
                "gender": "F",
                "country": "Sweden",
            },
        ],
    )
    def test_dict_spec(self, dict_spec: Spec, d):
        assert dict_spec.is_valid(d)

    @pytest.mark.parametrize(
        "d",
        [
            None,
            "a string",
            0,
            3.14,
            True,
            False,
            {"a", "b", "c"},
            ["a", "b", "c"],
            ("a", "b", "c"),
            {
                "id": "0237424237",
                "first_name": "Carl",
                "last_name": "Sagan",
                "date_of_birth": "1996-12-20",
                "gender": "M",
                "state": "CA",
            },
            {
                "id": "958e2f55-5fdf-4b84-a522-a0765299ba4b",
                "first_name": "Marie",
                "last_name": "Curie",
                "date_of_birth": "1867-11-07",
                "occupation": "Chemist",
            },
            {
                "id": "3b41d474-f105-469d-8f4d-8e84091af48f",
                "first_name": "Bill",
                "last_name": "Murray",
                "date_of_birth": "1950-09-21",
                "gender": "M",
                "state": "IL",
            },
            {
                "id": "54a9489e-b5b6-4320-aedf-9bc6ef5f4910",
                "first_name": "Greta",
                "last_name": "Thunberg",
                "date_of_birth": "2003-1-3",
                "gender": "F",
                "country": "Sweden",
            },
        ],
    )
    def test_dict_spec_failure(self, dict_spec: Spec, d):
        assert not dict_spec.is_valid(d)

    @pytest.mark.parametrize(
        "v,path",
        [
            ([{"name": "Mark Jones", "license_states": "GA"}], [0, "license_states"]),
            (
                [
                    {"name": "Darryl Smith", "license_states": ["NY"]},
                    {"name": "Mark Jones", "license_states": ["GA", "California"]},
                ],
                [1, "license_states", 1],
            ),
            ([{"name": "Gary Busey"}], [0, "license_states"]),
        ],
    )
    def test_error_details(self, v, path):
        try:
            s(
                [{"name": s.is_str, "license_states": [s.str("state", length=2)]}]
            ).validate_ex(v)
        except ValidationError as e:
            err = e.errors[0]
            assert path == err.path


class TestDictSpecConformation:
    @pytest.fixture
    def fromisoformat(self):
        if sys.version_info >= (3, 7):
            return date.fromisoformat
        else:
            _ISO_DATE_REGEX = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

            def _fromisoformat(s: str) -> date:
                match = re.fullmatch(_ISO_DATE_REGEX, s)
                assert match is not None
                year, month, day = tuple(int(match.group(x)) for x in (1, 2, 3))
                return date(year, month, day)

            return _fromisoformat

    @pytest.fixture
    def dict_spec(self, fromisoformat) -> Spec:
        return s(
            {
                "first_name": s.str("first_name", conformer=str.title),
                "last_name": s.str("last_name", conformer=str.title),
                s.opt("date_of_birth"): s.str(
                    "date_of_birth", format_="iso-date", conformer=fromisoformat
                ),
            }
        )

    def test_dict_conformation(self, dict_spec: Spec):
        conformed = dict_spec.conform(
            {"first_name": "chris", "last_name": "rink", "date_of_birth": "1990-01-14"}
        )
        assert isinstance(conformed, dict)
        assert "Chris" == conformed["first_name"]
        assert "Rink" == conformed["last_name"]
        assert date(year=1990, month=1, day=14) == conformed["date_of_birth"]

        conformed = dict_spec.conform({"first_name": "peter", "last_name": "criss"})
        assert isinstance(conformed, dict)
        assert "Peter" == conformed["first_name"]
        assert "Criss" == conformed["last_name"]
        assert None is conformed.get("date_of_birth")


class TestObjectSpecValidation:
    @attr.s(auto_attribs=True, frozen=True, slots=True)
    class Person:
        id: str
        first_name: str
        last_name: str
        date_of_birth: str
        gender: str
        state: Optional[str] = None
        occupation: Optional[str] = None
        country: Optional[str] = None

    @pytest.fixture
    def obj_spec(self) -> Spec:
        return s.obj(
            {
                "id": s.str("id", format_="uuid"),
                "first_name": s.str("first_name"),
                "last_name": s.str("last_name"),
                "date_of_birth": s.str("date_of_birth", format_="iso-date"),
                "gender": s("gender", {"M", "F"}),
                s.opt("state"): s.nilable(s("state", {"CA", "GA", "NY"})),
            }
        )

    @pytest.mark.parametrize(
        "o",
        [
            Person(
                id="e1bc9fb2-a4d3-4683-bfef-3acc61b0edcc",
                first_name="Carl",
                last_name="Sagan",
                date_of_birth="1996-12-20",
                gender="M",
                state="CA",
            ),
            Person(
                id="958e2f55-5fdf-4b84-a522-a0765299ba4b",
                first_name="Marie",
                last_name="Curie",
                date_of_birth="1867-11-07",
                gender="F",
                occupation="Chemist",
            ),
            Person(
                id="54a9489e-b5b6-4320-aedf-9bc6ef5f4910",
                first_name="Greta",
                last_name="Thunberg",
                date_of_birth="2003-01-03",
                gender="F",
            ),
        ],
    )
    def test_obj_spec(self, obj_spec: Spec, o):
        assert obj_spec.is_valid(o)

    @pytest.mark.parametrize(
        "o",
        [
            Person(
                id="0237424237",
                first_name="Carl",
                last_name="Sagan",
                date_of_birth="1996-12-20",
                gender="M",
            ),
            Person(
                id="958e2f55-5fdf-4b84-a522-a0765299ba4b",
                first_name="Marie",
                last_name="Curie",
                date_of_birth="1996-12-20",
                gender="",
                occupation="Chemist",
            ),
            Person(
                id="3b41d474-f105-469d-8f4d-8e84091af48f",
                first_name="Bill",
                last_name="Murray",
                date_of_birth="1950-09-21",
                gender="M",
                state="IL",
            ),
            Person(
                id="54a9489e-b5b6-4320-aedf-9bc6ef5f4910",
                first_name="Greta",
                last_name="Thunberg",
                date_of_birth="2003-1-3",
                gender="F",
            ),
        ],
    )
    def test_obj_spec_failure(self, obj_spec: Spec, o):
        assert not obj_spec.is_valid(o)


class TestSetSpec:
    @pytest.fixture
    def set_spec(self) -> Spec:
        return s({"a", "b", "c"})

    def test_set_spec(self, set_spec: Spec):
        assert set_spec.is_valid("a")
        assert set_spec.is_valid("b")
        assert set_spec.is_valid("c")
        assert not set_spec.is_valid("d")
        assert not set_spec.is_valid(1)

    def test_set_spec_conformation(self, set_spec: Spec):
        assert "a" is set_spec.conform("a")
        assert "b" is set_spec.conform("b")
        assert "c" is set_spec.conform("c")
        assert INVALID is set_spec.conform("d")
        assert INVALID is set_spec.conform(1)


class TestEnumSetSpec:
    class YesNo(Enum):
        YES = "Yes"
        NO = "No"

    @pytest.fixture
    def enum_spec(self) -> Spec:
        return s(self.YesNo)

    def test_enum_spec(self, enum_spec: Spec):
        assert enum_spec.is_valid("Yes")
        assert enum_spec.is_valid("No")
        assert enum_spec.is_valid(self.YesNo.YES)
        assert enum_spec.is_valid(self.YesNo.NO)
        assert not enum_spec.is_valid("Maybe")
        assert not enum_spec.is_valid(None)

    def test_enum_spec_conformation(self, enum_spec: Spec):
        assert self.YesNo.YES == enum_spec.conform("Yes")
        assert self.YesNo.NO == enum_spec.conform("No")
        assert self.YesNo.YES == enum_spec.conform(self.YesNo.YES)
        assert self.YesNo.NO == enum_spec.conform(self.YesNo.NO)
        assert INVALID is enum_spec.conform("Maybe")
        assert INVALID is enum_spec.conform(None)


class TestTupleSpecValidation:
    @pytest.fixture
    def tuple_spec(self) -> Spec:
        return s(
            (
                s.str("id", format_="uuid"),
                s.str("first_name"),
                s.str("last_name"),
                s.str("date_of_birth", format_="iso-date"),
                s("gender", {"M", "F"}),
            )
        )

    @pytest.mark.parametrize(
        "row",
        [
            (
                "e1bc9fb2-a4d3-4683-bfef-3acc61b0edcc",
                "Carl",
                "Sagan",
                "1996-12-20",
                "M",
            ),
            (
                "958e2f55-5fdf-4b84-a522-a0765299ba4b",
                "Marie",
                "Curie",
                "1867-11-07",
                "F",
            ),
            (
                "54a9489e-b5b6-4320-aedf-9bc6ef5f4910",
                "Greta",
                "Thunberg",
                "2003-01-03",
                "F",
            ),
        ],
    )
    def test_tuple_spec(self, tuple_spec, row):
        assert tuple_spec.is_valid(row)

    @pytest.mark.parametrize(
        "row",
        [
            None,
            "a string",
            0,
            3.14,
            True,
            False,
            {"a", "b", "c"},
            ["a", "b", "c"],
            ("a", "b", "c"),
            ("372970274234", "Carl", "Sagan", "1996-12-20", "M"),
            (
                "958e2f55-5fdf-4b84-a522-a0765299ba4b",
                "Marie",
                "Curie",
                "1867-11-07",
                "N",
            ),
            ("54a9489e-b5b6-4320-aedf-9bc6ef5f4910", "Greta", "Thunberg", "2003-01-03"),
        ],
    )
    def test_tuple_spec_failure(self, tuple_spec, row):
        assert not tuple_spec.is_valid(row)

    @pytest.mark.parametrize(
        "v,path",
        [
            ([("Ronald Weasley", "GA"), ("Frodo Baggins", "HB")], [1, 1]),
            ([("Ronald Weasley",), ("Ira Glass", "NY")], [0]),
        ],
    )
    def test_error_details(self, v, path):
        try:
            s([(s.str("name"), {"IL", "GA", "NY"}), {"maxlength": 2}]).validate_ex(v)
        except ValidationError as e:
            err = e.errors[0]
            assert path == err.path


class TestTupleSpecConformation:
    @pytest.fixture
    def tuple_spec(self) -> Spec:
        return s(
            "user-profile",
            (
                s.str(conformer=str.title),
                s.str(conformer=str.title),
                s.num("age", min_=18),
            ),
        )

    def test_tuple_conformation(self, tuple_spec: Spec):
        conformed = tuple_spec.conform(("chris", "rink", 29))
        assert type(conformed) is tuple
        assert "Chris" == conformed[0]
        assert "Rink" == conformed[1]
        assert 29 == conformed[2]

    @pytest.fixture
    def namedtuple_spec(self) -> Spec:
        return s(
            "user-profile",
            (
                s.str("first-name", conformer=str.title),
                s.str("last-name", conformer=str.title),
                s.num("age", min_=18),
            ),
        )

    def test_namedtuple_conformation(self, namedtuple_spec: Spec):
        conformed = namedtuple_spec.conform(("chris", "rink", 29))
        assert type(conformed).__name__ == "user_profile"
        assert "Chris" == conformed.first_name == conformed[0]
        assert "Rink" == conformed.last_name == conformed[1]
        assert 29 == conformed.age == conformed[2]


class TestAllSpecValidation:
    @pytest.fixture
    def all_spec(self) -> Spec:
        return s.all(
            s.str(format_="uuid", conformer=uuid.UUID), lambda id_: id_.version == 4
        )

    @pytest.mark.parametrize(
        "v",
        [
            "c5a28680-986f-4f0d-8187-80d1fbe22059",
            "3BE59FF6-9C75-4027-B132-C9792D84547D",
        ],
    )
    def test_all_validation(self, all_spec, v):
        assert all_spec.is_valid(v)
        assert uuid.UUID(v) == all_spec.conform(v)

    @pytest.mark.parametrize(
        "v",
        [
            "6281d852-ef4d-11e9-9002-4c327592fea9",
            "0e8d7ceb-56e8-36d2-9b54-ea48d4bdea3f",
            "10988ff4-136c-5ca7-ab35-a686a56c22c4",
            "",
            "5",
            "abcde",
            "ABCDe",
            5,
            3.14,
            None,
            {},
            set(),
            [],
        ],
    )
    def test_all_failure(self, all_spec, v):
        assert not all_spec.is_valid(v)
        assert INVALID is all_spec.conform(v)


class TestAllSpecConformation:
    class YesNo(Enum):
        YES = "Yes"
        NO = "No"

    @pytest.fixture
    def all_spec(self) -> Spec:
        return s.all(s.str(conformer=str.title), self.YesNo)

    @pytest.mark.parametrize(
        "v,expected",
        [
            ("yes", YesNo.YES),
            ("Yes", YesNo.YES),
            ("yES", YesNo.YES),
            ("YES", YesNo.YES),
            ("no", YesNo.NO),
            ("No", YesNo.NO),
            ("nO", YesNo.NO),
            ("NO", YesNo.NO),
        ],
    )
    def test_all_spec_conformation(self, all_spec: Spec, v, expected):
        assert expected == all_spec.conform(v)


def test_any():
    spec = s.any(s.is_num, s.is_str)
    assert spec.is_valid("5")
    assert spec.is_valid(5)
    assert spec.is_valid(3.14)
    assert not spec.is_valid(None)
    assert not spec.is_valid({})
    assert not spec.is_valid(set())
    assert not spec.is_valid([])


@pytest.mark.parametrize(
    "v", [None, 25, 3.14, 3j, [], set(), frozenset(), (), "abcdef"]
)
def test_is_any(v):
    assert s.is_any.is_valid(v)


class TestBoolValidation:
    @pytest.mark.parametrize("v", [True, False])
    def test_bool(self, v):
        assert s.is_bool.is_valid(v)

    @pytest.mark.parametrize("v", [1, 0, "", "a string"])
    def test_bool_failure(self, v):
        assert not s.is_bool.is_valid(v)

    def test_is_false(self):
        assert s.is_false.is_valid(False)

    @pytest.mark.parametrize("v", [True, 1, 0, "", "a string"])
    def test_is_true_failure(self, v):
        assert not s.is_false.is_valid(v)

    def test_is_true(self):
        assert s.is_true.is_valid(True)

    @pytest.mark.parametrize("v", [False, 1, 0, "", "a string"])
    def test_is_true_failure(self, v):
        assert not s.is_true.is_valid(v)


class TestBytesSpecValidation:
    @pytest.mark.parametrize(
        "v",
        [
            b"",
            b"a string",
            b"\xf0\x9f\x98\x8f",
            bytearray(),
            bytearray(b"\xf0\x9f\x98\x8f"),
        ],
    )
    def test_is_bytes(self, v):
        assert s.is_bytes.is_valid(v)

    @pytest.mark.parametrize("v", [25, None, 3.14, [], set(), "", "a string", "😏"])
    def test_not_is_bytes(self, v):
        assert not s.is_bytes.is_valid(v)

    class TestMinlengthSpec:
        @pytest.fixture
        def minlength_spec(self) -> Spec:
            return s.bytes(minlength=5)

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_minlength(self, v):
            with pytest.raises(ValueError):
                s.bytes(minlength=v)

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_minlength(self, v):
            with pytest.raises(TypeError):
                s.bytes(minlength=v)

        @pytest.mark.parametrize("v", [b"abcde", b"abcdef"])
        def test_is_minlength(self, minlength_spec: Spec, v):
            assert minlength_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v", [None, 25, 3.14, [], set(), b"", b"a", b"ab", b"abc", b"abcd"]
        )
        def test_is_not_minlength(self, minlength_spec: Spec, v):
            assert not minlength_spec.is_valid(v)

    class TestMaxlengthSpec:
        @pytest.fixture
        def maxlength_spec(self) -> Spec:
            return s.bytes(maxlength=5)

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_maxlength(self, v):
            with pytest.raises(ValueError):
                s.bytes(maxlength=v)

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_maxlength(self, v):
            with pytest.raises(TypeError):
                s.bytes(maxlength=v)

        @pytest.mark.parametrize("v", [b"", b"a", b"ab", b"abc", b"abcd", b"abcde"])
        def test_is_maxlength(self, maxlength_spec: Spec, v):
            assert maxlength_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v", [None, 25, 3.14, [], set(), b"abcdef", b"abcdefg"]
        )
        def test_is_not_maxlength(self, maxlength_spec: Spec, v):
            assert not maxlength_spec.is_valid(v)

    def test_minlength_and_maxlength_agreement(self):
        s.bytes(minlength=10, maxlength=10)
        s.bytes(minlength=8, maxlength=10)

        with pytest.raises(ValueError):
            s.bytes(minlength=10, maxlength=8)


class TestInstSpecValidation:
    @pytest.mark.parametrize("v", [datetime(year=2000, month=1, day=1)])
    def test_is_inst(self, v):
        assert s.is_inst.is_valid(v)

    @pytest.mark.parametrize(
        "v",
        [
            None,
            25,
            3.14,
            3j,
            [],
            set(),
            frozenset(),
            (),
            "abcdef",
            time(),
            date(year=2000, month=1, day=1),
        ],
    )
    def test_is_inst_failure(self, v):
        assert not s.is_inst.is_valid(v)

    class TestBeforeSpec:
        @pytest.fixture
        def before_spec(self) -> Spec:
            return s.inst(before=datetime(year=2000, month=1, day=1))

        @pytest.mark.parametrize(
            "v",
            [
                datetime(year=1980, month=1, day=15),
                datetime(year=1999, month=12, day=31),
                datetime(
                    year=1999,
                    month=12,
                    day=31,
                    hour=23,
                    minute=59,
                    second=59,
                    microsecond=999999,
                ),
                datetime(year=2000, month=1, day=1),
            ],
        )
        def test_before_spec(self, before_spec: Spec, v):
            assert before_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v",
            [
                datetime(year=2000, month=1, day=2),
                datetime(year=2020, month=1, day=15),
                datetime(
                    year=2000, month=1, day=1, hour=0, minute=0, second=0, microsecond=1
                ),
            ],
        )
        def test_before_spec_failure(self, before_spec: Spec, v):
            assert not before_spec.is_valid(v)

    class TestAfterSpec:
        @pytest.fixture
        def after_spec(self) -> Spec:
            return s.inst(after=datetime(year=2000, month=1, day=1))

        @pytest.mark.parametrize(
            "v",
            [
                datetime(year=2000, month=1, day=1),
                datetime(year=2020, month=1, day=2),
                datetime(year=2000, month=1, day=15),
                datetime(
                    year=2000, month=1, day=1, hour=0, minute=0, second=0, microsecond=1
                ),
            ],
        )
        def test_after_spec(self, after_spec: Spec, v):
            assert after_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v",
            [
                datetime(year=1980, month=1, day=15),
                datetime(year=1999, month=12, day=31),
                datetime(
                    year=1999,
                    month=12,
                    day=31,
                    hour=23,
                    minute=59,
                    second=59,
                    microsecond=999999,
                ),
            ],
        )
        def test_after_spec_failure(self, after_spec: Spec, v):
            assert not after_spec.is_valid(v)

    class TestIsAwareSpec:
        @pytest.fixture
        def aware_spec(self) -> Spec:
            return s.inst(is_aware=True)

        def test_aware_spec(self, aware_spec):
            assert aware_spec.is_valid(datetime.now(timezone.utc))

        def test_aware_spec_failure(self, aware_spec):
            assert not aware_spec.is_valid(datetime.utcnow())


class TestDateSpecValidation:
    @pytest.mark.parametrize(
        "v", [date(year=2000, month=1, day=1), datetime(year=2000, month=1, day=1)]
    )
    def test_is_date(self, v):
        assert s.is_date.is_valid(v)

    @pytest.mark.parametrize(
        "v", [None, 25, 3.14, 3j, [], set(), frozenset(), (), "abcdef", time()]
    )
    def test_is_date_failure(self, v):
        assert not s.is_date.is_valid(v)

    class TestBeforeSpec:
        @pytest.fixture
        def before_spec(self) -> Spec:
            return s.date(before=date(year=2000, month=1, day=1))

        @pytest.mark.parametrize(
            "v",
            [
                date(year=1980, month=1, day=15),
                date(year=1999, month=12, day=31),
                date(year=1999, month=12, day=31),
                date(year=2000, month=1, day=1),
            ],
        )
        def test_before_spec(self, before_spec: Spec, v):
            assert before_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v", [date(year=2000, month=1, day=2), date(year=2020, month=1, day=15)]
        )
        def test_before_spec_failure(self, before_spec: Spec, v):
            assert not before_spec.is_valid(v)

    class TestAfterSpec:
        @pytest.fixture
        def after_spec(self) -> Spec:
            return s.date(after=date(year=2000, month=1, day=1))

        @pytest.mark.parametrize(
            "v",
            [
                date(year=2020, month=1, day=2),
                date(year=2000, month=1, day=15),
                date(year=2000, month=1, day=1),
            ],
        )
        def test_after_spec(self, after_spec: Spec, v):
            assert after_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v",
            [
                date(year=1980, month=1, day=15),
                date(year=1999, month=12, day=31),
                date(year=1999, month=12, day=31),
            ],
        )
        def test_after_spec_failure(self, after_spec: Spec, v):
            assert not after_spec.is_valid(v)

    class TestIsAwareSpec:
        def test_aware_spec(self) -> Spec:
            s.date(is_aware=False)

            with pytest.raises(TypeError):
                s.date(is_aware=True)


class TestTimeSpecValidation:
    @pytest.mark.parametrize("v", [time()])
    def test_is_time(self, v):
        assert s.is_time.is_valid(v)

    @pytest.mark.parametrize(
        "v",
        [
            None,
            25,
            3.14,
            3j,
            [],
            set(),
            frozenset(),
            (),
            "abcdef",
            date(year=2000, month=1, day=1),
            datetime(year=2000, month=1, day=1),
        ],
    )
    def test_is_time_failure(self, v):
        assert not s.is_time.is_valid(v)

    class TestBeforeSpec:
        @pytest.fixture
        def before_spec(self) -> Spec:
            return s.time(before=time(hour=12, minute=0, second=0))

        @pytest.mark.parametrize(
            "v",
            [
                time(hour=11, minute=59, second=59, microsecond=999999),
                time(hour=11, minute=0, second=0),
                time(hour=0, minute=0, second=0),
            ],
        )
        def test_before_spec(self, before_spec: Spec, v):
            assert before_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v",
            [
                time(hour=12, minute=0, second=0, microsecond=1),
                time(hour=12, minute=59, second=0),
                time(hour=23, minute=0, second=0),
            ],
        )
        def test_before_spec_failure(self, before_spec: Spec, v):
            assert not before_spec.is_valid(v)

    class TestAfterSpec:
        @pytest.fixture
        def after_spec(self) -> Spec:
            return s.time(after=time(hour=12, minute=0, second=0))

        @pytest.mark.parametrize(
            "v",
            [
                time(hour=12, minute=0, second=0, microsecond=1),
                time(hour=12, minute=59, second=0),
                time(hour=23, minute=0, second=0),
            ],
        )
        def test_after_spec(self, after_spec: Spec, v):
            assert after_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v",
            [
                time(hour=11, minute=59, second=59, microsecond=999999),
                time(hour=11, minute=0, second=0),
                time(hour=0, minute=0, second=0),
            ],
        )
        def test_after_spec_failure(self, after_spec: Spec, v):
            assert not after_spec.is_valid(v)

    class TestIsAwareSpec:
        @pytest.fixture
        def aware_spec(self) -> Spec:
            return s.time(is_aware=True)

        def test_aware_spec(self, aware_spec):
            assert aware_spec.is_valid(time(tzinfo=timezone.utc))

        def test_aware_spec_failure(self, aware_spec):
            assert not aware_spec.is_valid(time())


def test_nilable():
    assert s.nilable(s.is_str).is_valid(None)
    assert s.nilable(s.is_str).is_valid("")
    assert s.nilable(s.is_str).is_valid("a string")


class TestNumSpecValidation:
    @pytest.mark.parametrize("v", [-3, 25, 3.14, -2.72, -33])
    def test_is_num(self, v):
        assert s.is_num.is_valid(v)

    @pytest.mark.parametrize("v", [4j, 6j, "", "a string", "😏", None, [], set()])
    def test_not_is_num(self, v):
        assert not s.is_num.is_valid(v)

    class TestMinSpec:
        @pytest.fixture
        def minspec(self) -> Spec:
            return s.num(min_=5)

        @pytest.mark.parametrize("v", [5, 6, 100, 300.14, 5.83838828283])
        def test_is_above_min(self, minspec: Spec, v):
            assert minspec.is_valid(v)

        @pytest.mark.parametrize(
            "v", [None, -50, 4.9, 4, 0, 3.14, [], set(), "", "a", "ab", "abc", "abcd"]
        )
        def test_is_not_above_min(self, minspec: Spec, v):
            assert not minspec.is_valid(v)

    class TestMaxSpec:
        @pytest.fixture
        def maxspec(self) -> Spec:
            return s.num(max_=5)

        @pytest.mark.parametrize("v", [-50, 4.9, 4, 0, 3.14, 5])
        def test_is_below_max(self, maxspec: Spec, v):
            assert maxspec.is_valid(v)

        @pytest.mark.parametrize(
            "v",
            [
                None,
                6,
                100,
                300.14,
                5.83838828283,
                [],
                set(),
                "",
                "a",
                "ab",
                "abc",
                "abcd",
            ],
        )
        def test_is_not_below_max(self, maxspec: Spec, v):
            assert not maxspec.is_valid(v)

    def test_min_and_max_agreement(self):
        s.num(min_=10, max_=10)
        s.num(min_=8, max_=10)

        with pytest.raises(ValueError):
            s.num(min_=10, max_=8)

        with pytest.raises(ValueError):
            s.num(min_=10, max_=8.6)


class TestStringSpecValidation:
    @pytest.mark.parametrize("v", ["", "a string", "😏"])
    def test_is_str(self, v):
        assert s.is_str.is_valid(v)

    @pytest.mark.parametrize("v", [25, None, 3.14, [], set()])
    def test_not_is_str(self, v):
        assert not s.is_str.is_valid(v)

    class TestCountValidation:
        @pytest.fixture
        def count_spec(self) -> Spec:
            return s.str(length=3)

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_count(self, v):
            with pytest.raises(ValueError):
                return s.str(length=v)

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_count(self, v):
            with pytest.raises(TypeError):
                s.str(length=v)

        @pytest.mark.parametrize("v", ["xxx", "xxy", "773", "833"])
        def test_maxlength_spec(self, count_spec: Spec, v):
            assert count_spec.is_valid(v)

        @pytest.mark.parametrize("v", ["", "x", "xx", "xxxx", "xxxxx"])
        def test_count_spec_failure(self, count_spec: Spec, v):
            assert not count_spec.is_valid(v)

        @pytest.mark.parametrize(
            "opts",
            [
                {"length": 2, "minlength": 3},
                {"length": 2, "maxlength": 3},
                {"length": 2, "minlength": 1, "maxlength": 3},
            ],
        )
        def test_count_and_minlength_or_maxlength_agreement(self, opts):
            with pytest.raises(ValueError):
                s.str(**opts)

    class TestMinlengthSpec:
        @pytest.fixture
        def minlength_spec(self) -> Spec:
            return s.str(minlength=5)

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_minlength(self, v):
            with pytest.raises(ValueError):
                s.str(minlength=v)

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_minlength(self, v):
            with pytest.raises(TypeError):
                s.str(minlength=v)

        @pytest.mark.parametrize("v", ["abcde", "abcdef"])
        def test_is_minlength(self, minlength_spec: Spec, v):
            assert minlength_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v", [None, 25, 3.14, [], set(), "", "a", "ab", "abc", "abcd"]
        )
        def test_is_not_minlength(self, minlength_spec: Spec, v):
            assert not minlength_spec.is_valid(v)

    class TestMaxlengthSpec:
        @pytest.fixture
        def maxlength_spec(self) -> Spec:
            return s.str(maxlength=5)

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_maxlength(self, v):
            with pytest.raises(ValueError):
                s.str(maxlength=v)

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_maxlength(self, v):
            with pytest.raises(TypeError):
                s.str(maxlength=v)

        @pytest.mark.parametrize("v", ["", "a", "ab", "abc", "abcd", "abcde"])
        def test_is_maxlength(self, maxlength_spec: Spec, v):
            assert maxlength_spec.is_valid(v)

        @pytest.mark.parametrize("v", [None, 25, 3.14, [], set(), "abcdef", "abcdefg"])
        def test_is_not_maxlength(self, maxlength_spec: Spec, v):
            assert not maxlength_spec.is_valid(v)

    def test_minlength_and_maxlength_agreement(self):
        s.str(minlength=10, maxlength=10)
        s.str(minlength=8, maxlength=10)

        with pytest.raises(ValueError):
            s.str(minlength=10, maxlength=8)

    class TestRegexSpec:
        @pytest.fixture
        def zipcode_spec(self) -> Spec:
            return s.str(regex=r"\d{5}(-\d{4})?")

        @pytest.mark.parametrize(
            "v", ["10017", "10017-3332", "37779", "37779-2770", "00000"]
        )
        def test_is_zipcode(self, zipcode_spec: Spec, v):
            assert zipcode_spec.is_valid(v)

        @pytest.mark.parametrize(
            "v", [None, 25, 3.14, [], set(), "abcdef", "abcdefg", "100017", "10017-383"]
        )
        def test_is_not_zipcode(self, zipcode_spec: Spec, v):
            assert not zipcode_spec.is_valid(v)

    class TestISODateFormat:
        @pytest.fixture
        def conform(self):
            if sys.version_info >= (3, 7):
                return date.fromisoformat
            else:
                from dataspec.impl import _str_to_iso_date

                return _str_to_iso_date

        @pytest.fixture
        def conforming_date_spec(self) -> Spec:
            return s.str(conform_format="iso-date")

        @pytest.fixture
        def date_spec(self) -> Spec:
            return s.str(format_="iso-date")

        @pytest.mark.parametrize("v", ["2019-10-12", "1945-09-02", "1066-10-14"])
        def test_is_date_str(
            self, date_spec: Spec, conforming_date_spec: Spec, conform, v
        ):
            assert date_spec.is_valid(v)
            assert conforming_date_spec.is_valid(v)
            assert conform(v) == conforming_date_spec.conform(v)

        @pytest.mark.parametrize(
            "v",
            [
                None,
                25,
                3.14,
                [],
                set(),
                "abcdef",
                "abcdefg",
                "100017",
                "10017-383",
                "1945-9-2",
                "430-10-02",
            ],
        )
        def test_is_not_date_str(self, date_spec: Spec, conforming_date_spec: Spec, v):
            assert not date_spec.is_valid(v)
            assert not conforming_date_spec.is_valid(v)

    @pytest.mark.skipif(
        sys.version_info <= (3, 7), reason="datetime.fromisoformat added in Python 3.7"
    )
    class TestISODatetimeFormat:
        @pytest.fixture
        def conform(self):
            return datetime.fromisoformat

        @pytest.fixture
        def conforming_datetime_spec(self) -> Spec:
            return s.str(conform_format="iso-datetime")

        @pytest.fixture
        def datetime_spec(self) -> Spec:
            return s.str(format_="iso-datetime")

        @pytest.mark.parametrize(
            "v",
            [
                "2019-10-12T18:03:50.617-00:00",
                "1945-09-02T18:03:50.617-00:00",
                "1066-10-14T18:03:50.617-00:00",
                "2019-10-12",
                "1945-09-02",
                "1066-10-14",
            ],
        )
        def test_is_datetime_str(
            self, datetime_spec: Spec, conforming_datetime_spec: Spec, conform, v
        ):
            assert datetime_spec.is_valid(v)
            assert conforming_datetime_spec.is_valid(v)
            assert conform(v) == conforming_datetime_spec.conform(v)

        @pytest.mark.parametrize(
            "v",
            [
                None,
                25,
                3.14,
                [],
                set(),
                "abcdef",
                "abcdefg",
                "100017",
                "10017-383",
                "1945-9-2",
                "430-10-02",
            ],
        )
        def test_is_not_datetime_str(
            self, datetime_spec: Spec, conforming_datetime_spec: Spec, v
        ):
            assert not datetime_spec.is_valid(v)
            assert not conforming_datetime_spec.is_valid(v)

    class TestUUIDFormat:
        @pytest.fixture
        def conforming_uuid_spec(self) -> Spec:
            return s.str(conform_format="uuid")

        @pytest.fixture
        def uuid_spec(self) -> Spec:
            return s.str(format_="uuid")

        @pytest.mark.parametrize(
            "v",
            [
                "91d7e5f0-7567-4569-a61d-02ed57507f47",
                "91d7e5f075674569a61d02ed57507f47",
                "06130510-83A5-478B-B65C-6A8DC2104E2F",
                "0613051083A5478BB65C6A8DC2104E2F",
            ],
        )
        def test_is_uuid_str(self, uuid_spec: Spec, conforming_uuid_spec: Spec, v):
            assert uuid_spec.is_valid(v)
            assert conforming_uuid_spec.is_valid(v)
            assert uuid.UUID(v) == conforming_uuid_spec.conform(v)

        @pytest.mark.parametrize(
            "v", [None, 25, 3.14, [], set(), "abcdef", "abcdefg", "100017", "10017-383"]
        )
        def test_is_not_uuid_str(self, uuid_spec: Spec, conforming_uuid_spec: Spec, v):
            assert not uuid_spec.is_valid(v)
            assert not conforming_uuid_spec.is_valid(v)

    @pytest.mark.parametrize(
        "opts",
        [
            {"regex": r"\d{5}(-\d{4})?", "format_": "uuid"},
            {"regex": r"\d{5}(-\d{4})?", "conform_format": "uuid"},
            {"conform_format": "uuid", "format_": "uuid"},
        ],
    )
    def test_regex_and_format_agreement(self, opts):
        with pytest.raises(ValueError):
            s.str(**opts)


class TestUUIDSpecValidation:
    @pytest.mark.parametrize(
        "v",
        [
            "6281d852-ef4d-11e9-9002-4c327592fea9",
            "0e8d7ceb-56e8-36d2-9b54-ea48d4bdea3f",
            "c5a28680-986f-4f0d-8187-80d1fbe22059",
            "3BE59FF6-9C75-4027-B132-C9792D84547D",
            "10988ff4-136c-5ca7-ab35-a686a56c22c4",
        ],
    )
    def test_uuid_validation(self, v):
        assert not s.is_uuid.is_valid(v)
        assert s.is_uuid.is_valid(uuid.UUID(v))
        assert uuid.UUID(v) == s.is_uuid.conform(uuid.UUID(v))

    @pytest.mark.parametrize(
        "v", ["", "5", "abcde", "ABCDe", 5, 3.14, None, {}, set(), []]
    )
    def test_uuid_validation_failure(self, v):
        assert not s.is_uuid.is_valid(v)
        assert INVALID is s.is_uuid.conform(v)

    class TestUUIDVersionSpecValidation:
        @pytest.fixture
        def uuid_spec(self) -> Spec:
            return s.uuid(versions={1, 4})

        @pytest.mark.parametrize("versions", [{1, 3, 4, 8}, {1, -1}, {"1", "3", "5"}])
        def test_invalid_uuid_version_spec(self, versions) -> Spec:
            with pytest.raises(ValueError):
                s.uuid(versions=versions)

        @pytest.mark.parametrize(
            "v",
            [
                "6281d852-ef4d-11e9-9002-4c327592fea9",
                "c5a28680-986f-4f0d-8187-80d1fbe22059",
                "3BE59FF6-9C75-4027-B132-C9792D84547D",
            ],
        )
        def test_uuid_validation(self, uuid_spec: Spec, v):
            assert not uuid_spec.is_valid(v)
            assert uuid_spec.is_valid(uuid.UUID(v))
            assert uuid.UUID(v) == uuid_spec.conform(uuid.UUID(v))

        @pytest.mark.parametrize(
            "v",
            [
                "0e8d7ceb-56e8-36d2-9b54-ea48d4bdea3f",
                "10988ff4-136c-5ca7-ab35-a686a56c22c4",
                "",
                "5",
                "abcde",
                "ABCDe",
                5,
                3.14,
                None,
                {},
                set(),
                [],
            ],
        )
        def test_uuid_validation_failure(self, uuid_spec: Spec, v):
            assert not uuid_spec.is_valid(v)
            assert INVALID is uuid_spec.conform(v)


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
