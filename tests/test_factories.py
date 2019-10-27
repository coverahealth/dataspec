import sys
import uuid
from datetime import date, datetime, time, timezone
from enum import Enum

import pytest

from dataspec import INVALID, Spec, s

try:
    from dateutil.parser import parse as parse_date
except ImportError:
    parse_date = None


try:
    import phonenumbers
except ImportError:
    phonenumbers = None


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

    class TestLengthValidation:
        @pytest.fixture
        def length_spec(self) -> Spec:
            return s.bytes(length=3)

        @pytest.mark.parametrize("v", [-1, -100])
        def test_min_count(self, v):
            with pytest.raises(ValueError):
                return s.bytes(length=v)

        @pytest.mark.parametrize("v", [-0.5, 0.5, 2.71])
        def test_int_count(self, v):
            with pytest.raises(TypeError):
                s.bytes(length=v)

        @pytest.mark.parametrize("v", [b"xxx", b"xxy", b"773", b"833"])
        def test_length_spec(self, length_spec: Spec, v):
            assert length_spec.is_valid(v)

        @pytest.mark.parametrize("v", [b"", b"x", b"xx", b"xxxx", b"xxxxx"])
        def test_length_spec_failure(self, length_spec: Spec, v):
            assert not length_spec.is_valid(v)

        @pytest.mark.parametrize(
            "opts",
            [
                {"length": 2, "minlength": 3},
                {"length": 2, "maxlength": 3},
                {"length": 2, "minlength": 1, "maxlength": 3},
            ],
        )
        def test_length_and_minlength_or_maxlength_agreement(self, opts):
            with pytest.raises(ValueError):
                s.bytes(**opts)

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


class TestEmailSpecValidation:
    @pytest.mark.parametrize(
        "spec_kwargs",
        [
            {"host": "coverahealth.com"},
            {"localpart": "chris.person"},
            {"domain": "coverahealth.com", "domain_regex": r"(api\.)?coverahealth.com"},
        ],
    )
    def test_invalid_email_specs(self, spec_kwargs):
        with pytest.raises(ValueError):
            s.email(**spec_kwargs)

    @pytest.fixture
    def email_spec(self) -> Spec:
        return s.email()

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

    @pytest.fixture
    def email_address(self) -> str:
        return "chris.person@gmail.com"

    @pytest.mark.parametrize(
        "spec_kwargs",
        [
            {"username": "chris.person"},
            {"username_in": {"jdoe", "chris.person"}},
            {"username_regex": r"(chris\.person|jdoe)"},
            {"domain": "gmail.com"},
            {"domain_in": {"coverahealth.com", "gmail.com"}},
            {"domain_regex": r"(coverahealth|gmail)\.com"},
        ],
    )
    def test_is_email_str(self, email_address: str, spec_kwargs):
        spec = s.email(**spec_kwargs)
        assert spec.is_valid(email_address)
        assert email_address == spec.conform(email_address)

    @pytest.mark.parametrize(
        "spec_kwargs",
        [
            {"username": "jdoe"},
            {"username_in": {"jdoe", "john.doe"}},
            {"username_regex": r"(john\.|j)doe"},
            {"domain": "coverahealth.com"},
            {"domain_in": {"mail.coverahealth.com", "coverahealth.com"}},
            {"domain_regex": r"(mail\.)?coverahealth\.com"},
        ],
    )
    def test_is_not_email_str(self, email_address: str, spec_kwargs):
        spec = s.email(**spec_kwargs)
        assert not spec.is_valid(email_address)
        assert INVALID is spec.conform(email_address)


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

    def test_before_after_agreement(self):
        s.inst(
            before=datetime(year=2000, month=1, day=1),
            after=datetime(year=2000, month=1, day=1),
        )
        s.inst(
            before=datetime(year=2000, month=1, day=1),
            after=datetime(year=2000, month=1, day=2),
        )

        with pytest.raises(ValueError):
            s.inst(
                before=datetime(year=2000, month=1, day=2),
                after=datetime(year=2000, month=1, day=1),
            )

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

    def test_before_after_agreement(self):
        s.date(
            before=date(year=2000, month=1, day=1),
            after=date(year=2000, month=1, day=1),
        )
        s.date(
            before=date(year=2000, month=1, day=1),
            after=date(year=2000, month=1, day=2),
        )

        with pytest.raises(ValueError):
            s.date(
                before=date(year=2000, month=1, day=2),
                after=date(year=2000, month=1, day=1),
            )

    class TestIsAwareSpec:
        def test_aware_spec(self):
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

    def test_before_after_agreement(self):
        s.date(
            before=time(hour=12, minute=0, second=0),
            after=time(hour=12, minute=0, second=0),
        )
        s.date(
            before=time(hour=12, minute=0, second=0),
            after=time(hour=12, minute=0, second=1),
        )

        with pytest.raises(ValueError):
            s.date(
                before=time(hour=12, minute=0, second=2),
                after=time(hour=12, minute=0, second=0),
            )

    class TestIsAwareSpec:
        @pytest.fixture
        def aware_spec(self) -> Spec:
            return s.time(is_aware=True)

        def test_aware_spec(self, aware_spec):
            assert aware_spec.is_valid(time(tzinfo=timezone.utc))

        def test_aware_spec_failure(self, aware_spec):
            assert not aware_spec.is_valid(time())


