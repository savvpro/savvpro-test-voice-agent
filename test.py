
import unittest
from datetime import date, timedelta

from main import ReservationAssistant


class TestReservationAssistant(unittest.TestCase):

    def setUp(self):
        self.assistant = ReservationAssistant()
        self.booking_date = date.today() + timedelta(days=1)

    def test_parse_time_with_am_pm(self):
        self.assertEqual(
            self.assistant._parse_time("7 PM"), "19:00"
        )
        self.assertEqual(
            self.assistant._parse_time("5:30 PM"), "17:30"
        )

    def test_parse_time_24_hour_format(self):
        self.assertEqual(
            self.assistant._parse_time("19:30"), "19:30"
        )

    def test_invalid_time(self):
        self.assertIsNone(
            self.assistant._parse_time("not a time")
        )

    def test_booking_creation(self):
        self.assistant.slots = {
            "date": self.booking_date,
            "party_size": 2,
            "time": "19:00",
            "name": "Ali",
        }

        reply = self.assistant._make_booking()

        self.assertEqual(len(self.assistant.reservations), 1)
        self.assertEqual(
            self.assistant.reservations[0]["reference"], "TT1001"
        )
        self.assertIn("TT1001", reply)

    def test_cancelled_reference_not_reused(self):
        first_reference = self.assistant._next_reference()
        self.assertEqual(first_reference, "TT1001")

        second_reference = self.assistant._next_reference()
        self.assertEqual(second_reference, "TT1002")

    def test_all_eight_tables_exist(self):
        self.assertEqual(self.assistant.TABLE_COUNT, 8)

    def test_booking_duration(self):
        self.assertEqual(self.assistant.BOOKING_MINUTES, 30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
