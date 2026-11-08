"""作者：Wangyuan；日期：2026-11-08。取消状态和加权分布边界回归。"""
import unittest
from simulation.chain_models import FlightOccurrence
from simulation.robust import weighted_percentile


class ApiRegressionTests(unittest.TestCase):
    def test_cancelled_result_is_cancelled_state(self):
        row = FlightOccurrence('synthetic', '2040-01-01', 'ZZ100', 'XXXX', 'YYYY', result_kind='cancelled')
        self.assertEqual(row.status_machine(), 'cancelled')

    def test_zero_weight_does_not_change_lowest_quantile(self):
        self.assertEqual(weighted_percentile([0, 10], [0, 1], 0), 10)
        self.assertEqual(weighted_percentile([0, 10], [0, 0], 0), 0)


if __name__ == '__main__':
    unittest.main()