@pytest.mark.skipif(parse_date is None, reason="python-dateutil must be installed")
class TestInstStringSpecValidation:
    ISO_DATETIMES = [
        ("2003-09-25T10:49:41", datetime(2003, 9, 25, 10, 49, 41)),
        ("2003-09-25T10:49", datetime(2003, 9, 25, 10, 49)),
        ("2003-09-25T10", datetime(2003, 9, 25, 10)),
        ("2003-09-25", datetime(2003, 9, 25)),
        ("20030925T104941", datetime(2003, 9, 25, 10, 49, 41)),
        ("20030925T1049", datetime(2003, 9, 25, 10, 49, 0)),
        ("20030925T10", datetime(2003, 9, 25, 10)),
        ("20030925", datetime(2003, 9, 25)),
        ("2003-09-25 10:49:41,502", datetime(2003, 9, 25, 10, 49, 41, 502000)),
        ("19760704", datetime(1976, 7, 4)),
        ("0099-01-01T00:00:00", datetime(99, 1, 1, 0, 0)),
        ("0031-01-01T00:00:00", datetime(31, 1, 1, 0, 0)),
        ("20080227T21:26:01.123456789", datetime(2008, 2, 27, 21, 26, 1, 123456)),
        ("0003-03-04", datetime(3, 3, 4)),
        ("950404 122212", datetime(1995, 4, 4, 12, 22, 12)),
    ]
    NON_ISO_DATETIMES = [
        ("Thu Sep 25 10:36:28 2003", datetime(2003, 9, 25, 10, 36, 28)),
        ("Thu Sep 25 2003", datetime(2003, 9, 25)),
        ("199709020908", datetime(1997, 9, 2, 9, 8)),
        ("19970902090807", datetime(1997, 9, 2, 9, 8, 7)),
        ("09-25-2003", datetime(2003, 9, 25)),
        ("25-09-2003", datetime(2003, 9, 25)),
        ("10-09-2003", datetime(2003, 10, 9)),
        ("10-09-03", datetime(2003, 10, 9)),
        ("2003.09.25", datetime(2003, 9, 25)),
        ("09.25.2003", datetime(2003, 9, 25)),
        ("25.09.2003", datetime(2003, 9, 25)),
        ("10.09.2003", datetime(2003, 10, 9)),
        ("10.09.03", datetime(2003, 10, 9)),
        ("2003/09/25", datetime(2003, 9, 25)),
        ("09/25/2003", datetime(2003, 9, 25)),
        ("25/09/2003", datetime(2003, 9, 25)),
        ("10/09/2003", datetime(2003, 10, 9)),
        ("10/09/03", datetime(2003, 10, 9)),
        ("2003 09 25", datetime(2003, 9, 25)),
        ("09 25 2003", datetime(2003, 9, 25)),
        ("25 09 2003", datetime(2003, 9, 25)),
        ("10 09 2003", datetime(2003, 10, 9)),
        ("10 09 03", datetime(2003, 10, 9)),
        ("25 09 03", datetime(2003, 9, 25)),
        ("03 25 Sep", datetime(2003, 9, 25)),
        ("25 03 Sep", datetime(2025, 9, 3)),
        ("  July   4 ,  1976   12:01:02   am  ", datetime(1976, 7, 4, 0, 1, 2)),
        ("Wed, July 10, '96", datetime(1996, 7, 10, 0, 0)),
        ("1996.July.10 AD 12:08 PM", datetime(1996, 7, 10, 12, 8)),
        ("July 4, 1976", datetime(1976, 7, 4)),
        ("7 4 1976", datetime(1976, 7, 4)),
        ("4 jul 1976", datetime(1976, 7, 4)),
        ("4 Jul 1976", datetime(1976, 7, 4)),
        ("7-4-76", datetime(1976, 7, 4)),
        ("0:01:02 on July 4, 1976", datetime(1976, 7, 4, 0, 1, 2)),
        ("July 4, 1976 12:01:02 am", datetime(1976, 7, 4, 0, 1, 2)),
        ("Mon Jan  2 04:24:27 1995", datetime(1995, 1, 2, 4, 24, 27)),
        ("04.04.95 00:22", datetime(1995, 4, 4, 0, 22)),
        ("Jan 1 1999 11:23:34.578", datetime(1999, 1, 1, 11, 23, 34, 578000)),
        ("3rd of May 2001", datetime(2001, 5, 3)),
        ("5th of March 2001", datetime(2001, 3, 5)),
        ("1st of May 2003", datetime(2003, 5, 1)),
        ("13NOV2017", datetime(2017, 11, 13)),
        ("December.0031.30", datetime(31, 12, 30)),
    ]
    ALL_DATETIMES = ISO_DATETIMES + NON_ISO_DATETIMES

    @pytest.fixture
    def inst_str_spec(self) -> Spec:
        return s.inst_str()

    @pytest.mark.parametrize("date_str,datetime_obj", ALL_DATETIMES)
    def test_inst_str_validation(self, inst_str_spec: Spec, date_str, datetime_obj):
        assert inst_str_spec.is_valid(date_str)
        assert datetime_obj == inst_str_spec.conform(date_str)

    @pytest.mark.parametrize(
        "v", ["", "abcde", "Tue September 32 2019", 5, 3.14, None, {}, set(), []]
    )
    def test_inst_str_validation_failure(self, inst_str_spec: Spec, v):
        assert not inst_str_spec.is_valid(v)
        assert INVALID is inst_str_spec.conform(v)

    @pytest.fixture
    def iso_inst_str_spec(self) -> Spec:
        return s.inst_str(iso_only=True)

    @pytest.mark.parametrize("date_str,datetime_obj", ISO_DATETIMES)
    def test_iso_inst_str_validation(
        self, iso_inst_str_spec: Spec, date_str, datetime_obj
    ):
        assert iso_inst_str_spec.is_valid(date_str)
        assert datetime_obj == iso_inst_str_spec.conform(date_str)

    @pytest.mark.parametrize(
        "v",
        ["", "abcde", "Tue September 32 2019", 5, 3.14, None, {}, set(), []]
        + list(map(lambda v: v[0], NON_ISO_DATETIMES)),
    )
    def test_iso_inst_str_validation_failure(self, iso_inst_str_spec: Spec, v):
        assert not iso_inst_str_spec.is_valid(v)
        assert INVALID is iso_inst_str_spec.conform(v)


