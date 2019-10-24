import sys
import uuid
from datetime import date, datetime, time, timezone
from enum import Enum

import pytest

from dataspec import INVALID, Spec, s


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


class TestStringFormatValidation:
    class TestEmailFormat:
        @pytest.fixture
        def email_spec(self) -> Spec:
            return s.str(format_="email")

        @pytest.mark.parametrize(
            "v",
            [
                "chris@localhost",
                "chris@gmail.com",
                "chris+extra@gmail.com",
                "chris.person@gmail.com",
            ],
        )
        def test_is_email_str(self, email_spec: Spec, v):
            assert email_spec.is_valid(v)

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
                "chris",
                "chris@",
                "@gmail",
                "@gmail.com",
            ],
        )
        def test_is_not_email_str(self, email_spec: Spec, v):
            assert not email_spec.is_valid(v)

    class TestISODateFormat:
        @pytest.fixture
        def conform(self):
            if sys.version_info >= (3, 7):
                return date.fromisoformat
            else:
                from dataspec.factories import _str_to_iso_date

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

    @pytest.mark.skipif(
        sys.version_info <= (3, 7), reason="time.fromisoformat added in Python 3.7"
    )
    class TestISOTimeFormat:
        @pytest.fixture
        def conform(self):
            return time.fromisoformat

        @pytest.fixture
        def conforming_time_spec(self) -> Spec:
            return s.str(conform_format="iso-time")

        @pytest.fixture
        def time_spec(self) -> Spec:
            return s.str(format_="iso-time")

        @pytest.mark.parametrize(
            "v",
            [
                "18",
                "18-00:00",
                "18.335",
                "18.335-00:00",
                "18:03",
                "18:03-00:00",
                "18:03.335",
                "18:03.335-00:00",
                "18:03:50",
                "18:03:50-00:00",
                "18:03:50.617",
                "18:03:50.617-00:00",
                "18:03:50.617332",
                "18:03:50.617332-00:00",
            ],
        )
        def test_is_time_str(
            self, time_spec: Spec, conforming_time_spec: Spec, conform, v
        ):
            assert time_spec.is_valid(v)
            assert conforming_time_spec.is_valid(v)
            assert conform(v) == conforming_time_spec.conform(v)

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
                "2019-10-12",
                "1945-09-02",
                "1066-10-14",
            ],
        )
        def test_is_not_time_str(self, time_spec: Spec, conforming_time_spec: Spec, v):
            assert not time_spec.is_valid(v)
            assert not conforming_time_spec.is_valid(v)

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