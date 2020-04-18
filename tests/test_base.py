import random
import re
import sys
from datetime import date
from enum import Enum
from typing import Optional, Type

import attr
import pytest

from dataspec import INVALID, Spec, ValidationError, s


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
        assert self.YesNo.YES == enum_spec.conform("YES")
        assert self.YesNo.NO == enum_spec.conform("NO")
        assert self.YesNo.YES == enum_spec.conform("Yes")
        assert self.YesNo.NO == enum_spec.conform("No")
        assert self.YesNo.YES == enum_spec.conform(self.YesNo.YES)
        assert self.YesNo.NO == enum_spec.conform(self.YesNo.NO)
        assert INVALID is enum_spec.conform("Maybe")
        assert INVALID is enum_spec.conform(None)

        # Testing the last branch of the conformer
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


class TestTypeSpec:
    @pytest.mark.parametrize(
        "tp,vals",
        [
            (None, [None]),
            (bool, [True, False]),
            (bytes, [b"", b"a", b"bytes"]),
            (dict, [{}, {"a": "b"}]),
            (float, [-1.0, 0.0, 1.0]),
            (int, [-1, 0, 1]),
            (list, [[], ["a"], ["a", 1]]),
            (set, [set(), {"a", "b", "c"}]),
            (str, ["", "a", "a string", r"", r"a", r"astring"]),
            (tuple, [(), ("a",), ("a", 1)]),
        ],
    )
    def test_typecheck(self, tp, vals):
        spec = s(tp)
        assert all(spec.is_valid(v) for v in vals)

    @pytest.fixture
    def python_vals(self):
        return [
            None,
            True,
            False,
            b"",
            b"a",
            b"bytes",
            {},
            {"a": "b"},
            -1.0,
            0.0,
            1.0,
            -1,
            0,
            1,
            [],
            ["a"],
            ["a", 1],
            set(),
            {"a", "b", "c"},
            "",
            "a",
            "a string",
            r"",
            r"a",
            r"astring",
            (),
            ("a",),
            ("a", 1),
        ]

    @pytest.mark.parametrize(
        "tp", [bool, bytes, dict, float, int, list, set, str, tuple]
    )
    def test_typecheck_failure(self, tp, python_vals):
        spec = s(tp)
        vals = filter(lambda v: not isinstance(v, tp), python_vals)
        assert all(not spec.is_valid(v) for v in vals)