@pytest.mark.parametrize("v", [None, "", "a string"])
def test_nilable(v):
    assert s.nilable(s.is_str).is_valid(v)


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


@pytest.mark.skipif(phonenumbers is None, reason="phonenumbers must be installed")
class TestPhoneNumberStringSpecValidation:
    @pytest.mark.parametrize(
        "region", ["US", "Us", "uS", "us", "GB", "Gb", "gB", "gb", "DE", "dE", "De"]
    )
    def test_valid_regions(self, region):
        s.phone(region=region)

    @pytest.mark.parametrize("region", ["USA", "usa", "america", "ZZ", "zz", "FU"])
    def test_invalid_regions(self, region):
        with pytest.raises(ValueError):
            s.phone(region=region)

    @pytest.fixture
    def phone_spec(self) -> Spec:
        return s.phone(region="US")

    @pytest.mark.parametrize(
        "v",
        [
            "9175555555",
            "+19175555555",
            "(917) 555-5555",
            "917-555-5555",
            "1-917-555-5555",
            "917.555.5555",
            "917 555 5555",
        ],
    )
    def test_valid_phone_number(self, phone_spec: Spec, v):
        assert phone_spec.is_valid(v)
        assert "+19175555555" == phone_spec.conform(v)

    @pytest.mark.parametrize(
        "v",
        [
            None,
            -50,
            4.9,
            4,
            0,
            3.14,
            [],
            set(),
            "",
            "917555555",
            "+1917555555",
            "(917) 555-555",
            "917-555-555",
            "1-917-555-555",
            "917.555.555",
            "917 555 555",
        ],
    )
    def test_invalid_phone_number(self, phone_spec: Spec, v):
        assert not phone_spec.is_valid(v)
        assert INVALID is phone_spec.conform(v)


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
        def test_count_spec(self, count_spec: Spec, v):
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


class TestURLSpecValidation:
    @pytest.mark.parametrize(
        "spec_kwargs",
        [
            {},
            {"host": "coverahealth.com"},
            {
                "hostname": "coverahealth.com",
                "hostname_regex": r"(api\.)?coverahealth.com",
            },
            {"port_regex": r"80|443"},
        ],
    )
    def test_invalid_url_specs(self, spec_kwargs):
        with pytest.raises(ValueError):
            s.url(**spec_kwargs)

    @pytest.mark.parametrize(
        "spec_kwargs", [{"hostname_regex": b"coverahealth.com"}, {"port_in": [80, 443]}]
    )
    def test_invalid_url_spec_argument_types(self, spec_kwargs):
        with pytest.raises(TypeError):
            s.url(**spec_kwargs)

    @pytest.mark.parametrize(
        "v", [None, 25, 3.14, {}, [], set(), (), "", "//[coverahealth.com"]
    )
    def test_invalid_url(self, v):
        assert not s.url(hostname_regex=r".*").is_valid(v)

    @pytest.fixture
    def urlstr(self) -> str:
        return (
            "https://jdoe:securepass@api.coverahealth.com:80/v1/patients"
            "?last-name=Smith&last-name=Doe&birth-year=1985#user-profile"
        )

    def test_valid_query_str(self, urlstr):
        assert s.url(
            query={
                "last-name": [s.all(s.str(), str.istitle)],
                "birth-year": [s.str(regex=r"\d{4}")],
            }
        ).is_valid(urlstr)

    def test_invalid_query_str(self, urlstr):
        assert not s.url(
            query={
                "last-name": [s.str(), {"count": 1}],
                "birth-year": [s.str(regex=r"\d{4}")],
            }
        ).is_valid(urlstr)

    @pytest.mark.parametrize(
        "spec_kwargs",
        [
            {"scheme": "https"},
            {"scheme_in": {"https", "http"}},
            {"scheme_regex": r"https?"},
            {"netloc": "jdoe:securepass@api.coverahealth.com:80"},
            {
                "netloc_in": {
                    "jdoe:securepass@api.coverahealth.com:80",
                    "jdoe:securepass@api.coverahealth.com:443",
                }
            },
            {"netloc_regex": r"jdoe:securepass@api\.coverahealth\.com:(80|443)"},
            {"path": "/v1/patients"},
            {"path_in": {"/v1/patients", "/v2/patients"}},
            {"path_regex": r"\/(v1|v2)\/patients"},
            {"fragment": "user-profile"},
            {"fragment_in": {"user-profile", "user-addresses"}},
            {"fragment_regex": r"user\-(profile|addresses)"},
            {"username": "jdoe"},
            {"username_in": {"jdoe", "doej"}},
            {"username_regex": r"jdoe"},
            {"password": "securepass"},
            {"password_in": {"securepass", "insecurepass"}},
            {"password_regex": r"(in)?securepass"},
            {"hostname": "api.coverahealth.com"},
            {"hostname_in": {"coverahealth.com", "api.coverahealth.com"}},
            {"hostname_regex": r"(api\.)?coverahealth\.com"},
            {"port": 80},
            {"port_in": {80, 443}},
        ],
    )
    def test_is_url_str(self, urlstr: str, spec_kwargs):
        assert s.url(**spec_kwargs).is_valid(urlstr)

    @pytest.mark.parametrize(
        "spec_kwargs",
        [
            {"scheme": "http"},
            {"scheme_in": {"http", "ftp"}},
            {"scheme_regex": r"(ht|f)tp"},
            {"netloc": "carl:insecurepass@api.coverahealth.com:80"},
            {
                "netloc_in": {
                    "carl:insecurepass@api.coverahealth.com:80",
                    "carl:insecurepass@api.coverahealth.com:443",
                }
            },
            {"netloc_regex": r"carl:insecurepass@api\.coverahealth\.com:(80|443)"},
            {"path": "/v2/patients"},
            {"path_in": {"/v2/patients", "/v3/patients"}},
            {"path_regex": r"\/(v2|v3)\/patients"},
            {"fragment": "user-addresses"},
            {"fragment_in": {"user-phone-numbers", "user-addresses"}},
            {"fragment_regex": r"user\-(phone\-numbers|addresses)"},
            {"username": "carl"},
            {"username_in": {"carl", "vic"}},
            {"username_regex": r"(carl|vic)"},
            {"password": "insecurepass"},
            {"password_in": {"rlysecurepass", "insecurepass"}},
            {"password_regex": r"(rly|in)securepass"},
            {"hostname": "coverahealth.com"},
            {"hostname_in": {"coverahealth.com", "data.coverahealth.com"}},
            {"hostname_regex": r"(data\.)?coverahealth\.com"},
            {"port": 21},
            {"port_in": {21, 443}},
        ],
    )
    def test_is_not_url_str(self, urlstr: str, spec_kwargs):
        assert not s.url(**spec_kwargs).is_valid(urlstr)


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
        def test_invalid_uuid_version_spec(self, versions):
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
